export type UserRole = "admin" | "operator";

export interface UserProfile {
  id: string;
  employee_id: string;
  full_name: string;
  role: UserRole;
  department: string | null;
  is_active: boolean;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  expires_at: number;
  token_type: string;
  user: UserProfile;
}

export interface LoginPayload {
  employee_id: string;
  password: string;
}

export interface PasswordResetPayload {
  employee_id: string;
}
