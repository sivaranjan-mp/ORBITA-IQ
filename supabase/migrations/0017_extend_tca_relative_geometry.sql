-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0014_extend_tca_relative_geometry.sql
-- Scope: Add relative state, RIC decomposition, and encounter geometry to conjunction_alerts
-- ============================================================================

alter table if exists public.conjunction_alerts
    add column if not exists relative_position_x double precision,
    add column if not exists relative_position_y double precision,
    add column if not exists relative_position_z double precision,
    add column if not exists relative_velocity_x double precision,
    add column if not exists relative_velocity_y double precision,
    add column if not exists relative_velocity_z double precision,
    add column if not exists radial_separation_km double precision,
    add column if not exists along_track_separation_km double precision,
    add column if not exists cross_track_separation_km double precision,
    add column if not exists relative_velocity_angle_deg double precision,
    add column if not exists relative_inclination_deg double precision,
    add column if not exists encounter_geometry text;

comment on column public.conjunction_alerts.radial_separation_km is 'Relative separation along primary radial vector (km)';
comment on column public.conjunction_alerts.along_track_separation_km is 'Relative separation along primary in-track vector (km)';
comment on column public.conjunction_alerts.cross_track_separation_km is 'Relative separation along primary cross-track/normal vector (km)';
comment on column public.conjunction_alerts.encounter_geometry is 'Encounter classification: co-orbital, crossing, or head-on';
