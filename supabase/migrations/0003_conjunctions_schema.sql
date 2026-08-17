-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0003_conjunctions_schema.sql
-- Scope: conjunction_events table and enum types
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Enum: risk_level
-- ----------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'risk_level') then
    create type public.risk_level as enum ('low', 'medium', 'high', 'critical');
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- Enum: alert_status
-- ----------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'alert_status') then
    create type public.alert_status as enum ('open', 'monitoring', 'resolved', 'dismissed');
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- Table: conjunction_events
-- ----------------------------------------------------------------------------
create table if not exists public.conjunction_events (
  id                  uuid primary key default gen_random_uuid(),
  primary_satellite   text not null,
  primary_norad_id    integer not null,
  secondary_object    text not null,
  secondary_norad_id  integer not null,
  tca                 timestamptz not null,
  miss_distance_m     numeric not null,
  probability         numeric not null,
  risk_level          public.risk_level not null default 'low',
  status              public.alert_status not null default 'open',
  detected_by         text not null default 'satguard',
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index if not exists idx_conjunction_events_tca 
  on public.conjunction_events (tca desc);

create index if not exists idx_conjunction_events_status 
  on public.conjunction_events (status);

comment on table public.conjunction_events is
  'Records of conjunctions and their calculated risks to power the alerts dashboard.';

-- ----------------------------------------------------------------------------
-- updated_at triggers
-- ----------------------------------------------------------------------------
drop trigger if exists trg_conjunction_events_updated_at on public.conjunction_events;
create trigger trg_conjunction_events_updated_at
  before update on public.conjunction_events
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.conjunction_events enable row level security;

-- Everybody authenticated can read
drop policy if exists "conjunction_events_read_all" on public.conjunction_events;
create policy "conjunction_events_read_all" 
  on public.conjunction_events for select 
  using (auth.role() = 'authenticated');

-- Both admins and operators can manage (acknowledge/dismiss) alerts
drop policy if exists "conjunction_events_manage_all" on public.conjunction_events;
create policy "conjunction_events_manage_all" 
  on public.conjunction_events for all 
  using (auth.role() = 'authenticated') 
  with check (auth.role() = 'authenticated');
