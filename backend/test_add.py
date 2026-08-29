import asyncio
import os
import sys
# Make sure we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import async_session_maker
from app.services.satellite_service import SatelliteService

async def main():
    async with async_session_maker() as db:
        s = SatelliteService(db)
        try:
            sat = await s.add_satellite_by_norad(48274, 'test')
            print("Success:", sat)
        except Exception as e:
            print(f"Failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
