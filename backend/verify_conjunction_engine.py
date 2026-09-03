import time
import os
import numpy as np
from datetime import datetime, timedelta, timezone
from sgp4.api import Satrec

from app.services.satguard_service import SatguardService
from app.services.conjunction_engine import ConjunctionEngine
from app.services.sgp4_service import propagate_tle
from app.services.probability_engine import ProbabilityEngine

print("==================================================================")
print("1. PROOF OF SYNTHETIC SEED KNOWN CLOSE-APPROACH CONJUNCTION TEST")
print("==================================================================")

# Primary: ISS (ZARYA) NORAD 25544 (Inclination 51.64 deg, ~418km Altitude)
tle1_1 = "1 25544U 98067A   26245.50000000  .00004070  00000+0  82080-4 0  9996"
tle1_2 = "2 25544  51.6313 277.6073 0005029  99.7358 260.4199 15.48970443583732"

# Secondary: Test Payload (Identical orbit offset by 0.0003 deg in RAAN & 0.0001 in mean anomaly)
# This creates a deterministic, physically valid close approach within the 5-day window
tle2_1 = "1 99001U 26001A   26245.50000000  .00004070  00000+0  82080-4 0  9999"
tle2_2 = "2 99001  51.6313 277.6085 0005029  99.7358 260.4208 15.48970443583732"

satrec1 = Satrec.twoline2rv(tle1_1, tle1_2)
satrec2 = Satrec.twoline2rv(tle2_1, tle2_2)

now = datetime.now(timezone.utc)
jd_base = now.toordinal() + 1721425.5
fr_base = (now.hour * 3600 + now.minute * 60 + now.second) / 86400.0
dt_secs = np.arange(0, 120 * 3600, 60, dtype=np.float64)
fr_array = fr_base + dt_secs / 86400.0
jd_array = np.full_like(fr_array, jd_base)

e1, r1, v1 = satrec1.sgp4_array(jd_array, fr_array)
e2, r2, v2 = satrec2.sgp4_array(jd_array, fr_array)

diff = r1 - r2
dists_sq = np.sum(diff * diff, axis=1)
min_idx = int(np.argmin(dists_sq))
coarse_min_km = float(np.sqrt(dists_sq[min_idx]))

from scipy.optimize import minimize_scalar
def dfunc(t_sec):
    dt = now + timedelta(seconds=t_sec)
    dist, *_ = SatguardService._distance_at_time(satrec1, satrec2, dt)
    return dist

res = minimize_scalar(dfunc, bounds=(max(0, (min_idx-1)*60), (min_idx+1)*60), method='bounded')
refined_tca_sec = float(res.x)
tca = now + timedelta(seconds=refined_tca_sec)
refined_dist_km, r1_vec, v1_vec, r2_vec, v2_vec, rel_vel = SatguardService._distance_at_time(satrec1, satrec2, tca)
risk_level = ConjunctionEngine.classify_risk_by_miss_distance(refined_dist_km)
prob_res = ProbabilityEngine.calculate_probability(miss_distance_m=refined_dist_km * 1000.0, hbr_m=20.0)

print(f"Primary Object:      ISS (ZARYA) (#25544)")
print(f"Secondary Object:    SYNTHETIC-DEB-ALPHA (#99001)")
print(f"TCA:                 {tca.isoformat()} (T+{refined_tca_sec/3600:.2f} hours)")
print(f"Miss Distance:       {refined_dist_km:.4f} km ({refined_dist_km * 1000.0:.1f} meters)")
print(f"Relative Velocity:   {rel_vel:.2f} km/s")
print(f"Collision Prob (Pc): {prob_res['pc']:.2e}")
print(f"Classified Risk:     {risk_level.upper()}")
assert refined_dist_km < 1.0, "Expected miss distance under 1 km"
assert risk_level == "critical", "Expected Critical risk level"
print("=> SYNTHETIC SEED DETECTION VERIFIED: Detected as CRITICAL (< 1 km) as expected!\n")


print("==================================================================")
print("2. FLEET VS. FLEET COMPLETE BENCHMARK (611 SATELLITES, 0 TRUNCATION)")
print("==================================================================")
tle_path = os.path.join('app', 'data', 'active_satellites.tle')
fleet = []
with open(tle_path, 'r', encoding='utf-8') as f:
    lines = [l.strip() for l in f if l.strip()]

idx = 0
while idx < len(lines) and len(fleet) < 611:
    if idx + 2 < len(lines) and lines[idx+1].startswith('1 ') and lines[idx+2].startswith('2 '):
        name = lines[idx]
        l1 = lines[idx+1]
        l2 = lines[idx+2]
        idx += 3
        try:
            apogee, perigee = SatguardService.compute_apogee_perigee(l1, l2)
            satrec = Satrec.twoline2rv(l1, l2)
            fleet.append({'name': name, 'norad_id': int(l1[2:7]), 'line1': l1, 'line2': l2, 'apogee': apogee, 'perigee': perigee, 'satrec': satrec})
        except Exception:
            pass
    else:
        idx += 1

print(f"Loaded {len(fleet)} Fleet Satellites.")

# Precompute 5-day ephemerides
t0 = time.time()
ephemeris = {}
valid_fleet = []
for s in fleet:
    e, r, v = s['satrec'].sgp4_array(jd_array, fr_array)
    if not (e != 0).any():
        ephemeris[s['norad_id']] = r
        valid_fleet.append(s)
t1 = time.time()
precompute_time = t1 - t0

# Stage 1 Coarse Filter
t2 = time.time()
raw_pairs = 0
stage1_survivors = []
for i in range(len(valid_fleet)):
    s1 = valid_fleet[i]
    for j in range(i + 1, len(valid_fleet)):
        s2 = valid_fleet[j]
        raw_pairs += 1
        if ConjunctionEngine.passes_stage1_coarse_filter(s1['perigee'], s1['apogee'], s2['perigee'], s2['apogee'], margin_km=50.0):
            stage1_survivors.append((s1, s2))
t3 = time.time()
stage1_time = t3 - t2
elim_pct = (1.0 - len(stage1_survivors)/raw_pairs) * 100

# Stage 2 Vectorized 5-Day Scan of 100% of Stage 1 survivors
t4 = time.time()
detected = []
for s1, s2 in stage1_survivors:
    r1 = ephemeris[s1['norad_id']]
    r2 = ephemeris[s2['norad_id']]
    diff = r1 - r2
    dists_sq = np.sum(diff*diff, axis=1)
    min_idx = int(np.argmin(dists_sq))
    min_dist = float(np.sqrt(dists_sq[min_idx]))
    if min_dist <= 50.0:
        detected.append((s1, s2, min_dist))
t5 = time.time()
stage2_time = t5 - t4

print(f"Raw Pairs Evaluated:              {raw_pairs:,}")
print(f"Stage 1 Survivors:                {len(stage1_survivors):,} ({elim_pct:.2f}% eliminated)")
print(f"Stage 1 Time:                     {stage1_time*1000:.2f} ms")
print(f"Stage 2 Scanned Pairs:            {len(stage1_survivors):,} (100% of survivors, 0 truncated)")
print(f"Stage 2 Time:                     {stage2_time:.2f} s ({stage2_time/max(1, len(stage1_survivors))*1000:.3f} ms/pair)")
print(f"Total Fleet vs. Fleet Run Time:   {precompute_time + stage1_time + stage2_time:.2f} seconds")
print(f"Close Approaches Detected (<50km): {len(detected)}")
print("==================================================================")
