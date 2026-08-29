import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.session import Base
from app.services.satellite_service import SatelliteService

async def main():
    # Create an in-memory SQLite database for testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # Create all tables (this will create them according to the Python models, 
    # but wait, the Python models HAVE the x_km columns, so it wouldn't fail!)
    # To reproduce the exact failure, we need to create the table WITHOUT x_km
    # just like the production database has it.
    
    async with engine.begin() as conn:
        # Create satellites
        await conn.run_sync(Base.metadata.create_all)
        
        # Now let's drop the x_km columns to simulate production
        try:
            await conn.execute(text("ALTER TABLE orbit_state DROP COLUMN x_km"))
            await conn.execute(text("ALTER TABLE orbit_state DROP COLUMN y_km"))
            await conn.execute(text("ALTER TABLE orbit_state DROP COLUMN z_km"))
            await conn.execute(text("ALTER TABLE orbit_state DROP COLUMN vx_kms"))
            await conn.execute(text("ALTER TABLE orbit_state DROP COLUMN vy_kms"))
            await conn.execute(text("ALTER TABLE orbit_state DROP COLUMN vz_kms"))
        except:
            pass # SQLite ALTER TABLE DROP COLUMN might not be supported depending on version

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as db:
        s = SatelliteService(db)
        try:
            print("Attempting to add NORAD ID 48274...")
            sat = await s.add_satellite_by_norad(48274, 'test')
            print("Success:", sat)
        except Exception as e:
            print("--- TRACEBACK ---")
            import traceback
            traceback.print_exc()
            print("-----------------")

from sqlalchemy import text
if __name__ == "__main__":
    asyncio.run(main())
