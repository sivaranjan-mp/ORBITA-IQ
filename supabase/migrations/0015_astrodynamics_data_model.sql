-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0015_astrodynamics_data_model.sql
-- Scope: Core Astrodynamics Data Model Extensions:
--        data_sources, algorithm_versions, state_vectors, covariance_matrices,
--        orbit_solutions, oem_records, data_freshness, and cdm_records extensions.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Table: data_sources
-- Reference registry for external data feeds, internal integrators, and upload sources.
-- ----------------------------------------------------------------------------
create table if not exists public.data_sources (
    id                  uuid primary key default gen_random_uuid(),
    code                text unique not null,
    name                text not null,
    category            text not null, -- 'EXTERNAL_CATALOG', 'INTERNAL_PROPAGATION', 'OBSERVATION_SENSOR', 'OPERATOR_EPHEMERIS'
    is_authoritative    boolean not null default false,
    description         text,
    api_endpoint        text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index if not exists idx_data_sources_code on public.data_sources (code);
create index if not exists idx_data_sources_category on public.data_sources (category);

comment on table public.data_sources is
  'Master reference table identifying data origins (CelesTrak, Space-Track, LeoLabs, internal engines, operator uploads).';

-- ----------------------------------------------------------------------------
-- 2. Table: algorithm_versions
-- Provenance registry of astrodynamics algorithms, versions, and configuration sets.
-- ----------------------------------------------------------------------------
create table if not exists public.algorithm_versions (
    id                  uuid primary key default gen_random_uuid(),
    name                text not null,
    version             text not null,
    author              text,
    description         text,
    parameters          jsonb not null default '{}'::jsonb,
    is_active           boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    constraint uq_algorithm_name_version unique (name, version)
);

create index if not exists idx_algorithm_versions_name on public.algorithm_versions (name);
create index if not exists idx_algorithm_versions_active on public.algorithm_versions (is_active);

comment on table public.algorithm_versions is
  'Versioned registry of propagation, conjunction screening, and Pc calculation algorithms for mathematical provenance.';

-- ----------------------------------------------------------------------------
-- 3. Table: oem_records
-- CCSDS Orbit Ephemeris Message (OEM) header and metadata.
-- ----------------------------------------------------------------------------
create table if not exists public.oem_records (
    id                      uuid primary key default gen_random_uuid(),
    satellite_id            uuid references public.satellites(id) on delete set null,
    norad_id                integer,
    object_name             text not null,
    object_id               text not null, -- International designator / COSPAR
    originator              text not null,
    message_id              text,
    start_time              timestamptz not null,
    stop_time               timestamptz not null,
    interpolation_method    text default 'HERMITE',
    interpolation_degree    integer default 7,
    reference_frame         text not null default 'ECI_J2000',
    time_system             text not null default 'UTC',
    source_id               uuid references public.data_sources(id) on delete set null,
    raw_metadata            jsonb,
    created_at              timestamptz not null default now()
);

create index if not exists idx_oem_records_sat_time on public.oem_records (satellite_id, start_time, stop_time);
create index if not exists idx_oem_records_norad_time on public.oem_records (norad_id, start_time, stop_time);
create index if not exists idx_oem_records_source on public.oem_records (source_id);

comment on table public.oem_records is
  'CCSDS Orbit Ephemeris Message header metadata. Ephemeris data points link directly to state_vectors.';

-- ----------------------------------------------------------------------------
-- 4. Table: state_vectors
-- Normalized raw Cartesian position/velocity states at specific epochs.
-- ----------------------------------------------------------------------------
create table if not exists public.state_vectors (
    id                  uuid primary key default gen_random_uuid(),
    satellite_id        uuid references public.satellites(id) on delete set null,
    norad_id            integer,
    epoch               timestamptz not null,
    reference_frame     text not null default 'TEME', -- 'TEME', 'ECI_J2000', 'ECI_GCRF', 'ECEF_ITRF', 'RTN'
    x_km                double precision not null,
    y_km                double precision not null,
    z_km                double precision not null,
    vx_kms              double precision not null,
    vy_kms              double precision not null,
    vz_kms              double precision not null,
    source_id           uuid references public.data_sources(id) on delete set null,
    oem_record_id       uuid references public.oem_records(id) on delete cascade,
    sequence_idx        integer,
    entity_tag          text, -- 'orbit_solution', 'oem_point', 'cdm_primary', 'cdm_secondary', 'manual'
    created_at          timestamptz not null default now()
);

create index if not exists idx_state_vectors_satellite_epoch on public.state_vectors (satellite_id, epoch desc);
create index if not exists idx_state_vectors_norad_epoch on public.state_vectors (norad_id, epoch desc);
create index if not exists idx_state_vectors_epoch on public.state_vectors (epoch desc);
create index if not exists idx_state_vectors_oem_seq on public.state_vectors (oem_record_id, sequence_idx);
create index if not exists idx_state_vectors_source on public.state_vectors (source_id);

comment on table public.state_vectors is
  'Universal Cartesian position/velocity vectors referenced by orbit solutions, OEM ephemeris trajectories, and CDMs.';

-- ----------------------------------------------------------------------------
-- 5. Table: covariance_matrices
-- High-precision uncertainty associated with state vectors for Pc computations.
-- ----------------------------------------------------------------------------
create table if not exists public.covariance_matrices (
    id                  uuid primary key default gen_random_uuid(),
    state_vector_id     uuid references public.state_vectors(id) on delete cascade,
    reference_frame     text not null default 'RTN', -- 'RTN', 'ECI_J2000', 'TEME', 'EFG'
    
    -- Position-Position Covariance (km^2)
    cx_x                double precision not null,
    cx_y                double precision not null default 0.0,
    cx_z                double precision not null default 0.0,
    cy_y                double precision not null,
    cy_z                double precision not null default 0.0,
    cz_z                double precision not null,
    
    -- Position-Velocity Cross-Terms (km^2/s)
    cx_vx               double precision default 0.0,
    cx_vy               double precision default 0.0,
    cx_vz               double precision default 0.0,
    cy_vx               double precision default 0.0,
    cy_vy               double precision default 0.0,
    cy_vz               double precision default 0.0,
    cz_vx               double precision default 0.0,
    cz_vy               double precision default 0.0,
    cz_vz               double precision default 0.0,
    
    -- Velocity-Velocity Covariance ((km/s)^2)
    cvx_vx              double precision default 0.0,
    cvx_vy              double precision default 0.0,
    cvx_vz              double precision default 0.0,
    cvy_vy              double precision default 0.0,
    cvy_vz              double precision default 0.0,
    cvz_vz              double precision default 0.0,
    
    raw_matrix          jsonb,
    created_at          timestamptz not null default now()
);

create index if not exists idx_covariance_matrices_state_vector on public.covariance_matrices (state_vector_id);

comment on table public.covariance_matrices is
  '6x6 upper-triangular covariance matrices with explicit reference frame for collision probability calculation.';

-- ----------------------------------------------------------------------------
-- 6. Table: orbit_solutions
-- Historical time-series orbit determination outputs and fit quality metadata.
-- ----------------------------------------------------------------------------
create table if not exists public.orbit_solutions (
    id                      uuid primary key default gen_random_uuid(),
    satellite_id            uuid references public.satellites(id) on delete set null,
    norad_id                integer not null,
    epoch                   timestamptz not null,
    solution_type           text not null default 'SGP4_TLE', -- 'SGP4_TLE', 'NUMERICAL_OD', 'EPHEMERIS_INTERPOLATION', 'SPECIAL_PERTURBATIONS'
    state_vector_id         uuid references public.state_vectors(id) on delete set null,
    covariance_matrix_id    uuid references public.covariance_matrices(id) on delete set null,
    source_id               uuid references public.data_sources(id) on delete set null,
    algorithm_version_id    uuid references public.algorithm_versions(id) on delete set null,
    
    -- Solution quality / OD fit metadata
    fit_span_hours          double precision,
    observations_used       integer,
    observations_available  integer,
    weighted_rms            double precision,
    residuals_summary       jsonb,
    
    -- Keplerian representation summary for fast filtering
    semi_major_axis_km      double precision,
    eccentricity            double precision,
    inclination_deg         double precision,
    raan_deg                double precision,
    arg_of_perigee_deg      double precision,
    mean_anomaly_deg        double precision,
    period_minutes          double precision,
    bstar                   double precision,
    
    created_at              timestamptz not null default now()
);

create index if not exists idx_orbit_solutions_sat_epoch on public.orbit_solutions (satellite_id, epoch desc);
create index if not exists idx_orbit_solutions_norad_epoch on public.orbit_solutions (norad_id, epoch desc);
create index if not exists idx_orbit_solutions_state_vec on public.orbit_solutions (state_vector_id);
create index if not exists idx_orbit_solutions_cov_mat on public.orbit_solutions (covariance_matrix_id);
create index if not exists idx_orbit_solutions_source on public.orbit_solutions (source_id);
create index if not exists idx_orbit_solutions_alg on public.orbit_solutions (algorithm_version_id);

comment on table public.orbit_solutions is
  'Historical time-series of orbit determinations, propagation fits, and quality residuals per satellite.';

-- ----------------------------------------------------------------------------
-- 7. Table: data_freshness
-- Per-source and per-entity sync tracking, staleness monitoring, and heartbeat status.
-- ----------------------------------------------------------------------------
create table if not exists public.data_freshness (
    id                          uuid primary key default gen_random_uuid(),
    source_id                   uuid not null references public.data_sources(id) on delete cascade,
    entity_type                 text not null, -- 'catalog_satellites', 'tle_records', 'fleet_orbit_state', 'cdm_records'
    entity_id                   uuid,
    norad_id                    integer,
    last_attempt_at             timestamptz not null default now(),
    last_success_at             timestamptz,
    latest_data_epoch           timestamptz,
    staleness_threshold_hours   double precision not null default 24.0,
    sync_status                 text not null default 'healthy', -- 'healthy', 'stale', 'failing', 'syncing'
    records_synced              integer default 0,
    error_message               text,
    updated_at                  timestamptz not null default now()
);

create index if not exists idx_data_freshness_source_entity on public.data_freshness (source_id, entity_type);
create index if not exists idx_data_freshness_norad on public.data_freshness (norad_id);
create index if not exists idx_data_freshness_status on public.data_freshness (sync_status);

comment on table public.data_freshness is
  'Catalog and telemetry sync health monitoring, timestamps, and staleness detection.';

-- ----------------------------------------------------------------------------
-- 8. Additive Extensions to Existing Tables (Nullable Columns Only)
-- ----------------------------------------------------------------------------

-- A. satellites: link to primary authoritative data source
alter table public.satellites
    add column if not exists source_id uuid references public.data_sources(id) on delete set null;

create index if not exists idx_satellites_source_id on public.satellites (source_id);

-- B. tle_records: link to data source
alter table public.tle_records
    add column if not exists source_id uuid references public.data_sources(id) on delete set null;

create index if not exists idx_tle_records_source_id on public.tle_records (source_id);

-- C. omm_records: link to data source
alter table public.omm_records
    add column if not exists source_id uuid references public.data_sources(id) on delete set null;

create index if not exists idx_omm_records_source_id on public.omm_records (source_id);

-- D. catalog_satellites: link to data source
alter table public.catalog_satellites
    add column if not exists source_id uuid references public.data_sources(id) on delete set null;

create index if not exists idx_catalog_satellites_source_id on public.catalog_satellites (source_id);

-- E. conjunction_events: link to generating algorithm version
alter table public.conjunction_events
    add column if not exists algorithm_version_id uuid references public.algorithm_versions(id) on delete set null;

create index if not exists idx_conjunction_events_alg_id on public.conjunction_events (algorithm_version_id);

-- F. conjunction_alerts: link to generating algorithm version
alter table public.conjunction_alerts
    add column if not exists algorithm_version_id uuid references public.algorithm_versions(id) on delete set null;

create index if not exists idx_conjunction_alerts_alg_id on public.conjunction_alerts (algorithm_version_id);

-- G. cdm_records: extend with state vectors, covariances, metadata, and data sources
alter table public.cdm_records
    add column if not exists message_id text,
    add column if not exists originator text,
    add column if not exists emergency_reportable boolean default false,
    add column if not exists primary_state_vector_id uuid references public.state_vectors(id) on delete set null,
    add column if not exists secondary_state_vector_id uuid references public.state_vectors(id) on delete set null,
    add column if not exists primary_covariance_matrix_id uuid references public.covariance_matrices(id) on delete set null,
    add column if not exists secondary_covariance_matrix_id uuid references public.covariance_matrices(id) on delete set null,
    add column if not exists miss_distance_m double precision,
    add column if not exists relative_speed_km_s double precision,
    add column if not exists collision_probability double precision,
    add column if not exists source_id uuid references public.data_sources(id) on delete set null,
    add column if not exists algorithm_version_id uuid references public.algorithm_versions(id) on delete set null;

create index if not exists idx_cdm_records_pri_state on public.cdm_records (primary_state_vector_id);
create index if not exists idx_cdm_records_sec_state on public.cdm_records (secondary_state_vector_id);
create index if not exists idx_cdm_records_pri_cov on public.cdm_records (primary_covariance_matrix_id);
create index if not exists idx_cdm_records_sec_cov on public.cdm_records (secondary_covariance_matrix_id);
create index if not exists idx_cdm_records_source on public.cdm_records (source_id);
create index if not exists idx_cdm_records_alg on public.cdm_records (algorithm_version_id);

-- ----------------------------------------------------------------------------
-- 9. Triggers: updated_at
-- ----------------------------------------------------------------------------
drop trigger if exists trg_data_sources_updated_at on public.data_sources;
create trigger trg_data_sources_updated_at
  before update on public.data_sources
  for each row
  execute function public.set_updated_at();

drop trigger if exists trg_algorithm_versions_updated_at on public.algorithm_versions;
create trigger trg_algorithm_versions_updated_at
  before update on public.algorithm_versions
  for each row
  execute function public.set_updated_at();

drop trigger if exists trg_data_freshness_updated_at on public.data_freshness;
create trigger trg_data_freshness_updated_at
  before update on public.data_freshness
  for each row
  execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 10. Seed Baseline Data (Idempotent)
-- ----------------------------------------------------------------------------
insert into public.data_sources (code, name, category, is_authoritative, description)
values
    ('CELESTRAK', 'CelesTrak', 'EXTERNAL_CATALOG', true, 'Public GP/TLE catalog source maintained by Dr. T.S. Kelso'),
    ('SPACE_TRACK', 'Space-Track.org (18th SDS)', 'EXTERNAL_CATALOG', true, 'US Space Force 18th Space Defense Squadron catalog & CDM feed'),
    ('INTERNAL_SGP4', 'Orbita-IQ SatGuard SGP4', 'INTERNAL_PROPAGATION', false, 'Internal analytical SGP4 ephemeris propagation engine'),
    ('INTERNAL_OD', 'Orbita-IQ Numerical OD Engine', 'INTERNAL_PROPAGATION', false, 'Internal numerical orbit determination & integrator'),
    ('USER_UPLOAD', 'Manual Operator Upload', 'OPERATOR_EPHEMERIS', false, 'Direct telemetry/CDM upload via operator UI'),
    ('LEOLABS', 'LeoLabs Radar Network', 'OBSERVATION_SENSOR', true, 'Commercial radar tracking data provider')
on conflict (code) do nothing;

insert into public.algorithm_versions (name, version, author, description, parameters)
values
    ('SATGUARD_SGP4', '1.0.0', 'SatGuard Core', 'Standard SGP4 analytical propagation with WGS84 constants', '{"step_seconds": 60, "gravity_model": "wgs84"}'::jsonb),
    ('ASYMMETRIC_SCREENING', '1.0.0', 'SatGuard Core', 'Two-stage asymmetric ellipsoidal filtering and TCA fine refinement', '{"lookahead_hours": 120, "coarse_step_seconds": 120, "fine_step_seconds": 5, "miss_dist_threshold_km": 50.0}'::jsonb),
    ('FOSTER_PC_2D', '1.0.0', 'NASA CARA / Foster', '2D probability of collision calculation in the B-plane encountering frame', '{"integration_method": "foster_1992"}'::jsonb)
on conflict (name, version) do nothing;

-- ----------------------------------------------------------------------------
-- 11. Row Level Security (RLS) Policies
-- ----------------------------------------------------------------------------
alter table public.data_sources enable row level security;
alter table public.algorithm_versions enable row level security;
alter table public.oem_records enable row level security;
alter table public.state_vectors enable row level security;
alter table public.covariance_matrices enable row level security;
alter table public.orbit_solutions enable row level security;
alter table public.data_freshness enable row level security;

-- 11.1 data_sources Policies
drop policy if exists "data_sources_read_all" on public.data_sources;
create policy "data_sources_read_all"
    on public.data_sources
    for select
    using (auth.role() = 'authenticated');

drop policy if exists "data_sources_write_restricted" on public.data_sources;
create policy "data_sources_write_restricted"
    on public.data_sources
    for all
    using (
        auth.role() = 'service_role'
        or (auth.role() = 'authenticated' and public.is_admin())
    )
    with check (
        auth.role() = 'service_role'
        or (auth.role() = 'authenticated' and public.is_admin())
    );

-- 11.2 algorithm_versions Policies
drop policy if exists "algorithm_versions_read_all" on public.algorithm_versions;
create policy "algorithm_versions_read_all"
    on public.algorithm_versions
    for select
    using (auth.role() = 'authenticated');

drop policy if exists "algorithm_versions_write_restricted" on public.algorithm_versions;
create policy "algorithm_versions_write_restricted"
    on public.algorithm_versions
    for all
    using (
        auth.role() = 'service_role'
        or (auth.role() = 'authenticated' and public.is_admin())
    )
    with check (
        auth.role() = 'service_role'
        or (auth.role() = 'authenticated' and public.is_admin())
    );

-- 11.3 oem_records Policies
drop policy if exists "oem_records_read_all" on public.oem_records;
create policy "oem_records_read_all"
    on public.oem_records
    for select
    using (auth.role() = 'authenticated');

drop policy if exists "oem_records_write_restricted" on public.oem_records;
create policy "oem_records_write_restricted"
    on public.oem_records
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

-- 11.4 state_vectors Policies
drop policy if exists "state_vectors_read_all" on public.state_vectors;
create policy "state_vectors_read_all"
    on public.state_vectors
    for select
    using (auth.role() = 'authenticated');

drop policy if exists "state_vectors_write_restricted" on public.state_vectors;
create policy "state_vectors_write_restricted"
    on public.state_vectors
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

-- 11.5 covariance_matrices Policies
drop policy if exists "covariance_matrices_read_all" on public.covariance_matrices;
create policy "covariance_matrices_read_all"
    on public.covariance_matrices
    for select
    using (auth.role() = 'authenticated');

drop policy if exists "covariance_matrices_write_restricted" on public.covariance_matrices;
create policy "covariance_matrices_write_restricted"
    on public.covariance_matrices
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

-- 11.6 orbit_solutions Policies
drop policy if exists "orbit_solutions_read_all" on public.orbit_solutions;
create policy "orbit_solutions_read_all"
    on public.orbit_solutions
    for select
    using (auth.role() = 'authenticated');

drop policy if exists "orbit_solutions_write_restricted" on public.orbit_solutions;
create policy "orbit_solutions_write_restricted"
    on public.orbit_solutions
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

-- 11.7 data_freshness Policies
drop policy if exists "data_freshness_read_all" on public.data_freshness;
create policy "data_freshness_read_all"
    on public.data_freshness
    for select
    using (auth.role() = 'authenticated');

drop policy if exists "data_freshness_write_restricted" on public.data_freshness;
create policy "data_freshness_write_restricted"
    on public.data_freshness
    for all
    using (
        auth.role() = 'service_role'
        or (auth.role() = 'authenticated' and public.is_admin())
    )
    with check (
        auth.role() = 'service_role'
        or (auth.role() = 'authenticated' and public.is_admin())
    );

COMMIT;
