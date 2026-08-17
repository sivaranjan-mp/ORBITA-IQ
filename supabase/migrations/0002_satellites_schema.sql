-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0002_satellites_schema.sql
-- Scope: satellites, tle_records, omm_records
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Enum: satellite_status
-- ----------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'satellite_status') then
    create type public.satellite_status as enum ('active', 'degraded', 'inactive', 'decayed');
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- Enum: object_type
-- ----------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'object_type') then
    create type public.object_type as enum ('payload', 'debris', 'rocket_body', 'unknown');
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- Table: satellites
-- ----------------------------------------------------------------------------
create table if not exists public.satellites (
  id                       uuid primary key default gen_random_uuid(),
  norad_id                 integer not null unique,
  name                     text not null,
  international_designator text,
  object_type              public.object_type not null default 'unknown',
  status                   public.satellite_status not null default 'active',
  owner_org                text,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

create index if not exists idx_satellites_norad_id on public.satellites (norad_id);

comment on table public.satellites is
  'Tracked space objects (satellites, debris) and their metadata.';

-- ----------------------------------------------------------------------------
-- Table: tle_records
-- ----------------------------------------------------------------------------
create table if not exists public.tle_records (
  id           uuid primary key default gen_random_uuid(),
  satellite_id uuid not null references public.satellites(id) on delete cascade,
  line1        text not null,
  line2        text not null,
  source       text,
  epoch        timestamptz not null,
  created_at   timestamptz not null default now()
);

create index if not exists idx_tle_records_satellite_id_epoch 
  on public.tle_records (satellite_id, epoch desc);

comment on table public.tle_records is
  'Historical Two-Line Element (TLE) records for tracked objects.';

-- ----------------------------------------------------------------------------
-- Table: omm_records
-- ----------------------------------------------------------------------------
create table if not exists public.omm_records (
  id           uuid primary key default gen_random_uuid(),
  satellite_id uuid not null references public.satellites(id) on delete cascade,
  epoch        timestamptz not null,
  payload      jsonb not null,
  created_at   timestamptz not null default now()
);

create index if not exists idx_omm_records_satellite_id_epoch 
  on public.omm_records (satellite_id, epoch desc);

comment on table public.omm_records is
  'CCSDS Orbit Data Messages (OMM) JSON payloads.';

-- ----------------------------------------------------------------------------
-- updated_at triggers
-- ----------------------------------------------------------------------------
drop trigger if exists trg_satellites_updated_at on public.satellites;
create trigger trg_satellites_updated_at
  before update on public.satellites
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.satellites enable row level security;
alter table public.tle_records enable row level security;
alter table public.omm_records enable row level security;

-- Everybody authenticated can read
drop policy if exists "satellites_read_all" on public.satellites;
create policy "satellites_read_all" on public.satellites for select using (auth.role() = 'authenticated');

drop policy if exists "tle_records_read_all" on public.tle_records;
create policy "tle_records_read_all" on public.tle_records for select using (auth.role() = 'authenticated');

drop policy if exists "omm_records_read_all" on public.omm_records;
create policy "omm_records_read_all" on public.omm_records for select using (auth.role() = 'authenticated');

-- Only admins can insert/update/delete
drop policy if exists "satellites_admin_manage_all" on public.satellites;
create policy "satellites_admin_manage_all" on public.satellites for all using (public.is_admin()) with check (public.is_admin());

drop policy if exists "tle_records_admin_manage_all" on public.tle_records;
create policy "tle_records_admin_manage_all" on public.tle_records for all using (public.is_admin()) with check (public.is_admin());

drop policy if exists "omm_records_admin_manage_all" on public.omm_records;
create policy "omm_records_admin_manage_all" on public.omm_records for all using (public.is_admin()) with check (public.is_admin());
