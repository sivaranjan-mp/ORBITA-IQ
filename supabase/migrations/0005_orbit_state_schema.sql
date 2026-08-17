-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0005_orbit_state_schema.sql
-- Scope: orbit_state table for caching pre-calculated orbital parameters
-- ============================================================================

create table if not exists public.orbit_state (
  id uuid primary key default gen_random_uuid(),
  satellite_id uuid references public.satellites(id) on delete cascade not null,
  altitude_km numeric not null,
  latitude_deg numeric not null default 0,
  longitude_deg numeric not null default 0,
  velocity_km_s numeric not null default 0,
  inclination_deg numeric not null,
  period_minutes numeric not null,
  eccentricity numeric not null,
  raan_deg numeric not null,
  mean_anomaly_deg numeric not null,
  epoch timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint unique_satellite_orbit_state unique (satellite_id)
);

-- Indices
create index if not exists idx_orbit_state_satellite_id on public.orbit_state (satellite_id);

-- ----------------------------------------------------------------------------
-- updated_at triggers
-- ----------------------------------------------------------------------------
drop trigger if exists trg_orbit_state_updated_at on public.orbit_state;
create trigger trg_orbit_state_updated_at
  before update on public.orbit_state
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.orbit_state enable row level security;

drop policy if exists "orbit_state_read_all" on public.orbit_state;
create policy "orbit_state_read_all" 
  on public.orbit_state for select 
  using (auth.role() = 'authenticated');

drop policy if exists "orbit_state_manage_admin" on public.orbit_state;
create policy "orbit_state_manage_admin" 
  on public.orbit_state for all 
  using (public.is_admin()) 
  with check (public.is_admin());
