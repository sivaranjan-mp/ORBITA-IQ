import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app

def test_dashboard_crash():
    client = TestClient(app, raise_server_exceptions=True)
    
    # We need to mock get_current_user or decode_access_token to simulate a logged-in user
    with patch("app.dependencies.decode_access_token") as mock_decode:
        mock_decode.return_value = {"sub": "123e4567-e89b-12d3-a456-426614174000"}
        
        with patch("app.dependencies.get_admin_client") as mock_admin:
            mock_table = MagicMock()
            mock_select = MagicMock()
            mock_eq = MagicMock()
            mock_maybe_single = MagicMock()
            mock_execute = MagicMock()
            
            mock_admin.return_value.table.return_value = mock_table
            mock_table.select.return_value = mock_select
            mock_select.eq.return_value = mock_eq
            mock_eq.maybe_single.return_value = mock_maybe_single
            mock_maybe_single.execute.return_value = mock_execute
            
            mock_execute.data = {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "employee_id": "EMP-001",
                "full_name": "Test User",
                "role": "admin",
                "department": "Engineering",
                "is_active": True,
                "last_login_at": "2023-01-01T12:00:00+00:00"
            }
            
            # Make a request to the dashboard
            try:
                print("Sending request to /api/v1/dashboard")
                response = client.get("/api/v1/dashboard", headers={"Authorization": "Bearer fake_token"})
                print("Response:", response.status_code, response.json())
            except Exception as e:
                print("CAUGHT EXCEPTION!")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    test_dashboard_crash()
