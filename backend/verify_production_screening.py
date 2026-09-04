import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.session import DATABASE_URL as DEFAULT_DB_URL, Base
from app.services.satguard_service import SatguardService
from app.db.schema_check import verify_schema


async def run_live_verification(target_url: str):
    print("==================================================================")
    print("ORBITA IQ: DATABASE & SCREENING VERIFICATION SUITE")
    print("==================================================================")
    
    # Normalize URL scheme
    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif target_url.startswith("postgresql://") and not target_url.startswith("postgresql+asyncpg://"):
        target_url = target_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Sanitize for logging
    sanitized_url = target_url
    if "@" in sanitized_url:
        proto_user, host_db = sanitized_url.split("@", 1)
        if ":" in proto_user:
            proto = proto_user.split("://")[0]
            user = proto_user.split("://")[1].split(":")[0]
            sanitized_url = f"{proto}://{user}:****@{host_db}"
    print(f"Target Database URL: {sanitized_url}")

    engine = create_async_engine(target_url, echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Startup Schema Check (Read-Only)
    print("\n--- 1. Schema Validation & Enum Inspection (Read-Only) ---")
    try:
        check_result = await verify_schema(engine)
        print(f"Schema Check Status: {check_result}")
    except Exception as e:
        print(f"Schema check error: {e}")

    # 2. Inspect Column Types directly
    print("\n--- 2. Direct Column Type Inspection (information_schema) ---")
    try:
        async with session_maker() as session:
            inspect_query = text("""
                SELECT table_name, column_name, data_type, udt_name
                FROM information_schema.columns 
                WHERE table_name IN ('satellites', 'conjunction_events', 'conjunction_alerts', 'alerts')
                  AND column_name IN ('status', 'object_type', 'risk_level')
                ORDER BY table_name, column_name;
            """)
            res = await session.execute(inspect_query)
            rows = res.fetchall()
            if rows:
                print(f"{'TABLE':<22} | {'COLUMN':<15} | {'DATA TYPE':<15} | {'UDT NAME':<18}")
                print("-" * 75)
                for r in rows:
                    print(f"{r[0]:<22} | {r[1]:<15} | {r[2]:<15} | {r[3]:<18}")
            else:
                print("No matching information_schema records found (or table not created yet).")
    except Exception as e:
        print(f"Column inspection note: {e}")

    # 3. Test Live Satguard Conjunction Screening Execution
    print("\n--- 3. Testing Satguard Screening Execution (/api/v1/alerts/screen) ---")
    try:
        async with session_maker() as session:
            service = SatguardService(session)
            t0 = time.time()
            metrics = await service.screen_all(lookahead_hours=120.0, step_size_s=60, miss_dist_threshold_km=50.0)
            t1 = time.time()
            print("Screening completed successfully!")
            print(f"Total Duration:         {t1 - t0:.3f} s")
            print(f"Events Created:         {metrics.get('events_created', 0)}")
            print(f"Fleet vs Fleet Pairs:   {metrics.get('fleet_vs_fleet_pairs', 0):,}")
            print(f"Fleet vs Catalog Pairs: {metrics.get('fleet_vs_catalog_pairs', 0):,}")
            print(f"Stage 1 Survivors:      {metrics.get('stage1_survivors', 0):,}")
            print(f"Stage 2 Scanned Pairs:  {metrics.get('stage2_scanned_pairs', 0):,}")
    except Exception as e:
        print(f"\n[FAILED] Screening execution note: {e}")
        import traceback
        traceback.print_exc()

    await engine.dispose()
    print("\n==================================================================")
    print("Verification execution finished.")
    print("==================================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify database schema and conjunction screening.")
    parser.add_argument("--db-url", type=str, default=None, help="Target PostgreSQL database URL")
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL") or DEFAULT_DB_URL
    asyncio.run(run_live_verification(db_url))
