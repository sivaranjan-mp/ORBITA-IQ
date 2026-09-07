-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0017_maneuver_candidates.sql
-- Scope: Maneuver Candidate Generator table and enum for Collision Avoidance Maneuver (CAM) evaluation
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Enum: maneuver_direction
-- ----------------------------------------------------------------------------
do $$ begin
    create type public.maneuver_direction as enum (
        'along_track_earlier',
        'along_track_later',
        'radial_positive',
        'radial_negative',
        'cross_track_positive',
        'cross_track_negative'
    );
exception
    when duplicate_object then null;
end $$;

-- ----------------------------------------------------------------------------
-- Table: maneuver_candidates
-- ----------------------------------------------------------------------------
create table if not exists public.maneuver_candidates (
    id                             uuid primary key default gen_random_uuid(),
    alert_id                       uuid not null references public.conjunction_alerts(id) on delete cascade,
    direction                      public.maneuver_direction not null,
    delta_v_m_s                    double precision not null,
    delta_v_r_m_s                  double precision not null default 0.0,
    delta_v_t_m_s                  double precision not null default 0.0,
    delta_v_n_m_s                  double precision not null default 0.0,
    burn_epoch                     timestamptz not null,
    time_before_tca_hours          double precision not null,
    resulting_tca                  timestamptz not null,
    resulting_miss_distance_m      double precision not null,
    resulting_miss_distance_km     double precision not null,
    resulting_relative_velocity_km_s double precision,
    resulting_probability          double precision not null default 0.0,
    resulting_risk_level           public.risk_level not null default 'low',
    miss_distance_improvement_m    double precision not null,
    risk_level_change              text,
    efficiency_m_per_m_s           double precision not null default 0.0,
    fuel_cost_proxy_m_s            double precision not null,
    created_at                     timestamptz not null default now(),
    updated_at                     timestamptz not null default now()
);

-- Indices for rapid UI queries & filtering
create index if not exists idx_maneuver_candidates_alert_id on public.maneuver_candidates (alert_id);
create index if not exists idx_maneuver_candidates_efficiency on public.maneuver_candidates (alert_id, efficiency_m_per_m_s desc);
create index if not exists idx_maneuver_candidates_burn_epoch on public.maneuver_candidates (burn_epoch);
create index if not exists idx_maneuver_candidates_direction on public.maneuver_candidates (direction);

comment on table public.maneuver_candidates is
  'Generated collision avoidance maneuver candidates with Two-Body + J2 numerical propagation scoring.';

-- ----------------------------------------------------------------------------
-- updated_at trigger
-- ----------------------------------------------------------------------------
drop trigger if exists trg_maneuver_candidates_updated_at on public.maneuver_candidates;
create trigger trg_maneuver_candidates_updated_at
  before update on public.maneuver_candidates
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.maneuver_candidates enable row level security;

-- Everybody authenticated can read
drop policy if exists "maneuver_candidates_read_all" on public.maneuver_candidates;
create policy "maneuver_candidates_read_all"
  on public.maneuver_candidates for select
  using (auth.role() = 'authenticated');

-- Authenticated operators and admins can manage maneuver candidates
drop policy if exists "maneuver_candidates_manage_all" on public.maneuver_candidates;
create policy "maneuver_candidates_manage_all"
  on public.maneuver_candidates for all
  using (auth.role() = 'authenticated')
  with check (auth.role() = 'authenticated');
