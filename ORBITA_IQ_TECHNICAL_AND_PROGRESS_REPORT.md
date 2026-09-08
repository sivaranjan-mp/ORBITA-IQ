# ORBITA-IQ: Complete Technical & Progress Report

**Document Version:** 2.0.0  
**Audit Date:** September 7, 2026  
**Git Branch / Commit:** `main` (`a2cd18a` — *fix(alerts): prevent blocking external TLE lookups and eliminate infinite skeleton loading*)  
**Live System:** [orbita-iq.vercel.app](https://orbita-iq.vercel.app)  
**PDF Report:** [ORBITA_IQ_TECHNICAL_PROGRESS_REPORT.pdf](file:///p:/Projects/satellite-ops-dashboard/satellite-ops-auth/ORBITA_IQ_TECHNICAL_PROGRESS_REPORT.pdf)

---

## Executive Summary & Audit Verdict

This report delivers a rigorous, evidence-based technical audit of **ORBITA-IQ**, a cloud-native satellite conjunction-intelligence and flight-dynamics operations platform. 

The audit evaluated both the **pre-existing core system** (catalog ingestion, fleet tracking, SGP4 orbit propagation, SatGuard 2-stage conjunction screening, Foster 1992 probability integration with Hard-Body Radius, and CesiumJS 3D viewer) and the newly designed **Maneuver Candidate Generator Pipeline** across six designated architectural modules.

### Key Audit Findings:
1. **Core System (100% Operational):** The catalog of 5,027 active space objects, automated 5-minute orbit propagation, 20-minute conjunction screening across a 5-day lookahead window, and CesiumJS 3D viewer are fully operational in code, database schema, and live deployment, supported by 105 passing backend unit and integration tests.
2. **Maneuver Modules 1 & 2 (Fully Built & Tested):** Maneuver Candidate Grid Generation (6 RTN directions, variable $\Delta v$ magnitudes, and burn lead times) and Maneuver Propagation (Two-Body + $J_2$ numerical integration via SciPy DOP853, sub-second TCA refinement via Brent minimization, and post-maneuver $P_c$ re-computation) are fully implemented, validated with 16 passing unit tests, and exposed via REST API endpoints (`POST/GET /alerts/{alert_id}/maneuver-candidates`).
3. **Maneuver Module 4 (Partially Built):** Candidate ranking currently computes an efficiency metric ($\text{efficiency} = \Delta\text{miss\_distance} / \Delta v$) and sorts candidates descending. A multi-attribute composite scoring function, rating categories, and `recommended_candidate_id` schema are not yet implemented.
4. **Maneuver Modules 3, 5, and 6 (Not Yet Built / Planned):**
   - **Module 3 (Full-Catalog Re-Screening):** Not implemented; candidates are evaluated only against the alert's primary secondary object.
   - **Module 5 (12-State Operational Lifecycle State Machine):** Not implemented; the database and API currently utilize a basic 6-value status enum (`open`, `monitoring`, `active`, `acknowledged`, `resolved`, `dismissed`).
   - **Module 6 (Two-Person Dual Approval Workflow):** Partially enforced via architectural safety constraints. The AI Assistant is strictly quarantined to read-only qualitative advice with zero database mutation or execution routes. However, dedicated dual-signature approval tables and engineer/approver role separation have not yet been built.
5. **Frontend Integration Gap:** The maneuver candidate generation API endpoints are fully active on the backend but have not yet been connected to interactive UI components in the React dashboard.

---

## 1. System Overview & Deployment Status

### 1.1 Deployment Topology & Live Status

| Component | Platform / Host | Live URL / Endpoint | Deployed Version / Commit | Audit Status & Drift |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend UI** | Vercel (Edge CDN) | `https://orbita-iq.vercel.app` | Commit `a2cd18a` (`main` branch) | **Live & Operational** — Zero drift with `origin/main` |
| **Backend API** | Render (Web Service) | `https://satellite-ops-backend.onrender.com` (`/api/v1/*`) | Python 3.11 / FastAPI 0.115.0 (`render.yaml`) | **Live & Operational** — `autoDeploy: true` on push to `main` |
| **Database & Auth** | Supabase (AWS us-east-1) | PostgreSQL 15 + GoTrue Auth | 19 Migrations (`0001` through `0017`) | **Live & Operational** — RLS active across all tables |
| **3D Orbit Viewer** | CesiumJS WebGL | Static Worker Bundles on CDN | CesiumJS 1.121.1 (`vite-plugin-cesium`) | **Live & Operational** — 3D globe with trajectory scrub |

### 1.2 Tech Stack Verification & Dependency Audit

- **Frontend:** React 18.3.1, TypeScript 5.5.4, Vite 5.4.5, TailwindCSS 3.4.10, Axios 1.7.7, `@supabase/supabase-js` 2.45.4, Recharts 2.12.7, Radix UI Primitives, `date-fns` 4.4.0, Lucide React icons.
- **Backend:** FastAPI 0.115.0, Uvicorn 0.30.6, SQLAlchemy 2.0.52 (AsyncEngine with `asyncpg` 0.31.0), Pydantic 2.9.2, SGP4 2.23, SciPy 1.15.2, NumPy 2.2.3, APScheduler 3.11.0, Anthropic SDK 0.40.0+ / Google Generative AI (Gemini 2.5 Flash), PyJWT 2.9.0, SlowAPI 0.1.9.
- **Schema Discipline Audit:** SQLAlchemy declarative models explicitly specify string-value mapping (`values_callable=lambda x: [e.value for e in x]`) to ensure seamless enum compatibility with PostgreSQL and prevent asyncpg type mismatch regressions.

---

## 2. Core System Audit (Pre-Existing Capabilities)

All pre-existing core capabilities were inspected in the codebase and verified through test execution.

```
+---------------------------------------------------------------------------------------------------+
|                                  ORBITA-IQ CORE PIPELINE                                          |
+---------------------------------------------------------------------------------------------------+
|  [CelesTrak Sync (12h)] --> [Active Catalog (5,027 Sats)]                                         |
|  [Fleet Telemetry/TLE]  --> [Fleet Tracking DB] ----+                                             |
|                                                     |                                             |
|                                                     v                                             |
|                                       [SGP4 Propagation (5 min)]                                  |
|                                                     |                                             |
|                                                     +--> [WebSocket Broadcast (/orbit/ws)]        |
|                                                     |                                             |
|                                                     v                                             |
|                                  [SatGuard Screening (20 min)]                                    |
|                                  - Stage 1: Coarse Band Overlap                                   |
|                                  - Stage 2: 5-Day SGP4 Scan + SciPy Minimization                  |
|                                                     |                                             |
|                                                     v                                             |
|                                    [Conjunction Assessment]                                       |
|                                    - Foster 1992 Pc with Hard-Body Radius                         |
|                                    - Relative State & RIC Decomposition (dR, dI, dC)              |
|                                    - Risk Classification (Critical/High/Med/Low)                  |
|                                                     |                                             |
|                                                     v                                             |
|                                [Conjunction Alerts & History DB]                                  |
|                                                     |                                             |
|                                                     v                                             |
|                                   [CesiumJS 3D Orbit Visualizer]                                  |
+---------------------------------------------------------------------------------------------------+
```

### 2.1 Subsystem Ground-Truth Summary

1. **Catalog Ingestion:** 
   - Master active satellite dataset: `backend/app/data/active_satellites.tle` containing **5,027 active space objects** (15,081 lines of 3-line TLE format).
   - Automated periodic catalog synchronization configured on a 12-hour cadence via APScheduler job `run_catalog_sync_job` (`CatalogService.run_sync_background_job`).
   - Live fallback search against CelesTrak API (`celestrak_service.py`) for on-demand object ingestion.
   - File upload endpoints supporting raw Two-Line Elements (`/satellites/upload-tle`) and CCSDS Orbit Mean-Elements Messages (`/satellites/upload-omm`).

2. **Fleet Tracking & Orbit Quality Assessment:**
   - Active fleet satellites tracked in `satellites` table with associated `tle_records` and `orbit_state` records.
   - Data Quality Scoring Engine (`DataQualityService`): Implements regime-aware freshness scoring (LEO $\le 18\text{h}$, MEO $\le 36\text{h}$, GEO $\le 48\text{h}$, HEO $\le 24\text{h}$), provenance authority scoring (Space-Track/CelesTrak: 100, LeoLabs: 95, Internal OD: 90, User Upload: 60), and covariance availability weighting (0–100 quality score).

3. **Orbit Propagation (5-Minute Cadence):**
   - Registered APScheduler background job: `update_orbit_states` (Job ID: `update_orbit_states_job`) executing on an interval of **5 minutes**.
   - Propagates all active fleet satellites forward to current epoch using SGP4, writes updated Cartesian state vectors to database in a bulk transaction, and broadcasts position updates over WebSockets (`/orbit/ws` via `orbit_manager`).
   - On-demand rate-limited orbit refresh endpoint (`POST /satellites/refresh`) protected by a 60-second cooldown limiter.

4. **Conjunction Screening (SatGuard Engine — 20-Minute Cadence):**
   - Registered APScheduler background job: `run_screening_job` (Job ID: `run_screening_job`) executing on an interval of **20 minutes**.
   - Screening Scope: 5-day (120-hour) lookahead window evaluating Fleet vs. Fleet and Fleet vs. 5,027 Catalog Objects.
   - **Two-Stage Screening Pipeline:**
     - *Stage 1 (Coarse Filter):* Evaluates apogee and perigee altitude bounds ($h_a, h_p$) with an altitude safety margin ($\delta h = 50\text{ km}$). Pairs without overlapping orbital shells are rejected in $O(1)$ operations per pair.
     - *Stage 2 (Fine Propagation & Minimization):* Executes step propagation scan (60-second coarse step) on all Stage 1 survivors. Local minima are refined using 1D scalar bounded optimization (`scipy.optimize.minimize_scalar` with tolerance $10^{-4}$) to resolve exact Time of Closest Approach (TCA) and minimum miss distance.

5. **Risk Classification, HBR, & Relative Geometry:**
   - Collision probability ($P_c$) calculated via Foster (1992) 2D probability density integration (`ProbabilityEngine.calculate_probability`).
   - Integrates explicit Hard-Body Radius (HBR) for both primary and secondary objects (`ProbabilityEngine.resolve_hbr` and `ProbabilityEngine.combine_hbr`).
   - Risk categorization:
     - **Critical:** $P_c \ge 10^{-4}$ or miss distance $\le 500\text{ m}$
     - **High:** $P_c \ge 10^{-5}$ or miss distance $\le 1,500\text{ m}$
     - **Medium:** $P_c \ge 10^{-6}$ or miss distance $\le 5,000\text{ m}$
     - **Low:** $P_c < 10^{-6}$ and miss distance $> 5,000\text{ m}$
   - Relative geometry decomposition (`relative_geometry.py`): Computes relative position $[x,y,z]$, relative velocity $[v_x,v_y,v_z]$, Radial/In-Track/Cross-Track (RIC) separations $(\Delta R, \Delta I, \Delta C)$, relative velocity angle, relative inclination, and encounter classification (`co-orbital`, `crossing`, `head-on`).
   - Audit trail: `alert_status_history` logs operator status changes with timestamps, operator ID, and notes.

6. **CesiumJS 3D Orbit Viewer:**
   - Interactive 3D globe (`OrbitViewerPage.tsx`, `CesiumGlobe.tsx`) rendering WGS84 Earth ellipsoid, satellite ephemeris orbits, real-time positions, sensor field-of-view cones, close approach vectors, and conjunction encounter points.

---

## 3. Maneuver Candidate Generator — Implementation Status per Module

```
+----------------------------------------------------------------------------------------------------+
|                      MANEUVER CANDIDATE GENERATOR PIPELINE STATUS                                  |
+----------------------------------------------------------------------------------------------------+
|  1. Candidate Generation       [ COMPLETE - BACKEND ]  6 RTN directions, delta-v & timing grid     |
|  2. Maneuver Propagation       [ COMPLETE - BACKEND ]  Two-Body + J2 ODE solve_ivp (DOP853) & Pc   |
|  3. Catalog Re-Screening       [ NOT IMPLEMENTED ]     Candidates screened only against secondary  |
|  4. Candidate Ranking          [ PARTIAL - EFFICIENCY] Sorted by miss improvement / delta-v        |
|  5. Lifecycle State Machine    [ NOT IMPLEMENTED ]     Basic 6-state enum, no 12-state machine     |
|  6. Two-Person Approval        [ PARTIAL - AI BARRED ] AI strictly read-only; no dual-sign flow    |
+----------------------------------------------------------------------------------------------------+
```

### Module 1: Candidate Generation (Direction Grid, $\Delta v$ Magnitude, & Burn Timing)
- **Status:** **Fully Implemented in Backend**
- **Code Artifacts:** `backend/app/services/maneuver_candidates.py` (`ManeuverCandidateService`, `build_rtn_frame`, `apply_delta_v`), `backend/app/models/maneuvers.py`, `backend/app/models/enums.py` (`ManeuverDirection`), `backend/app/schemas/maneuvers.py`.
- **Wiring:** Exposed via FastAPI endpoints `POST /api/v1/alerts/{alert_id}/maneuver-candidates` and `GET /api/v1/alerts/{alert_id}/maneuver-candidates`. Writes to `maneuver_candidates` table in PostgreSQL.
- **Unit Tests:** 7 dedicated passing unit tests in `test_maneuver_candidates.py`:
  - `test_build_rtn_frame_equatorial_circular`
  - `test_build_rtn_frame_orthonormality_arbitrary_orbit`
  - `test_build_rtn_frame_degenerate_cases`
  - `test_apply_delta_v_radial_positive`
  - `test_apply_delta_v_radial_negative`
  - `test_apply_delta_v_along_track_directions`
  - `test_apply_delta_v_cross_track_directions`
- **Gaps / Limitations:** Grid parameterization uses discrete fixed values (default 6 magnitudes $\times$ 5 timings $\times$ 6 directions = 180 combinations). No continuous gradient optimization loop.

### Module 2: Maneuver Propagation (RTN Application, Two-Body + $J_2$ Integration, TCA/Pc)
- **Status:** **Fully Implemented in Backend**
- **Code Artifacts:** `backend/app/services/maneuver_candidates.py`:
  - `two_body_j2_dynamics`: ODE defining gravitational acceleration plus Earth's oblateness perturbation $J_2 = 1.08262668 \times 10^{-3}$.
  - `propagate_perturbed_arc`: High-order numerical integrator utilizing `scipy.integrate.solve_ivp` with `DOP853` (8th-order Runge-Kutta Dormand-Prince) and dense output interpolation.
  - `refine_candidate_tca`: Bounded scalar optimization resolving post-burn closest approach against the secondary object's SGP4 trajectory.
  - `ProbabilityEngine.calculate_probability`: Re-computes collision probability $P_c$ post-maneuver.
- **Unit Tests:** 5 dedicated passing unit tests in `test_maneuver_candidates.py`:
  - `test_two_body_j2_dynamics_derivatives`
  - `test_propagate_perturbed_arc_conservation`
  - `test_physics_along_track_prograde_increases_period`
  - `test_maneuver_candidate_generator_synthetic_conjunction`
  - `test_get_saved_candidates_for_alert`
- **Gaps / Limitations:** Force model is restricted to Two-Body + $J_2$. It does not model atmospheric drag (NRLMSISE-00), solar radiation pressure (SRP), or third-body lunar/solar gravity. All burns are modeled as instantaneous impulsive velocity vectors ($\Delta \mathbf{v}$). Covariance is not dynamically propagated via State Transition Matrix (STM) during candidate generation.

### Module 3: Full-Catalog Re-Screening
- **Status:** **NOT IMPLEMENTED**
- **Code Reality:** In `maneuver_candidates.py`, candidates are evaluated *strictly against the secondary object of the conjunction alert*. No function or pipeline exists to re-screen the candidate's perturbed trajectory against the 5,027 catalog satellites or fleet objects.
- **Unit Tests:** 0 tests exist for candidate catalog re-screening.
- **Technical Bottleneck:** Screening 180 candidate trajectories against 5,027 catalog objects creates $180 \times 5,027 = 904,860$ pair arc evaluations. Performing this synchronously in Python would block the API process for minutes. It requires spatial indexing (KD-Tree) and asynchronous Celery/Redis worker offloading.

### Module 4: Candidate Ranking & Rating Labels
- **Status:** **Partially Implemented (Efficiency Metric Only)**
- **Code Reality:** `maneuver_candidates.py` calculates:
  $$\text{efficiency} = \frac{\text{resulting\_miss\_distance\_m} - \text{baseline\_miss\_distance\_m}}{\Delta v\text{ (m/s)}}$$
  Candidates are sorted descending by `(efficiency_m_per_m_s, resulting_miss_distance_m)`.
- **Unit Tests:** Tested in `test_maneuver_candidate_generator_synthetic_conjunction`.
- **Gaps / Limitations:** Multi-attribute composite scoring (incorporating $P_c$ reduction, $\Delta v$ propellant penalty, execution lead-time penalty, and secondary collision margin), qualitative rating labels (`OPTIMAL`, `ACCEPTABLE`, `SUBOPTIMAL`, `DISQUALIFIED`), and an explicit `recommended_candidate_id` response field are not yet implemented.

### Module 5: Conjunction Lifecycle State Machine
- **Status:** **NOT IMPLEMENTED (Basic Status Enum Only)**
- **Code Reality:** The database and API utilize `ConjunctionStatus` (`OPEN`, `MONITORING`, `RESOLVED`, `DISMISSED`) and `AlertState` (`ACTIVE`, `ACKNOWLEDGED`, `RESOLVED`). Status updates are processed via `PUT /alerts/{alert_id}/status`.
- **Gaps / Limitations:** The formal 12-state linear lifecycle (`DETECTED` $\rightarrow$ `SCREENED` $\rightarrow$ `ASSESSED` $\rightarrow$ `CONFIRMED` $\rightarrow$ `ACTION REQUIRED` $\rightarrow$ `MANEUVER ANALYSIS` $\rightarrow$ `APPROVAL` $\rightarrow$ `EXECUTION` $\rightarrow$ `POST-MANEUVER` $\rightarrow$ `VERIFICATION` $\rightarrow$ `CLOSED`) and 5 branch side-states (`FALSE POSITIVE`, `DATA STALE`, `NO ACTION`, `SUPERSEDED`, `COORDINATION REQUIRED`) do not exist in the database enums or state transition guards.

### Module 6: Two-Person Approval Workflow & AI Quarantine
- **Status:** **Partially Implemented (AI Isolation Enforced; Approval Flow Not Built)**
- **AI Assistant Containment (Verified in Code):** The AI Assistant (`AIAdvisoryService`, `ai_assistant.py`) is rigorously isolated. It exposes only read-only qualitative advice (`GET /ai-assistant/advisories`, `POST /ai-assistant/recommend`). Its system prompt explicitly mandates: *"STRICTLY ADVISORY... NOT a certified Flight Dynamics System maneuver solution... NEVER calculate or output exact delta-v..."*. The AI Assistant possesses zero database write routes for alerts, maneuver candidates, or execution.
- **Dual-Signature Workflow (Not Built):** Dedicated `maneuver_approval` tables, dual-signature enforcement (proposer engineer ID $\ne$ approving director ID), and flight-dynamics operational gates are not yet implemented.

---

## 4. Data Model Changes & Migration Audit

All 19 database migrations in `supabase/migrations/` were audited against the SQLAlchemy declarative models in `backend/app/models/`:

| Migration File | Key Entities / Scope | SQLAlchemy Model | Migration Status |
| :--- | :--- | :--- | :--- |
| `0001_auth_schema.sql` | `profiles`, `login_audit_log`, RLS policies, `is_admin()` | Supabase Auth / Profiles | **Applied** |
| `0002_core_schema.sql` | `satellites`, `tle_records`, `omm_records` | `Satellite`, `TLERecord`, `OMMRecord` | **Applied** |
| `0003_conjunctions_schema.sql` | `conjunction_events` | `ConjunctionEvent` | **Applied** |
| `0004_cdm_schema.sql` | `cdm_records` | `CDMRecord` | **Applied** |
| `0005_orbit_state_schema.sql` | `orbit_propagation_cache`, `orbit_states` | `OrbitState` | **Applied** |
| `0006_alerts_schema.sql` | `alerts` | `Alert` | **Applied** |
| `0007 - 0009` | Nullable column updates and orbit state schema fixes | `OrbitState`, `ConjunctionEvent` | **Applied** |
| `0010_catalog_satellites.sql` | `catalog_satellites` master table | `CatalogSatellite` | **Applied** |
| `0011_conjunction_alerts.sql` | `conjunction_alerts` primary operational table | `ConjunctionAlert` | **Applied** |
| `0012_fix_enum_types.sql` | PostgreSQL enum alignment & casting | `enums.py` | **Applied** |
| `0013_ai_advisories.sql` | `ai_maneuver_advisories` cached LLM advice table | `AIManeuverAdvisory` | **Applied** |
| `0014_alert_status_history.sql`| `alert_status_history` audit trail table | `AlertStatusHistory` | **Applied** |
| `0015_astrodynamics_data_model.sql`| `data_sources`, `algorithm_versions`, `oem_records`, `state_vectors`, `covariance_matrices`, `orbit_solutions`, `data_freshness` | `DataSource`, `AlgorithmVersion`, `OEMRecord`, `StateVector`, `CovarianceMatrix`, `OrbitSolution`, `DataFreshness` | **Applied** |
| `0016_data_quality_scoring.sql`| Seeds `DATA_QUALITY_SCORING` algorithm v1.0.0 | Registered in `algorithm_versions` | **Applied** |
| `0017_extend_tca_relative_geometry.sql` | Extends `conjunction_alerts` with relative state $[x,y,z,v_x,v_y,v_z]$, RIC separations $(\Delta R, \Delta I, \Delta C)$, and encounter geometry | Mapped in `ConjunctionAlert` | **Applied** |
| `0017_maneuver_candidates.sql`| Creates `maneuver_direction` enum & `maneuver_candidates` table with RLS policies and indexes | `ManeuverCandidate` | **Applied** |
| `0018 - 0020` (Draft Scopes) | Draft scopes for Covariance STM propagation, 12-state Lifecycle, and Two-Person Approval | Not yet created in codebase | **Pending / Scoped** |

---

## 5. Lifecycle & Approval Workflow Status

### 5.1 Reachable Operational States

In the current live system, conjunction alerts transition across six reachable states:
```
[ OPEN ] <---> [ MONITORING ] <---> [ ACTIVE ] <---> [ ACKNOWLEDGED ] <---> [ RESOLVED / DISMISSED ]
```
Every status update is validated by `PUT /api/v1/alerts/{alert_id}/status` and recorded in `alert_status_history` with the acting operator's user ID, full name, timestamp, and optional remarks.

### 5.2 Role Separation & Safety Enforcement

- **Role Levels:** `admin` (full management and configuration), `operator` (satellite ingestion, alert resolution, screening triggers, maneuver generation), and `viewer` (read-only monitoring).
- **AI Safety Constraints:** Verified in code. The AI Assistant has no execution or update routes, ensuring that all collision avoidance decisions remain exclusively under human operator control.
- **Two-Person Approval Workflow:** Server-side dual-signature validation (enforcing that the operator proposing a maneuver candidate cannot be the approving director) is scoped for Migration `0020_maneuver_approval.sql` and is not yet enforced.

---

## 6. Known Risks & Technical Limitations

1. **Full-Catalog Re-Screening Computational Scaling:**
   - *Risk:* Evaluating 180 maneuver candidates against 5,027 catalog objects yields 904,860 candidate-orbit pair evaluations. Executing this synchronously inside a FastAPI request handler will block the worker process and trigger HTTP 504 gateway timeouts.
   - *Mitigation:* Implement spatial partitioning (3D KD-Tree or apogee/perigee bounding filters) to eliminate $>99.5\%$ of non-conjunction pairs in $O(\log N)$ time, and offload re-screening to asynchronous background workers (Celery/Redis).

2. **Force Model Fidelity & Impulsive Assumption:**
   - *Risk:* The numerical integrator models Earth's gravitational field ($GM$) and second zonal harmonic oblateness ($J_2$). In low Earth orbit ($<600\text{ km}$), unmodeled atmospheric drag causes secular in-track drift over multi-day arcs. Furthermore, maneuvers are modeled as instantaneous velocity impulses rather than finite-duration burns.
   - *Mitigation:* Integrate an exponential atmospheric density model for LEO propagation arcs and document operational execution constraints for low-thrust propulsion systems.

3. **Absence of SGP4 6x6 Covariance:**
   - *Risk:* Public Two-Line Elements do not provide 6x6 state covariance matrices. Collision probability ($P_c$) calculations rely on regime-based default positional covariance scaled by data freshness rather than dynamically propagated covariance.
   - *Mitigation:* Utilize official CCSDS Conjunction Data Messages (CDMs) containing calibrated 6x6 covariance whenever available, falling back to data-quality scaled covariance.

4. **Frontend UI Maneuver Disconnect:**
   - *Risk:* The maneuver candidate generator backend endpoints (`POST/GET /alerts/{alert_id}/maneuver-candidates`) are fully tested and operational, but have not yet been exposed via UI components in the React dashboard.
   - *Mitigation:* Implement a dedicated Maneuver Candidate Drawer and Trade Space table in `frontend/src/components/alerts/`.

---

## 7. Prioritized Next Steps for Operational Readiness

```
+----------------------------------------------------------------------------------------------------+
|                                    PRIORITIZED ROADMAP                                             |
+----------------------------------------------------------------------------------------------------+
|  [P0 - Immediate]   UI Integration of Maneuver Candidate Generator                                 |
|  [P0 - Immediate]   Composite Multi-Attribute Candidate Ranking & Rating Labels                     |
|  [P1 - Core]        Asynchronous Worker & KD-Tree Spatial Indexing for Catalog Re-Screening         |
|  [P1 - Core]        Migration 0019: 12-State Operational Conjunction Lifecycle State Machine       |
|  [P2 - Enterprise]  Migration 0020: Dual-Signature Two-Person Approval Workflow                     |
+----------------------------------------------------------------------------------------------------+
```

### Category A: Immediate UI & Ranking Integration (P0)
1. **Frontend Maneuver Drawer & Trade Space UI:** Build `ManeuverCandidateDialog.tsx` and `useManeuvers.ts` hook connecting the React frontend to `POST/GET /alerts/{alert_id}/maneuver-candidates`. Render candidate trade space scatter plots ($\Delta v$ vs. miss distance improvement), RTN vector breakdowns, and resulting risk classifications.
2. **Composite Candidate Ranking Engine:** Implement multi-objective scoring formula balancing $P_c$ reduction ($w_1=0.40$), $\Delta v$ propellant cost ($w_2=0.30$), burn lead-time margin ($w_3=0.15$), and post-burn clearance ($w_4=0.15$). Add rating labels (`OPTIMAL`, `ACCEPTABLE`, `SUBOPTIMAL`, `DISQUALIFIED`) and expose `recommended_candidate_id` in the API schema.

### Category B: Scaling & Lifecycle State Machine (P1)
3. **Asynchronous Catalog Re-Screening with KD-Tree:** Implement 3D spatial indexing (KD-Tree on orbital element space) to reduce the 904,860 candidate-orbit pair search space, and execute re-screening inside an asynchronous worker queue.
4. **Migration 0019 (Conjunction Lifecycle State Machine):** Create migration `0019_conjunction_event_lifecycle.sql` introducing the 12-state linear lifecycle (`DETECTED` through `CLOSED`) and 5 side-states, backed by server-side transition guard validators.

### Category C: Enterprise Compliance & Approval Workflow (P2)
5. **Migration 0020 (Two-Person Dual Approval):** Create migration `0020_maneuver_approval.sql` introducing `maneuver_approvals` table. Enforce dual-signature role separation (Flight Dynamics Engineer proposal $\ne$ Mission Director approval) with cryptographic audit logging prior to maneuver command export.

---

## Verification Traceability Index

Every finding in this report is traceable to specific source files, test suites, and database artifacts:

- **105 Passing Backend Tests:** `backend/tests/` (`pytest` executed cleanly in 20.48s).
- **Maneuver Candidate Generator (16 Tests):** `backend/tests/test_maneuver_candidates.py` & `backend/app/services/maneuver_candidates.py`.
- **SatGuard Conjunction Engine (4 Tests):** `backend/tests/test_conjunction_engine.py` & `backend/app/services/satguard_service.py`.
- **Foster 1992 Probability & HBR (3 Tests):** `backend/tests/test_probability_engine.py` & `backend/app/services/probability_engine.py`.
- **Relative Geometry & RIC Decomposition (4 Tests):** `backend/tests/test_relative_geometry.py` & `backend/app/services/relative_geometry.py`.
- **AI Advisory Quarantine (8 Tests):** `backend/tests/test_ai_advisory.py` & `backend/app/services/ai_advisory_service.py`.
- **Database Schema & Migrations:** `supabase/migrations/` (19 migration files, `0001` through `0017`).
- **Live Deployments:** Frontend at `https://orbita-iq.vercel.app`, Backend configuration in `render.yaml`.
- **Generated PDF Document:** [ORBITA_IQ_TECHNICAL_PROGRESS_REPORT.pdf](file:///p:/Projects/satellite-ops-dashboard/satellite-ops-auth/ORBITA_IQ_TECHNICAL_PROGRESS_REPORT.pdf).
