-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0011_conjunction_alerts.sql
-- Scope: Conjunction Alerts table (single source of truth for screening alerts)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: conjunction_alerts
-- ----------------------------------------------------------------------------
create table if not exists public.conjunction_alerts (
    id                     uuid primary key default gen_random_uuid(),
    satellite_a_norad_id   integer not null,
    satellite_a_name       text not null,
    satellite_b_norad_id   integer not null,
    satellite_b_name       text not null,
    satellite_a_id         uuid references public.satellites(id) on delete cascade,
    satellite_b_id         uuid references public.satellites(id) on delete set null,
    screening_scope        text not null default 'fleet_vs_catalog', -- 'fleet_vs_fleet' | 'fleet_vs_catalog'
    tca                    timestamptz not null,
    miss_distance_km       double precision not null,
    miss_distance_m        double precision not null,
    relative_velocity_km_s double precision,
    probability            double precision not null default 0.0,
    risk_level             public.risk_level not null default 'low',
    status                 public.alert_status not null default 'open',
    detected_by            text not null default 'satguard',
    computed_at            timestamptz not null default now(),
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now()
);

-- Indices for rapid UI queries & filtering
create index if not exists idx_conjunction_alerts_tca on public.conjunction_alerts (tca asc);
create index if not exists idx_conjunction_alerts_status_risk on public.conjunction_alerts (status, risk_level);
create index if not exists idx_conjunction_alerts_sat_a_norad on public.conjunction_alerts (satellite_a_norad_id);
create index if not exists idx_conjunction_alerts_sat_b_norad on public.conjunction_alerts (satellite_b_norad_id);
create index if not exists idx_conjunction_alerts_scope on public.conjunction_alerts (screening_scope);

comment on table public.conjunction_alerts is
  'Canonical single source of truth table for conjunction screening alerts across fleet and space catalog.';

-- ----------------------------------------------------------------------------
-- updated_at trigger
-- ----------------------------------------------------------------------------
drop trigger if exists trg_conjunction_alerts_updated_at on public.conjunction_alerts;
create trigger trg_conjunction_alerts_updated_at
  before update on public.conjunction_alerts
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.conjunction_alerts enable row level security;

-- Everybody authenticated can read
drop policy if exists "conjunction_alerts_read_all" on public.conjunction_alerts;
create policy "conjunction_alerts_read_all"
  on public.conjunction_alerts for select
  using (auth.role() = 'authenticated');

-- Authenticated operators and admins can manage alerts (acknowledge, resolve)
drop policy if exists "conjunction_alerts_manage_all" on public.conjunction_alerts;
create policy "conjunction_alerts_manage_all"
  on public.conjunction_alerts for all
  using (auth.role() = 'authenticated')
  with check (auth.role() = 'authenticated');
