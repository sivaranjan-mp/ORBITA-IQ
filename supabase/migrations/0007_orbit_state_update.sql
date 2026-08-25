-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0007_orbit_state_update.sql
-- Scope: Add missing ECI state vector columns to orbit_state table
-- ============================================================================

alter table public.orbit_state 
add column if not exists x_km numeric,
add column if not exists y_km numeric,
add column if not exists z_km numeric,
add column if not exists vx_kms numeric,
add column if not exists vy_kms numeric,
add column if not exists vz_kms numeric;
