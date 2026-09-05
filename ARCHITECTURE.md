# Orbita - IQ — Technical & Architecture Report

**Ground Operations · Conjunction Intelligence Dashboard**  
**Live deployment:** `orbita-iq.vercel.app`

---

## 1. Project Overview

Orbita - IQ is a satellite operations and conjunction-intelligence dashboard built for a ground-ops-style workflow: track a fleet of satellites, screen them for close approaches against both each other and the broader tracked object catalog, and surface actionable risk alerts to an operator — modeled loosely on real-world Conjunction Data Message (CDM) screening as performed by organizations like the 18th Space Defense Squadron.

The system covers the full loop: catalog ingestion → fleet tracking → orbit propagation → conjunction screening → risk classification → alerting → operator review, plus a 3D visualization layer and an LLM-assisted advisory tool for qualitative review.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS |
| **Frontend Hosting** | Vercel |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy (async, `asyncpg` driver) |
| **Backend Hosting** | Render (Web Service) |
| **Database / Auth** | Supabase (PostgreSQL, Auth, Realtime) |
| **Orbit Propagation** | SGP4/SDP4 (via `python-sgp4`, vectorized with NumPy) |
| **Scheduling** | APScheduler (`AsyncIOScheduler`) |
| **Numerics** | NumPy, SciPy (`scipy.optimize.minimize_scalar` for TCA refinement) |
| **3D Visualization** | CesiumJS |
| **Live Updates** | Supabase Realtime subscriptions + dedicated `/ws/orbit` WebSocket, with short-interval polling fallback |
| **External Data** | CelesTrak (TLE/catalog source) |

The frontend and backend are deployed and scaled independently — Vercel serves the static SPA build, and all API/data calls go directly to the Render-hosted FastAPI service rather than being proxied through Vercel.

---

## 3. Data Model

Core tables in the Supabase Postgres database:

- **`satellites`** — The tracked fleet ("My Satellites"). Includes NORAD ID, name, international designator, object type, status, owning organization, and orbital state.
- **`catalog_satellites`** — The global object catalog (~5,000+ objects spanning payloads, debris, and rocket bodies across LEO/MEO/GEO/HEO), searchable and filterable by regime and object type.
- **`tle_records`** — Stored two-line element sets backing SGP4 propagation for every tracked and cataloged object.
- **`orbit_state`** — Current propagated position/velocity per satellite, refreshed on a schedule and pushed to clients in real time.
- **`conjunction_alerts` / `conjunction_events`** — Single source of truth for screening results: satellite pair, scope, time of closest approach (TCA), miss distance, relative velocity, collision probability, risk level, and alert status.
- **`profiles`** — Operator identity (employee ID, name, role, department), backed by Supabase Auth.

Several fields use native Postgres enum types rather than plain strings — `satellite_status`, `object_type`, `risk_level`, `alert_status`, and `alert_state` — enforced at the schema level.

---

## 4. Core Features

- **Dashboard** — Fleet-wide summary: tracked satellite count, active alert count, high-risk alert count, next upcoming conjunction, a fleet altitude trend panel, and a live conjunction feed.
- **My Satellites** — The operator's tracked fleet (611 satellites in the current dataset), each with live altitude, latitude, longitude, velocity, and status, refreshed via scheduled SGP4 propagation.
- **All Satellites (Global Space Catalog)** — Full catalog (~5,028 objects), filterable by orbital regime (LEO/MEO/GEO/HEO) and object type (Payloads/Debris/Rocket Bodies), searchable by name/NORAD ID/COSPAR ID, paginated, with a "Sync Catalog" action to refresh from CelesTrak and per-object "Track" actions to add objects to the fleet.
- **Alerts** — Conjunction Data Message-style screening results, sorted by time of closest approach, filterable by risk level (Critical/High/Medium/Low) and by scope (Fleet vs. Fleet / Fleet vs. Catalog), with a detail view showing miss distance, relative velocity, collision probability, and operator status controls (Monitor/Resolve).
- **Orbit Viewer** — A CesiumJS-based 3D digital twin showing the tracked fleet's real-time positions and orbital paths, with imagery layer options, time-warp controls (1x–60x), and a live/global fleet toggle.
- **AI Assistant** — An LLM-driven layer for qualitative conjunction analysis and maneuver advisory generation, explicitly scoped as decision support rather than a certified flight dynamics tool — advisories are generated per-event and cached for operator review.
- **Settings** — Operator profile, notification thresholds, and security preferences.

