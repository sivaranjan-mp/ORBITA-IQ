# ORBITA-IQ

# Orbita-IQ — Authentication System

Production-ready authentication module for the Orbita-IQ &
Conjunction Intelligence Dashboard: Employee ID login, Admin/Operator roles,
protected routes, Supabase Auth, password reset, and session persistence.

## How login works

Supabase Auth is email/password native, so employees log in with an
**Employee ID** that the backend transparently resolves to the account's
email before handing the password off to Supabase's own auth engine —
your code never touches or compares raw passwords.

```
Browser                     FastAPI backend                  Supabase
--------                    ----------------                 --------
POST /auth/login       ───▶ look up email by employee_id
{employee_id, password}     (service-role client)
                             │
                             ▼
                        sign_in_with_password(email, password) ───▶ GoTrue
                             │                                       │
                             ◀── access_token / refresh_token ───────┘
◀── {access_token, refresh_token, user}
supabase.auth.setSession(...)   // supabase-js now owns persistence + refresh
```

Password reset and updates go straight from the browser to Supabase
(`resetPasswordForEmail` is triggered via the backend to resolve the
employee ID first; `updateUser({password})` runs client-side once the
user lands on `/reset-password` from their email).

## Project layout

```
satellite-ops-auth/
├── backend/            FastAPI auth service
├── frontend/            React + TS + Vite + Tailwind + shadcn/ui
└── supabase/migrations/ SQL schema (profiles, roles, RLS, lockout, audit log)
```

## Setup

### 1. Supabase project

1. Create a project at supabase.com.
2. Run `supabase/migrations/0001_auth_schema.sql` in the SQL editor.
3. Copy Project Settings → API: `Project URL`, `anon public` key,
   `service_role` key, and `JWT Secret`.
4. Create your first admin via the Admin API (see comment at the bottom
   of the migration file) with `user_metadata.role = "admin"`.

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Supabase values
uvicorn app.main:app --reload
```

Runs at `http://localhost:8000`. Interactive docs at `/docs`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # fill in VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY
npm run dev
```

Runs at `http://localhost:5173`.

## Security features included

- Passwords are never seen or stored by this codebase — verification is
  delegated entirely to Supabase GoTrue.
- Account lockout after N consecutive failed attempts (configurable),
  tracked in `login_audit_log`.
- Enumeration-resistant login and password-reset responses (generic
  messages regardless of whether the Employee ID exists).
- Row Level Security on `profiles`, with a trigger blocking self
  role/employee_id/active-status escalation even though users can update
  their own row.
- JWTs verified locally against the Supabase JWT secret (no network round
  trip per request); role is re-checked server-side on every protected
  API call via `require_role(...)`, never trusted from the client alone.
- Rate limiting on `/auth/login` and `/auth/password-reset/request`.
