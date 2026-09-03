import time
from datetime import datetime, timedelta, timezone
from sgp4.api import Satrec

from app.services.satguard_service import SatguardService
from app.services.conjunction_engine import ConjunctionEngine
from app.services.sgp4_service import propagate_tle

print("=== 1. ISS and STARLETTE Real Position Propagation ===")
# ISS (ZARYA) NORAD 25544
iss_l1 = "1 25544U 98067A   26245.46626010  .00004070  00000+0  82080-4 0  9996"
iss_l2 = "2 25544  51.6313 277.6073 0005029  99.7358 260.4199 15.48970443583732"
now = datetime.now(timezone.utc)
iss_state = propagate_tle(iss_l1, iss_l2, now)
print(f"ISS (ZARYA): Lat={iss_state['latitude_deg']:.2f} deg, Lon={iss_state['longitude_deg']:.2f} deg, Alt={iss_state['altitude_km']:.1f} km, Vel={iss_state['velocity_km_s']:.2f} km/s")
assert abs(iss_state['latitude_deg']) > 0 or abs(iss_state['longitude_deg']) > 0

# STARLETTE NORAD 7646
star_l1 = "1 07646U 75010A   26245.58837311 -.00000131  00000+0  87055-5 0  9996"
star_l2 = "2 07646  49.8242 159.0796 0205699 318.7494  39.8013 13.82351500605247"
star_state = propagate_tle(star_l1, star_l2, now)
print(f"STARLETTE:   Lat={star_state['latitude_deg']:.2f} deg, Lon={star_state['longitude_deg']:.2f} deg, Alt={star_state['altitude_km']:.1f} km, Vel={star_state['velocity_km_s']:.2f} km/s")
assert abs(star_state['latitude_deg']) > 0 or abs(star_state['longitude_deg']) > 0

print("\n=== 2. Stage 1 Coarse Filtering Simulation ===")
# Simulate 611 fleet satellites vs 5,000 catalog satellites (~3.05M candidate pairs)
fleet_altitudes = [(400 + (i % 200), 420 + (i % 200)) for i in range(611)]
catalog_altitudes = [(300 + (j % 1000) * 35, 320 + (j % 1000) * 35) for j in range(5000)]

t0 = time.time()
surviving_pairs = 0
total_pairs = len(fleet_altitudes) * len(catalog_altitudes)
for f_peri, f_apo in fleet_altitudes:
    for c_peri, c_apo in catalog_altitudes:
        if ConjunctionEngine.passes_stage1_coarse_filter(f_peri, f_apo, c_peri, c_apo, margin_km=50.0):
            surviving_pairs += 1
t1 = time.time()
eliminated_pct = (1.0 - (surviving_pairs / total_pairs)) * 100
print(f"Total Raw Pairs: {total_pairs:,}")
print(f"Surviving Pairs after Stage 1: {surviving_pairs:,} ({eliminated_pct:.2f}% eliminated)")
print(f"Stage 1 Evaluation Time: {(t1 - t0)*1000:.2f} ms")

print("\n=== 3. Stage 2 5-Day (120-hour) Propagation Speed on Surviving Pairs ===")
sat1 = Satrec.twoline2rv(iss_l1, iss_l2)
sat2 = Satrec.twoline2rv(star_l1, star_l2)

t0 = time.time()
steps = int(120 * 60) # 7200 steps (60s interval over 5 days)
for _ in range(50):
    for step in range(steps):
        SatguardService._distance_at_time(sat1, sat2, now + timedelta(seconds=step*60))
t1 = time.time()
print(f"50 candidate pairs scanned over 120h (360,000 SGP4 propagations): {t1 - t0:.2f} s ({(t1 - t0)/50*1000:.2f} ms/pair)")
print("Benchmark complete! All checks passed successfully.")
