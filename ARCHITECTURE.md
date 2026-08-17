# Satellite Operations & Conjunction Intelligence Dashboard — Architecture Reference

This document is the system-level reference for the whole project. The
`backend/`, `frontend/`, and `supabase/` folders in this zip are the
**implemented** slice of it (Authentication + the Mission Control
Dashboard shell). Everything else below (satellite CRUD, TLE/OMM/CDM
ingestion, SGP4 propagation, SatGuard screening) is the target
architecture those modules are designed to slot into — the frontend's
data hooks (`src/hooks/useSatellites.ts`, `useAlerts.ts`) and the
backend's service-layer pattern are already shaped for it.

## What's implemented in this zip

- **Authentication** (`backend/app/api/v1/endpoints/auth.py`,
  `frontend/src/context/AuthContext.tsx`): Employee ID login, Admin/Operator
  roles, protected routes, Supabase Auth, password reset, session
  persistence, account lockout, audit logging.
- **Mission Control Dashboard** (`frontend/src/pages/`): Dashboard, My
  Satellites, Alerts, Orbit Viewer (real CesiumJS globe), Settings —
  currently backed by a typed mock data layer (`frontend/src/mock/`) ready
  to be swapped for live API calls.

## Target folder structure (full system)

```
satellite-ops-dashboard/
├── apps/
│   ├── frontend/                                # React + TS + Vite
│   │   ├── src/
│   │   │   ├── components/{ui,layout,auth,satellites,uploads,
│   │   │   │   monitoring,conjunctions,collision-probability,orbit-viewer,shared}/
│   │   │   ├── features/{auth,satellites,tle-omm-cdm,conjunctions,
│   │   │   │   collision-probability,orbit-visualization}/
│   │   │   ├── hooks/ lib/ pages/ routes/ store/ types/ utils/
│   │   │   └── App.tsx main.tsx
│   │   └── vite.config.ts
│   └── backend/                                  # FastAPI + Python
│       ├── app/
│       │   ├── api/v1/endpoints/{auth,users,satellites,tle,omm,cdm,
│       │   │   conjunctions,collision_probability,monitoring,orbit,admin}.py
│       │   ├── core/ services/{celestrak_service,sgp4_service,
│       │   │   satguard_service,conjunction_engine,probability_engine,
│       │   │   tle_parser,omm_parser,cdm_parser}.py
│       │   ├── models/ schemas/ repositories/ workers/ websockets/
│       │   └── main.py
│       └── requirements.txt
├── infra/{docker-compose.yml, supabase/, k8s/}
└── .github/workflows/
```

## Target database schema (Supabase PostgreSQL)

| Table | Purpose |
|---|---|
| `profiles` | Extends `auth.users`: employee_id, role (admin/operator), lockout fields |
| `satellites` | Tracked objects: NORAD ID, name, type, owner, status |
| `tle_records` | TLE line1/line2 history per satellite, source, epoch |
| `omm_records` | Full CCSDS OMM payload + parsed orbital elements |
| `cdm_records` | Full CCSDS Conjunction Data Message payload |
| `conjunction_events` | Derived events: TCA, miss distance, risk level, status |
| `collision_probability_results` | Pc by method (Foster/Alfano/Patera/SatGuard) |
| `orbit_propagation_cache` | Cached SGP4 state-vector time series |
| `alerts` | Notification records tied to conjunction events |
| `audit_logs` | System-wide audit trail |
| `sync_jobs` | CelesTrak sync job scheduling/history |
| `login_audit_log` | **Implemented** — login attempt audit trail |

Full DDL for the implemented tables (`profiles`, `login_audit_log`) is in
`supabase/migrations/0001_auth_schema.sql`.

## Target API surface (FastAPI, prefix `/api/v1`)

| Group | Endpoints | Status |
|---|---|---|
| Auth | `/auth/login`, `/refresh`, `/logout`, `/me`, `/password-reset/request` | ✅ Implemented |
| Users | `/users` (CRUD, admin) | Not yet implemented |
| Satellites | `/satellites` (CRUD + add-by-NORAD-ID) | Not yet implemented |
| TLE / OMM | `/satellites/{id}/tle`, `/satellites/{id}/omm` (+ `/upload`) | Not yet implemented |
| CDM | `/cdm`, `/cdm/upload` | Not yet implemented |
| Monitoring | `/monitoring/dashboard-summary`, `/monitoring/satellites` | Not yet implemented |
| Conjunctions | `/conjunctions`, `/conjunctions/{id}`, `/{id}/status` | Not yet implemented |
| Collision Probability | `/collision-probability/compute`, `/{event_id}` | Not yet implemented |
| Orbit | `/orbit/{id}/propagate`, `/state-vector`, `/ground-track` | Not yet implemented |
| Alerts | `/alerts`, `/alerts/{id}/acknowledge` | Not yet implemented |
| Admin | `/admin/sync/celestrak`, `/admin/audit-logs` | Not yet implemented |

## Target component tree (frontend)

```
App
├── AuthProvider                          ✅ Implemented
├── Router
│   ├── LoginPage / ForgotPasswordPage / ResetPasswordPage   ✅ Implemented
│   └── ProtectedRoute → MissionControlLayout                ✅ Implemented
│       ├── Sidebar / Topbar / MissionClock                  ✅ Implemented
│       ├── DashboardPage (5 KPI cards, trend chart, feed)   ✅ Implemented
│       ├── MySatellitesPage (table, Add-by-NORAD-ID dialog) ✅ Implemented (UI; mock data)
│       ├── AlertsPage (filterable table, detail dialog)     ✅ Implemented (UI; mock data)
│       ├── OrbitViewerPage (real CesiumJS globe)             ✅ Implemented (simplified propagation)
│       └── SettingsPage (Profile / Notifications / Security) ✅ Implemented
```

See `frontend/README.md`-equivalent notes inline in each hook
(`useSatellites`, `useAlerts`) for exactly what to change when the real
`/satellites` and `/conjunctions` endpoints are built.
