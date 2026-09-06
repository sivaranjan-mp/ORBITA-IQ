-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0016_data_quality_scoring_algorithm.sql
-- Scope: Register DATA_QUALITY_SCORING in algorithm_versions
-- ============================================================================

BEGIN;

insert into public.algorithm_versions (name, version, author, description, parameters, is_active)
values
(
    'DATA_QUALITY_SCORING',
    '1.0.0',
    'ORBITA-IQ Astrodynamics Core',
    'Regime-aware multi-attribute orbital freshness, provenance, and covariance scoring formula.',
    '{
      "weights": {
        "freshness": 0.50,
        "source": 0.25,
        "covariance": 0.25
      },
      "regime_thresholds_hours": {
        "LEO": {"fresh": 18.0, "aging": 48.0, "stale": 96.0},
        "HEO": {"fresh": 24.0, "aging": 72.0, "stale": 144.0},
        "MEO": {"fresh": 36.0, "aging": 96.0, "stale": 168.0},
        "GEO": {"fresh": 48.0, "aging": 120.0, "stale": 240.0},
        "OTHER": {"fresh": 24.0, "aging": 48.0, "stale": 96.0}
      },
      "source_scores": {
        "SPACE_TRACK": 100,
        "CELESTRAK": 100,
        "LEOLABS": 95,
        "INTERNAL_OD": 90,
        "OPERATOR_EPHEMERIS": 90,
        "INTERNAL_SGP4": 80,
        "USER_UPLOAD": 60,
        "UNKNOWN": 30
      },
      "covariance_scores": {
        "FULL_6X6": 100,
        "POSITION_DIAGONAL": 60,
        "NONE": 20
      },
      "quality_bands": {
        "HIGH": 75.0,
        "MEDIUM": 60.0,
        "LOW": 35.0
      }
    }'::jsonb,
    true
)
on conflict (name, version) do update
set
    parameters = excluded.parameters,
    description = excluded.description,
    author = excluded.author,
    is_active = excluded.is_active,
    updated_at = now();

COMMIT;
