-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0009_orbit_state_nullable.sql
-- Scope: Make latitude_deg, longitude_deg, velocity_km_s nullable in orbit_state
--        table and null out fabricated zeros from failed TLE propagations.
-- ============================================================================

-- 1. Drop NOT NULL constraints
ALTER TABLE public.orbit_state ALTER COLUMN latitude_deg DROP NOT NULL;
ALTER TABLE public.orbit_state ALTER COLUMN longitude_deg DROP NOT NULL;
ALTER TABLE public.orbit_state ALTER COLUMN velocity_km_s DROP NOT NULL;

-- 2. Drop DEFAULT 0 values to ensure unpropagated states default to NULL
ALTER TABLE public.orbit_state ALTER COLUMN latitude_deg DROP DEFAULT;
ALTER TABLE public.orbit_state ALTER COLUMN longitude_deg DROP DEFAULT;
ALTER TABLE public.orbit_state ALTER COLUMN velocity_km_s DROP DEFAULT;

-- ----------------------------------------------------------------------------
-- 3. Data-repair statement:
-- Null out existing fabricated zeros for rows where ALL THREE fields are exactly 0.
-- Note: In production, inspect affected rows before running this UPDATE:
-- SELECT s.norad_id, s.name, o.latitude_deg, o.longitude_deg, o.velocity_km_s
-- FROM public.orbit_state o
-- JOIN public.satellites s ON o.satellite_id = s.id
-- WHERE o.latitude_deg = 0 AND o.longitude_deg = 0 AND o.velocity_km_s = 0;
-- ----------------------------------------------------------------------------
UPDATE public.orbit_state
SET latitude_deg = NULL, longitude_deg = NULL, velocity_km_s = NULL
WHERE latitude_deg = 0 AND longitude_deg = 0 AND velocity_km_s = 0;
