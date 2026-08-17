-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0001_auth_schema.sql
-- Scope: Employee ID login, Admin/Operator roles, lockout policy, audit log
-- ============================================================================

create extension if not exists "pgcrypto";

-- ----------------------------------------------------------------------------
-- Enum: user_role
-- ----------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'user_role') then
    create type public.user_role as enum ('admin', 'operator');
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- Table: profiles
-- Extends auth.users (Supabase-managed) with employee identity, role,
-- and login-security metadata. One row per auth.users row.
-- ----------------------------------------------------------------------------
create table if not exists public.profiles (
  id                     uuid primary key references auth.users(id) on delete cascade,
  employee_id            text not null unique,
  email                  text not null,
  full_name              text not null,
  role                   public.user_role not null default 'operator',
  department             text,
  is_active              boolean not null default true,
  failed_login_attempts  integer not null default 0,
  locked_until           timestamptz,
  last_login_at          timestamptz,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);

create unique index if not exists idx_profiles_employee_id on public.profiles (employee_id);
create index if not exists idx_profiles_role on public.profiles (role);

comment on table public.profiles is
  'Extends auth.users with employee identity, role, and login-security metadata.';

-- ----------------------------------------------------------------------------
-- Table: login_audit_log
-- Every login attempt (success or failure) for security monitoring and
-- to drive the lockout policy enforced in the backend AuthService.
-- ----------------------------------------------------------------------------
create table if not exists public.login_audit_log (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references public.profiles(id) on delete set null,
  employee_id  text not null,
  ip_address   text,
  success      boolean not null,
  created_at   timestamptz not null default now()
);

create index if not exists idx_login_audit_employee_id
  on public.login_audit_log (employee_id, created_at desc);

comment on table public.login_audit_log is
  'Audit trail of login attempts for security monitoring and lockout enforcement.';

-- ----------------------------------------------------------------------------
-- updated_at trigger
-- ----------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
  before update on public.profiles
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Sync auth.users -> profiles on signup.
--
-- Admins provision accounts via the Supabase Admin API
-- (supabase.auth.admin.create_user), passing user_metadata:
--   { employee_id, full_name, role, department }
-- This trigger creates the matching profiles row automatically.
-- ----------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, employee_id, email, full_name, role, department)
  values (
    new.id,
    upper(coalesce(new.raw_user_meta_data ->> 'employee_id', 'EMP-' || substr(new.id::text, 1, 8))),
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.email),
    coalesce((new.raw_user_meta_data ->> 'role')::public.user_role, 'operator'),
    new.raw_user_meta_data ->> 'department'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists trg_on_auth_user_created on auth.users;
create trigger trg_on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.login_audit_log enable row level security;

-- Helper: is the current JWT subject an admin?
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

-- profiles: a user can always read their own row
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
  on public.profiles for select
  using (id = auth.uid());

-- profiles: admins can read every row
drop policy if exists "profiles_select_admin_all" on public.profiles;
create policy "profiles_select_admin_all"
  on public.profiles for select
  using (public.is_admin());

-- profiles: a user can update their own row (role/is_active/employee_id
-- changes are blocked separately by the trigger below)
drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
  on public.profiles for update
  using (id = auth.uid())
  with check (id = auth.uid());

-- profiles: admins can manage (insert/update/delete) every row
drop policy if exists "profiles_admin_manage_all" on public.profiles;
create policy "profiles_admin_manage_all"
  on public.profiles for all
  using (public.is_admin())
  with check (public.is_admin());

-- login_audit_log: admins can read; writes go through the service-role
-- client from the backend, which bypasses RLS entirely.
drop policy if exists "login_audit_admin_read" on public.login_audit_log;
create policy "login_audit_admin_read"
  on public.login_audit_log for select
  using (public.is_admin());

-- ----------------------------------------------------------------------------
-- Guard: prevent non-admins from escalating their own privileges via the
-- "update own row" policy above (RLS alone can't restrict specific columns).
-- ----------------------------------------------------------------------------
create or replace function public.prevent_self_privilege_escalation()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if not public.is_admin() then
    if new.role is distinct from old.role
       or new.is_active is distinct from old.is_active
       or new.employee_id is distinct from old.employee_id then
      raise exception 'Insufficient privileges to modify role, active status, or employee ID.';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_prevent_self_privilege_escalation on public.profiles;
create trigger trg_prevent_self_privilege_escalation
  before update on public.profiles
  for each row
  execute function public.prevent_self_privilege_escalation();

-- ----------------------------------------------------------------------------
-- Seeding a first admin (run manually, once):
--
--   1. Create the user via Supabase Admin API / Dashboard so auth.users
--      gets a properly hashed password — never insert into auth.users
--      directly from SQL:
--
--        supabase.auth.admin.create_user({
--          "email": "admin@yourcompany.com",
--          "password": "<temporary-strong-password>",
--          "email_confirm": true,
--          "user_metadata": {
--            "employee_id": "EMP-0001",
--            "full_name": "Primary Administrator",
--            "role": "admin",
--            "department": "Flight Operations"
--          }
--        })
--
--   2. The trg_on_auth_user_created trigger above creates the matching
--      public.profiles row automatically with role = 'admin'.
-- ----------------------------------------------------------------------------
