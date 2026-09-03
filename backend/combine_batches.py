import csv
import os

csv1 = r"P:\Projects\active_satellites_catalog.csv"
csv2 = r"P:\Projects\active_satellites_catalog_batch_2.csv"
csv_all = r"P:\Projects\all_5000_satellites_catalog.csv"
tle_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "data", "active_satellites.tle")

sats = {}
for path in [csv1, csv2]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                sats[int(r["norad_id"])] = r

print(f"Total combined unique satellites: {len(sats):,}")

with open(csv_all, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "norad_id", "name", "international_designator", "object_type", 
        "orbit_regime", "apogee_km", "perigee_km", "inclination_deg", 
        "period_minutes", "line1", "line2"
    ])
    writer.writeheader()
    writer.writerows(sats.values())

tle_content = ""
for s in sats.values():
    tle_content += f"{s['name']}\n{s['line1']}\n{s['line2']}\n"

with open(tle_file, "w", encoding="utf-8") as f:
    f.write(tle_content)

print(f"[SUCCESS] Saved {len(sats):,} satellites to {csv_all} and updated {tle_file}!")
