-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0008_conjunctions_update.sql
-- Scope: Add missing columns to conjunction_events table
-- ============================================================================

alter table public.conjunction_events 
add column if not exists relative_velocity_km_s numeric;
