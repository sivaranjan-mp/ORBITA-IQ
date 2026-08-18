-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0002_core_schema.sql
-- Scope: Satellites, Orbit State, Conjunction Events, Alerts
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: satellites
-- ----------------------------------------------------------------------------
create table if not exists public.satellites (
    id uuid primary key default gen_random_uuid(),
    norad_id integer unique not null,
    name text not null,
    international_designator text,
    object_type text default 'payload',
    status text default 'active',
    owner_org text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_satellites_norad_id on public.satellites (norad_id);

-- ----------------------------------------------------------------------------
-- Table: orbit_state
-- ----------------------------------------------------------------------------
create table if not exists public.orbit_state (
    id uuid primary key default gen_random_uuid(),
    satellite_id uuid not null unique references public.satellites(id) on delete cascade,
    altitude_km double precision not null,
    latitude_deg double precision not null default 0,
    longitude_deg double precision not null default 0,
    velocity_km_s double precision not null default 0,
    inclination_deg double precision not null,
    period_minutes double precision not null,
    eccentricity double precision not null,
    raan_deg double precision not null,
    mean_anomaly_deg double precision not null,
    epoch timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- Table: tle_records
-- ----------------------------------------------------------------------------
create table if not exists public.tle_records (
    id uuid primary key default gen_random_uuid(),
    satellite_id uuid not null references public.satellites(id) on delete cascade,
    line1 text not null,
    line2 text not null,
    source text default 'celestrak',
    epoch timestamptz not null,
    created_at timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- Table: omm_records
-- ----------------------------------------------------------------------------
create table if not exists public.omm_records (
    id uuid primary key default gen_random_uuid(),
    satellite_id uuid not null references public.satellites(id) on delete cascade,
    epoch timestamptz,
    payload text not null,
    created_at timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- Table: conjunction_events
-- ----------------------------------------------------------------------------
create table if not exists public.conjunction_events (
    id uuid primary key default gen_random_uuid(),
    primary_satellite text not null,
    primary_norad_id integer not null,
    secondary_object text not null,
    secondary_norad_id integer not null,
    tca timestamptz not null,
    miss_distance_m double precision not null,
    probability double precision not null,
    risk_level text not null,
    status text default 'open',
    detected_by text not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_conjunction_events_tca on public.conjunction_events (tca);

-- ----------------------------------------------------------------------------
-- updated_at triggers
-- ----------------------------------------------------------------------------
drop trigger if exists trg_satellites_updated_at on public.satellites;
create trigger trg_satellites_updated_at
  before update on public.satellites
  for each row
  execute function public.set_updated_at();

drop trigger if exists trg_orbit_state_updated_at on public.orbit_state;
create trigger trg_orbit_state_updated_at
  before update on public.orbit_state
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.satellites enable row level security;
alter table public.orbit_state enable row level security;
alter table public.tle_records enable row level security;
alter table public.omm_records enable row level security;
alter table public.conjunction_events enable row level security;

-- Policies
create policy "satellites_read_all" on public.satellites for select using (true);
create policy "satellites_write_admin" on public.satellites for all using (public.is_admin());

create policy "orbit_state_read_all" on public.orbit_state for select using (true);
create policy "orbit_state_write_admin" on public.orbit_state for all using (public.is_admin());

create policy "tle_records_read_all" on public.tle_records for select using (true);
create policy "tle_records_write_admin" on public.tle_records for all using (public.is_admin());

create policy "omm_records_read_all" on public.omm_records for select using (true);
create policy "omm_records_write_admin" on public.omm_records for all using (public.is_admin());

create policy "conjunction_events_read_all" on public.conjunction_events for select using (true);
create policy "conjunction_events_write_admin" on public.conjunction_events for all using (public.is_admin());
