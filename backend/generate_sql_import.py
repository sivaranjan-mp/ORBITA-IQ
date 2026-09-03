import csv
import os

csv_path = r"P:\Projects\active_satellites_catalog.csv"
sql_path = r"P:\Projects\insert_catalog_satellites.sql"

with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Converting {len(rows):,} satellites to SQL INSERT statements...")

with open(sql_path, "w", encoding="utf-8") as f:
    f.write("-- ============================================================================\n")
    f.write("-- Satellite Operations & Conjunction Intelligence Dashboard\n")
    f.write(f"-- Bulk Space Catalog Ingestion ({len(rows):,} active space objects)\n")
    f.write("-- ============================================================================\n\n")
    
    # Split into chunks of 100 for fast SQL editor execution
    chunk_size = 100
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i+chunk_size]
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

print(f"[SUCCESS] Generated {sql_path} ({os.path.getsize(sql_path):,} bytes, {len(rows):,} satellites)!")
