from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Role = Literal["admin", "operator"]


class LoginRequest(BaseModel):
    employee_id: str = Field(..., min_length=3, max_length=32, examples=["EMP-0042"])
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("employee_id")
    @classmethod
    def normalize_employee_id(cls, v: str) -> str:
        return v.strip().upper()


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserProfile(BaseModel):
    id: str
    employee_id: str
    full_name: str
    role: Role
    department: str | None = None
    is_active: bool
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    expires_at: int
    token_type: str = "bearer"
    user: UserProfile


class PasswordResetRequest(BaseModel):
    employee_id: str = Field(..., min_length=3, max_length=32)

    @field_validator("employee_id")
    @classmethod
    def normalize_employee_id(cls, v: str) -> str:
        return v.strip().upper()


class MessageResponse(BaseModel):
    message: str
