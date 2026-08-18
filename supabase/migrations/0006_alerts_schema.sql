-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0006_alerts_schema.sql
-- Scope: Alerts and Alert History
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Enum: alert_state
-- ----------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'alert_state') then
    create type public.alert_state as enum ('active', 'acknowledged', 'resolved');
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- Table: alerts
-- ----------------------------------------------------------------------------
create table if not exists public.alerts (
    id uuid primary key default gen_random_uuid(),
    conjunction_event_id uuid not null references public.conjunction_events(id) on delete cascade,
    satellite_a_id uuid not null references public.satellites(id) on delete cascade,
    satellite_b_id uuid references public.satellites(id) on delete cascade,
    miss_distance double precision not null,
    relative_velocity double precision,
    time_of_closest_approach timestamptz not null,
    risk_level public.risk_level not null,
    status public.alert_state not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_alerts_satellite_a_id_tca on public.alerts (satellite_a_id, time_of_closest_approach desc);

-- ----------------------------------------------------------------------------
-- Table: alert_history
-- ----------------------------------------------------------------------------
create table if not exists public.alert_history (
    id uuid primary key default gen_random_uuid(),
    alert_id uuid not null references public.alerts(id) on delete cascade,
    risk_level public.risk_level not null,
    miss_distance double precision not null,
    relative_velocity double precision,
    timestamp timestamptz not null default now()
);

create index if not exists idx_alert_history_alert_id_timestamp on public.alert_history (alert_id, timestamp desc);

-- ----------------------------------------------------------------------------
-- updated_at triggers
-- ----------------------------------------------------------------------------
drop trigger if exists trg_alerts_updated_at on public.alerts;
create trigger trg_alerts_updated_at
  before update on public.alerts
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.alerts enable row level security;
alter table public.alert_history enable row level security;

-- Everybody authenticated can read
create policy "alerts_read_all" on public.alerts for select using (auth.role() = 'authenticated');
create policy "alert_history_read_all" on public.alert_history for select using (auth.role() = 'authenticated');

-- Only admins can manage (insert/update/delete)
create policy "alerts_admin_manage_all" on public.alerts for all using (public.is_admin()) with check (public.is_admin());
create policy "alert_history_admin_manage_all" on public.alert_history for all using (public.is_admin()) with check (public.is_admin());
