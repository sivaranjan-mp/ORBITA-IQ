-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0013_ai_advisories.sql
-- Scope: AI Maneuver Advisories caching table for conjunction alerts
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: ai_maneuver_advisories
-- ----------------------------------------------------------------------------
create table if not exists public.ai_maneuver_advisories (
    id                  uuid primary key default gen_random_uuid(),
    alert_id            uuid not null references public.conjunction_alerts(id) on delete cascade,
    satellite_norad_id  integer not null,
    recommendation_data jsonb not null,
    model_used          text not null default 'claude-3-5-haiku-20241022',
    prompt_tokens       integer,
    completion_tokens   integer,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    constraint uq_ai_advisories_alert_id unique (alert_id)
);

-- Indices for rapid lookup by alert_id and satellite_norad_id
create index if not exists idx_ai_advisories_alert_id on public.ai_maneuver_advisories (alert_id);
create index if not exists idx_ai_advisories_sat_norad on public.ai_maneuver_advisories (satellite_norad_id);

comment on table public.ai_maneuver_advisories is
  'Cached LLM-generated qualitative collision avoidance advisories for conjunction alerts.';

-- ----------------------------------------------------------------------------
-- updated_at trigger
-- ----------------------------------------------------------------------------
drop trigger if exists trg_ai_maneuver_advisories_updated_at on public.ai_maneuver_advisories;
create trigger trg_ai_maneuver_advisories_updated_at
  before update on public.ai_maneuver_advisories
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.ai_maneuver_advisories enable row level security;

-- Read policy: All authenticated users can read cached advisories
drop policy if exists "ai_maneuver_advisories_read_all" on public.ai_maneuver_advisories;
create policy "ai_maneuver_advisories_read_all"
  on public.ai_maneuver_advisories
  for select
  using (auth.role() = 'authenticated');

-- Write policy: Restricted strictly to service_role or authenticated operators/admins
drop policy if exists "ai_maneuver_advisories_write_restricted" on public.ai_maneuver_advisories;
drop policy if exists "ai_maneuver_advisories_manage_all" on public.ai_maneuver_advisories;
create policy "ai_maneuver_advisories_write_restricted"
  on public.ai_maneuver_advisories
  for all
  using (
    auth.role() = 'service_role'
    or (
      auth.role() = 'authenticated'
      and exists (
        select 1 from public.profiles
        where id = auth.uid() and role in ('admin', 'operator')
      )
    )
  )
  with check (
    auth.role() = 'service_role'
    or (
      auth.role() = 'authenticated'
      and exists (
        select 1 from public.profiles
        where id = auth.uid() and role in ('admin', 'operator')
      )
    )
  );
