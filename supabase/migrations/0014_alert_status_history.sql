-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0014_alert_status_history.sql
-- Scope: Conjunction Alert Status History table for audit trail & operator action tracking
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: alert_status_history
-- ----------------------------------------------------------------------------
create table if not exists public.alert_status_history (
    id                 uuid primary key default gen_random_uuid(),
    alert_id           uuid not null references public.conjunction_alerts(id) on delete cascade,
    previous_status    public.alert_status not null,
    new_status         public.alert_status not null,
    changed_by         uuid references public.profiles(id) on delete set null,
    changed_at         timestamptz not null default now(),
    notes              text
);

-- Indices for rapid query & ordering
create index if not exists idx_alert_status_history_alert_id on public.alert_status_history (alert_id, changed_at desc);
create index if not exists idx_alert_status_history_changed_at on public.alert_status_history (changed_at desc);
create index if not exists idx_alert_status_history_changed_by on public.alert_status_history (changed_by);

comment on table public.alert_status_history is
  'Audit log of status changes and operator actions on conjunction alerts (Monitoring, Resolved, Dismissed).';

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.alert_status_history enable row level security;

-- Everybody authenticated can read
drop policy if exists "alert_status_history_read_all" on public.alert_status_history;
create policy "alert_status_history_read_all"
  on public.alert_status_history for select
  using (auth.role() = 'authenticated');

-- Authenticated operators and admins can insert / manage history
drop policy if exists "alert_status_history_manage_all" on public.alert_status_history;
create policy "alert_status_history_manage_all"
  on public.alert_status_history for all
  using (auth.role() = 'authenticated')
  with check (auth.role() = 'authenticated');
