import os
import sys
import argparse
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

def create_admin_user(email: str, password: str, employee_id: str, full_name: str, department: str = "Flight Operations"):
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_role_key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in your .env file.")
        sys.exit(1)

    supabase: Client = create_client(supabase_url, service_role_key)

    print(f"Creating admin user: {email} (Employee ID: {employee_id})...")

    try:
        # Use Supabase Admin API to create user with admin metadata
        res = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "employee_id": employee_id.upper(),
                "full_name": full_name,
                "role": "admin",
                "department": department
            }
        })
        
        user_id = res.user.id
        print(f"✅ Successfully created user in auth.users (ID: {user_id})")

        # Explicitly ensure profiles table has role='admin'
        supabase.table("profiles").upsert({
            "id": user_id,
            "employee_id": employee_id.upper(),
            "email": email,
            "full_name": full_name,
            "role": "admin",
            "department": department,
            "is_active": True
        }).execute()

        print(f"✅ Successfully provisioned Admin profile for {full_name} ({employee_id.upper()})!")
        print(f"\nLogin credentials:")
        print(f" - Employee ID: {employee_id.upper()}")
        print(f" - Email: {email}")
        print(f" - Role: admin")

    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Create or provision an Orbita - IQ Admin User")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--password", required=True, help="User login password")
    parser.add_argument("--emp-id", required=True, help="Employee ID (e.g., EMP-0001)")
    parser.add_argument("--name", default="System Administrator", help="Full name")
    parser.add_argument("--dept", default="Flight Operations", help="Department")

    args = parser.parse_args()
    create_admin_user(args.email, args.password, args.emp_id, args.name, args.dept)

if __name__ == "__main__":
    main()
