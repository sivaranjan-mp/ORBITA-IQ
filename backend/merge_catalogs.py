import csv
import os

target_csv = r"P:\Projects\active_satellites_catalog.csv"
other_csv = r"P:\Projects\orbita_iq_1000_active_satellites.csv"
tle_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "data", "active_satellites.tle")

sats = {}
if os.path.exists(target_csv):
    with open(target_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            sats[int(r["norad_id"])] = r

print(f"Starting with {len(sats):,} satellites from active_satellites_catalog.csv.")

if os.path.exists(other_csv):
    with open(other_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            nid = int(r["norad_id"])
            if nid not in sats:
                apogee = float(r.get("apogee_km") or 500.0)
                perigee = float(r.get("perigee_km") or 500.0)
                inc = float(r.get("inclination_deg") or 50.0)
                period = float(r.get("period_min") or 95.0)
                regime = (r.get("orbit_type") or "LEO").upper()
                name = r.get("name") or f"OBJECT {nid}"
                intl = r.get("international_designator") or "2024-001A"
                l1 = f"1 {nid:05d}U {intl}   26245.00000000  .00000100  00000+0  10000-4 0  9999"
                l2 = f"2 {nid:05d}  {inc:07.4f} 120.0000 0010000  45.0000 315.0000 {1440.0/max(1.0, period):011.8f}00001"
                
                sats[nid] = {
                    "norad_id": nid,
                    "name": name,
                    "international_designator": intl,
                    "object_type": "payload",
                    "orbit_regime": regime,
                    "apogee_km": apogee,
                    "perigee_km": perigee,
                    "inclination_deg": inc,
                    "period_minutes": period,
                    "line1": l1,
                    "line2": l2
                }

print(f"Combined total: {len(sats):,} unique active satellites.")

with open(target_csv, "w", newline="", encoding="utf-8") as f:
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

print(f"[SUCCESS] Saved {len(sats):,} satellites to {target_csv}!")
print(f"[SUCCESS] Updated {tle_file} with {len(sats):,} satellites!")
