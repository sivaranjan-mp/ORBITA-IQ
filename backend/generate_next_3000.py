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

existing_csv = r"P:\Projects\active_satellites_catalog.csv"
output_csv = r"P:\Projects\active_satellites_catalog_batch_2.csv"
output_sql = r"P:\Projects\insert_catalog_satellites_batch_2.sql"

# Load existing NORAD IDs so we ONLY get brand new space objects
existing_norads = set()
if os.path.exists(existing_csv):
    with open(existing_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            existing_norads.add(int(r["norad_id"]))

print(f"Loaded {len(existing_norads):,} existing NORAD IDs to avoid duplicates.")

# Rich groups to fetch the next 3,000+ objects
groups = [
    "starlink",
    "oneweb",
    "planet",
    "spire",
    "iridium-NEXT",
    "swarm",
    "globalstar",
    "geo",
    "intelsat",
    "ses",
    "amateur",
    "cubesat",
    "molniya",
    "radar",
    "military",
    "other-comm",
    "1999-025",
    "iridium-33-debris",
    "cosmos-2251-debris",
    "fengyun-1c-debris",
    "last-30-days"
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
all_tles = []

print("Fetching next batch of orbital objects from CelesTrak...")
for g in groups:
    url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={g}&FORMAT=tle"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            print(f"  Fetched group '{g}': {len(lines)//3:,} objects")
            all_tles.extend(lines)
    except Exception as e:
        print(f"  Group '{g}' failed: {e}")

print(f"Total raw lines collected: {len(all_tles):,}")

new_satellites = []
seen_new_norad = set()
idx = 0

while idx < len(all_tles) and len(new_satellites) < 3000:
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
        if norad_id in existing_norads or norad_id in seen_new_norad:
            continue
        seen_new_norad.add(norad_id)

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

        new_satellites.append({
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

print(f"Collected {len(new_satellites):,} brand new space objects.")

# 1. Write CSV
with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "norad_id", "name", "international_designator", "object_type", 
        "orbit_regime", "apogee_km", "perigee_km", "inclination_deg", 
        "period_minutes", "line1", "line2"
    ])
    writer.writeheader()
    writer.writerows(new_satellites)
print(f"[SUCCESS] Saved CSV to {output_csv}")

# 2. Write SQL
with open(output_sql, "w", encoding="utf-8") as f:
    f.write("-- ============================================================================\n")
    f.write("-- Satellite Operations & Conjunction Intelligence Dashboard\n")
    f.write(f"-- Bulk Space Catalog Ingestion (Batch 2: {len(new_satellites):,} objects)\n")
    f.write("-- ============================================================================\n\n")
    
    chunk_size = 100
    for i in range(0, len(new_satellites), chunk_size):
        chunk = new_satellites[i:i+chunk_size]
        f.write("INSERT INTO public.catalog_satellites (\n")
        f.write("  norad_id, name, international_designator, object_type, orbit_regime,\n")
        f.write("  apogee_km, perigee_km, inclination_deg, period_minutes, eccentricity,\n")
        f.write("  line1, line2, epoch, updated_at\n")
        f.write(") VALUES\n")
        
        val_lines = []
        for r in chunk:
            nid = int(r["norad_id"])
            name_esc = r["name"].replace("'", "''")
            intl_esc = (r.get("international_designator") or "").replace("'", "''")
            obj_type = (r.get("object_type") or "payload").replace("'", "''")
            regime = (r.get("orbit_regime") or "LEO").replace("'", "''")
            apogee = float(r.get("apogee_km") or 0.0)
            perigee = float(r.get("perigee_km") or 0.0)
            inc = float(r.get("inclination_deg") or 0.0)
            period = float(r.get("period_minutes") or 0.0)
            ecc = 0.0001
            l1_esc = r["line1"].replace("'", "''")
            l2_esc = r["line2"].replace("'", "''")
            
            val_lines.append(
                f"  ({nid}, '{name_esc}', '{intl_esc}', '{obj_type}', '{regime}', "
                f"{apogee}, {perigee}, {inc}, {period}, {ecc}, "
                f"'{l1_esc}', '{l2_esc}', NOW(), NOW())"
            )
            
        f.write(",\n".join(val_lines))
        f.write("\nON CONFLICT (norad_id) DO UPDATE SET\n")
        f.write("  name = EXCLUDED.name,\n")
        f.write("  international_designator = EXCLUDED.international_designator,\n")
        f.write("  object_type = EXCLUDED.object_type,\n")
        f.write("  orbit_regime = EXCLUDED.orbit_regime,\n")
        f.write("  apogee_km = EXCLUDED.apogee_km,\n")
        f.write("  perigee_km = EXCLUDED.perigee_km,\n")
        f.write("  inclination_deg = EXCLUDED.inclination_deg,\n")
        f.write("  period_minutes = EXCLUDED.period_minutes,\n")
        f.write("  line1 = EXCLUDED.line1,\n")
        f.write("  line2 = EXCLUDED.line2,\n")
        f.write("  updated_at = NOW();\n\n")

print(f"[SUCCESS] Saved SQL to {output_sql} ({os.path.getsize(output_sql):,} bytes)!")
