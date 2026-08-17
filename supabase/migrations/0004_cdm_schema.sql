-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0004_cdm_schema.sql
-- Scope: cdm_records
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: cdm_records
-- ----------------------------------------------------------------------------
create table if not exists public.cdm_records (
  id                  uuid primary key default gen_random_uuid(),
  primary_norad_id    integer not null,
  secondary_norad_id  integer not null,
  tca                 timestamptz not null,
  payload             jsonb not null,
  created_at          timestamptz not null default now()
);

create index if not exists idx_cdm_records_norad_ids 
  on public.cdm_records (primary_norad_id, secondary_norad_id);

create index if not exists idx_cdm_records_tca 
  on public.cdm_records (tca desc);

comment on table public.cdm_records is
  'CCSDS Conjunction Data Message (CDM) JSON payloads.';

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.cdm_records enable row level security;

-- Everybody authenticated can read
drop policy if exists "cdm_records_read_all" on public.cdm_records;
create policy "cdm_records_read_all" on public.cdm_records for select using (auth.role() = 'authenticated');

-- Only admins can insert/update/delete
drop policy if exists "cdm_records_admin_manage_all" on public.cdm_records;
create policy "cdm_records_admin_manage_all" on public.cdm_records for all using (public.is_admin()) with check (public.is_admin());