---

## 5. Conjunction Screening Engine

This is the technical core of Orbita - IQ. Screening runs across two scopes — **Fleet vs. Fleet** and **Fleet vs. Catalog** — over a rolling **5-day (120-hour)** look-ahead window, using a two-stage pipeline:

1. **Stage 1 — Coarse Orbital Filter**: For every candidate pair, perigee/apogee altitude ranges (with a safety margin) are checked for overlap. Pairs whose orbits geometrically cannot intersect are discarded before propagation. This eliminates >99% of raw pairs in practice.
2. **Stage 2 — Vectorized Ephemeris Propagation**: For every unique satellite appearing in a surviving pair, a full 5-day position trajectory is precomputed once via vectorized SGP4. Relative distance between each surviving pair is then computed across the whole window as a single NumPy array operation, with the true time of closest approach refined via numerical optimization (`scipy.optimize.minimize_scalar`) once a local minimum is located. This keeps per-pair scan cost to a fraction of a millisecond.

### Risk Classification (by Miss Distance)

| Miss Distance | Risk Level | Active Operator Alert? |
|---|---|---|
| `< 1 km` | **Critical** | Yes |
| `1–5 km` | **High** | Yes |
| `5–25 km` | **Medium** | Stored / Visible in Table |
| `25–50 km` | **Low** | Stored / Visible in Table |
| `> 50 km` | Not reported | No |

Collision probability ($P_c$) is additionally computed per event for the detail view.

### Scheduled Jobs

- **Orbit Propagation:** Every 5 minutes, updates live fleet positions.
- **Conjunction Screening:** Every 20 minutes, full Fleet-vs-Fleet and Fleet-vs-Catalog pass.
- **Catalog Sync:** Every 12 hours, refreshes TLEs from CelesTrak.

---

## 6. Real-Time Data Flow

```
                     ┌──────────────────────┐
                     │  conjunction_alerts  │  (single source of truth)
                     └──────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
GET /api/v1/dashboard   GET /api/v1/alerts       Supabase Realtime
 - Active Alerts         - Filtered/sorted rows    - live push to clients
 - High Risk Alerts      - Status updates          - 20s polling fallback
 - Next Conjunction      - Horizon/TCA badges
```

Live orbit positions follow a dedicated path: the scheduled propagation job updates `orbit_state` and broadcasts over `/ws/orbit` WebSocket channel, consumed by both the My Satellites table and the Orbit Viewer 3D scene.

---

## 7. Deployment Architecture

```
 Vercel (React/Vite SPA)  ──HTTP──▶  Render (FastAPI)  ──asyncpg──▶  Supabase (Postgres)
                                          │                              │
                                          ├── APScheduler jobs           ├── Auth
                                          └── /ws/orbit WebSocket        └── Realtime
                                          
 CelesTrak ──(catalog sync job)──▶ Render (FastAPI) ──▶ Supabase (catalog_satellites)
```

---

## 8. Notable Engineering Considerations

- **Schema/Migration Discipline:** Column types (particularly native Postgres enums) stay in sync between SQLAlchemy models and the database via Alembic migrations, utilizing deploy-time schema validation.
- **SGP4 Accuracy over 5-Day Window:** Propagation error grows with time since epoch, prioritized with a 12-hour CelesTrak TLE sync cadence.
- **Alert Volume Management:** Separation of stored/filtered conjunction events from high-priority notifications prevents operator alert fatigue.

---

## 9. Next Steps & Roadmap

- Extend collision probability modeling beyond miss-distance thresholds for blended risk classification.
- Add historical conjunction & fleet altitude trend reporting with persistent time-series data.
- Integrate covariance-based conjunction assessment for higher-fidelity risk modeling beyond TLE-derived point state vectors.
