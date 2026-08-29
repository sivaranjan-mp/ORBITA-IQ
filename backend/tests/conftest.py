import os

# Set dummy environment variables before any application code is imported
# This allows pydantic BaseSettings to initialize without failing during test collection
os.environ["SUPABASE_URL"] = "http://localhost:8000"
os.environ["SUPABASE_ANON_KEY"] = "dummy.anon.key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "dummy.service.key"
os.environ["SUPABASE_JWT_SECRET"] = "dummy_jwt_secret_for_testing_purposes"
