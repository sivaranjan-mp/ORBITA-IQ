-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0010_catalog_satellites.sql
-- Scope: Global Space Catalog objects table, indexes, and RLS policies
-- ============================================================================

create table if not exists public.catalog_satellites (
  norad_id                 integer primary key,
  name                     text not null,
  international_designator text,
  object_type              text default 'payload',
  orbit_regime             text default 'LEO',
  apogee_km                double precision,
  perigee_km               double precision,
  inclination_deg          double precision,
  period_minutes           double precision,
  eccentricity             double precision,
  line1                    text not null,
  line2                    text not null,
  epoch                    timestamptz not null,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

create index if not exists idx_catalog_satellites_norad_id on public.catalog_satellites (norad_id);
create index if not exists idx_catalog_satellites_name on public.catalog_satellites (name);
create index if not exists idx_catalog_satellites_intl_des on public.catalog_satellites (international_designator);
create index if not exists idx_catalog_satellites_regime on public.catalog_satellites (orbit_regime);
create index if not exists idx_catalog_satellites_object_type on public.catalog_satellites (object_type);

comment on table public.catalog_satellites is
  'Global space catalog of satellites, debris, and rocket bodies for ownership-agnostic conjunction screening.';

-- Row Level Security
alter table public.catalog_satellites enable row level security;

-- Read policy: Any authenticated or anon query can read catalog items
drop policy if exists "catalog_satellites_read_all" on public.catalog_satellites;
create policy "catalog_satellites_read_all" on public.catalog_satellites for select using (true);

-- Write policy: Allow backend service role / admin to insert & update catalog records
drop policy if exists "catalog_satellites_write_all" on public.catalog_satellites;
create policy "catalog_satellites_write_all" on public.catalog_satellites for all using (true) with check (true);
