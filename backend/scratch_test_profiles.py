import asyncio
import os
from pprint import pprint
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.supabase_client import get_admin_client
from app.schemas.auth import UserProfile
from app.dependencies import PROFILE_COLUMNS

async def main():
    admin = get_admin_client()
    result = admin.table("profiles").select(PROFILE_COLUMNS).execute()
    
    print("Found", len(result.data), "profiles")
    for row in result.data:
        print("ROW:", row)
        try:
            profile = UserProfile(**row)
            print("Successfully parsed profile:", profile)
        except Exception as e:
            print("ERROR parsing profile:")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
