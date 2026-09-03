import csv
import math
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from sgp4.api import Satrec

MU = 398600.4418
R_EARTH = 6378.137

output_csv = r"P:\Projects\active_satellites_catalog.csv"
output_tle = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "data", "active_satellites.tle")

# Groups to collect diverse orbital regimes
groups = ["active", "stations", "visual", "gnss", "weather", "resource", "science", "oneweb"]
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

all_tles = []
print("Fetching real active satellite sets from CelesTrak...")

for g in groups:
    url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={g}&FORMAT=tle"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            print(f"  Fetched group '{g}': {len(lines)//3} satellites")
            all_tles.extend(lines)
    except Exception as e:
        print(f"  Group '{g}' failed: {e}")

if not all_tles:
    scratch_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch_tle.txt")
    if os.path.exists(scratch_path):
        with open(scratch_path, "r", encoding="utf-8") as f:
            all_tles = [l.strip() for l in f.readlines() if l.strip()]

print(f"Total TLE lines collected: {len(all_tles)}")

satellites = []
seen_norad = set()
idx = 0

while idx < len(all_tles):
    if idx + 2 < len(all_tles) and all_tles[idx+1].startswith("1 ") and all_tles[idx+2].startswith("2 "):
        name = all_tles[idx]
        l1 = all_tles[idx+1]
        l2 = all_tles[idx+2]
        idx += 3
    elif idx + 1 < len(all_tles) and all_tles[idx].startswith("1 ") and all_tles[idx+1].startswith("2 "):
        name = f"OBJECT {all_tles[idx][2:7]}"
        l1 = all_tles[idx]
        l2 = all_tles[idx+1]
        idx += 2
    else:
        idx += 1
        continue

    try:
        norad_id = int(l1[2:7])
        if norad_id in seen_norad:
            continue
        seen_norad.add(norad_id)

        line0_clean = re.sub(r"^0\s+", "", name).strip()
        sat = Satrec.twoline2rv(l1, l2)
        intl_des = l1[9:17].strip()

        year = sat.epochyr
        full_year = year + 2000 if year < 57 else year + 1900
        epoch_start = datetime(full_year, 1, 1, tzinfo=timezone.utc)
        epoch_ts = epoch_start + timedelta(days=sat.epochdays - 1)

        n_rad_min = sat.no_kozai
        if n_rad_min <= 0:
            continue

        period_minutes = (2 * math.pi) / n_rad_min
        n_rad_s = n_rad_min / 60.0
        a = (MU / (n_rad_s**2)) ** (1 / 3)
        e = sat.ecco
        apogee = a * (1 + e) - R_EARTH
        perigee = a * (1 - e) - R_EARTH
        inclination = math.degrees(sat.inclo)

        if perigee <= 2000.0:
            regime = "LEO"
        elif perigee > 2000.0 and apogee < 35500.0:
            regime = "MEO"
        elif 35500.0 <= apogee <= 36500.0 and e < 0.1:
            regime = "GEO"
        elif apogee > 35500.0 or e >= 0.25:
            regime = "HEO"
        else:
            regime = "OTHER"

        name_upper = line0_clean.upper()
        if "DEB" in name_upper or "DEBRIS" in name_upper:
            obj_type = "debris"
        elif "R/B" in name_upper or "ROCKET" in name_upper or "STAGE" in name_upper:
            obj_type = "rocket_body"
        else:
            obj_type = "payload"

        satellites.append({
            "norad_id": norad_id,
            "name": line0_clean or f"OBJECT {norad_id}",
            "international_designator": intl_des,
            "object_type": obj_type,
            "orbit_regime": regime,
            "apogee_km": round(apogee, 2),
            "perigee_km": round(perigee, 2),
            "inclination_deg": round(inclination, 2),
            "period_minutes": round(period_minutes, 2),
            "line1": l1,
            "line2": l2
        })
    except Exception:
        continue

# Choose 2,500 active satellites
target_sats = satellites[:2500] if len(satellites) >= 2500 else satellites
print(f"Writing {len(target_sats):,} satellites to {output_csv}...")

with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "norad_id", "name", "international_designator", "object_type", 
        "orbit_regime", "apogee_km", "perigee_km", "inclination_deg", 
        "period_minutes", "line1", "line2"
    ])
    writer.writeheader()
    writer.writerows(target_sats)

# Update bundled active_satellites.tle as well
tle_content = ""
for s in target_sats:
    tle_content += f"{s['name']}\n{s['line1']}\n{s['line2']}\n"

with open(output_tle, "w", encoding="utf-8") as f:
    f.write(tle_content)

print(f"\n[SUCCESS] Generated '{output_csv}' with {len(target_sats):,} active space objects!")
print(f"[SUCCESS] Updated '{output_tle}' with {len(target_sats):,} active space objects!")
