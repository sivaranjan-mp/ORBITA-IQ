import asyncio
import os
import sys

# Add the app directory to the python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.db.session import async_session_maker
from app.services.satellite_service import SatelliteService

NORAD_IDS = [
    25544, 48274, 20580, 25994, 27424, 28376, 25338, 28654, 33591, 43013, 
    54234, 37849, 25682, 39084, 49260, 39634, 40697, 42063, 41335, 43437, 
    42969, 46984, 54754, 36508, 35986, 38771, 43689, 29108, 29107, 28908, 
    28909, 39159, 41783, 44387, 51656
]

# We use EMP-0042 as the default owner_org, but you can change this to match your actual employee ID
OWNER_ORG = "EMP-0042"

async def main():
    async with async_session_maker() as session:
        service = SatelliteService(session)
        print(f"Adding {len(NORAD_IDS)} satellites for owner {OWNER_ORG}...")
        
        for norad_id in NORAD_IDS:
            try:
                # Add the satellite and fetch its data from CelesTrak
                sat = await service.add_satellite_by_norad(norad_id, owner_org=OWNER_ORG)
                print(f"[\u2713] Successfully added NORAD {norad_id}: {sat.name}")
            except ValueError as e:
                # Usually means satellite already exists
                print(f"[-] Skipped NORAD {norad_id}: {e}")
            except Exception as e:
                print(f"[X] Failed to add NORAD {norad_id}: {e}")
                
        print("\nFinished processing all satellites!")

if __name__ == "__main__":
    asyncio.run(main())
