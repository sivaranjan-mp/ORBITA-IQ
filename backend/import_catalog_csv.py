import asyncio
import csv
import os
import sys
from datetime import datetime, timezone
from typing import Optional

# Add the backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.catalog import CatalogSatellite
from app.services.catalog_service import CatalogService


def clean_val(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    val = val.strip()
    return val if val != "" else None


def to_float(val: Optional[str]) -> Optional[float]:
    v = clean_val(val)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def to_int(val: Optional[str]) -> Optional[int]:
    v = clean_val(val)
    if v is None:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


async def import_csv_to_catalog(csv_path: str, db_url: Optional[str] = None):
    if not os.path.exists(csv_path):
        print(f"Error: File '{csv_path}' not found.")
        return

    url = db_url or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("\n[NOTE] No SUPABASE_DB_URL found in environment.")
        print("To connect directly to Supabase Postgres, run:")
        print('  python backend/import_catalog_csv.py "P:\\Projects\\active_satellites_catalog.csv" --db-url "postgresql+asyncpg://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres"')
        print("\nAlternatively, you can copy and run the ready-made SQL file in your Supabase SQL Editor:")
        print("  P:\\Projects\\insert_catalog_satellites.sql\n")
        return

    engine = create_async_engine(url, echo=False, future=True)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"Loading satellite catalog from: {csv_path}...")
    
    # Detect encoding
    for enc in ("utf-8", "utf-8-sig", "latin1"):
        try:
            with open(csv_path, "r", encoding=enc) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                encoding_used = enc
                break
        except UnicodeDecodeError:
            continue
    else:
        print(f"Error: Could not decode file '{csv_path}' with utf-8 or latin1.")
        return

    if not rows:
        print("CSV file is empty.")
        return

    print(f"Found {len(rows):,} rows (using {encoding_used} encoding).")
    
    # Check headers
    first_row = rows[0]
    keys_lower = {k.lower().strip(): k for k in first_row.keys()}
    print(f"Detected columns: {list(first_row.keys())}")

    has_tle = ("line1" in keys_lower and "line2" in keys_lower)

    synced_count = 0
    now = datetime.now(timezone.utc)
    batch = []

    async with session_maker() as db:
        for idx, row in enumerate(rows, start=1):
            def get_f(col_name: str, default=None):
                k = keys_lower.get(col_name.lower())
                return row[k] if k else default

            name = clean_val(get_f("name", get_f("satname", get_f("satellite_name", "Unknown"))))
            norad_id = to_int(get_f("norad_id", get_f("norad_cat_id", get_f("catnr", get_f("id")))))
            intl_des = clean_val(get_f("international_designator", get_f("intl_des", get_f("cospar_id"))))
            obj_type = clean_val(get_f("object_type", get_f("type", "payload"))) or "payload"
            regime = clean_val(get_f("orbit_type", get_f("orbit_regime", get_f("regime", "LEO")))) or "LEO"

            line1 = clean_val(get_f("line1", get_f("tle_line1")))
            line2 = clean_val(get_f("line2", get_f("tle_line2")))

            if line1 and line2:
                parsed = CatalogService.parse_tle_elements(name or f"OBJECT {norad_id}", line1, line2)
                if parsed:
                    cat_sat = CatalogSatellite(
                        norad_id=parsed["norad_id"],
                        name=parsed["name"],
                        international_designator=parsed["international_designator"] or intl_des,
                        object_type=parsed["object_type"],
                        orbit_regime=parsed["orbit_regime"],
                        apogee_km=parsed["apogee_km"],
                        perigee_km=parsed["perigee_km"],
                        inclination_deg=parsed["inclination_deg"],
                        period_minutes=parsed["period_minutes"],
                        eccentricity=parsed["eccentricity"],
                        line1=parsed["line1"],
                        line2=parsed["line2"],
                        epoch=parsed["epoch"],
                        updated_at=now,
                    )
                    batch.append(cat_sat)
                    synced_count += 1
            elif norad_id:
                apogee = to_float(get_f("apogee_km", get_f("apogee")))
                perigee = to_float(get_f("perigee_km", get_f("perigee")))
                inc = to_float(get_f("inclination_deg", get_f("inclination")))
                period = to_float(get_f("period_min", get_f("period_minutes", get_f("period"))))
                ecc = to_float(get_f("eccentricity", "0.0001"))

                # Fallback dummy line1/line2 if only metadata is provided
                l1 = line1 or f"1 {norad_id:05d}U {intl_des or '00000A'}   24080.00000000  .00000000  00000-0  00000-0 0  9999"
                l2 = line2 or f"2 {norad_id:05d}  {inc or 0.0:07.4f} 000.0000 {int((ecc or 0.0)*10000000):07d} 000.0000 000.0000 15.00000000000000"

                cat_sat = CatalogSatellite(
                    norad_id=norad_id,
                    name=name or f"OBJECT {norad_id}",
                    international_designator=intl_des,
                    object_type=obj_type.lower(),
                    orbit_regime=regime.upper(),
                    apogee_km=apogee,
                    perigee_km=perigee,
                    inclination_deg=inc,
                    period_minutes=period,
                    eccentricity=ecc,
                    line1=l1,
                    line2=l2,
                    epoch=now,
                    updated_at=now,
                )
                batch.append(cat_sat)
                synced_count += 1

            if len(batch) >= 200:
                for item in batch:
                    await db.merge(item)
                await db.commit()
                print(f"Processed and committed {synced_count:,} / {len(rows):,} satellites...")
                batch = []

        if batch:
            for item in batch:
                await db.merge(item)
            await db.commit()

    print(f"\n[DONE] Successfully imported {synced_count:,} space objects into 'All Satellites' (catalog_satellites)!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import satellite catalog CSV into database")
    parser.add_argument("csv_file", nargs="?", default=None, help="Path to CSV file")
    parser.add_argument("--db-url", default=None, help="PostgreSQL connection string")
    args = parser.parse_args()

    csv_file = args.csv_file
    if not csv_file:
        default_candidates = [
            r"P:\Projects\active_satellites_catalog.csv",
            r"P:\Projects\orbita_iq_1000_active_satellites.csv",
            r"P:\Projects\satellites (1).csv",
        ]
        csv_file = next((c for c in default_candidates if os.path.exists(c)), None)
        if not csv_file:
            print("Usage: python import_catalog_csv.py <path_to_csv_file> [--db-url <url>]")
            sys.exit(1)

    asyncio.run(import_csv_to_catalog(csv_file, db_url=args.db_url))
