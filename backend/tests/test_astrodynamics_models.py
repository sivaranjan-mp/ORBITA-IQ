import uuid
from datetime import datetime, timezone
import pytest

from app.models.astrodynamics import (
    DataSource,
    AlgorithmVersion,
    OEMRecord,
    StateVector,
    CovarianceMatrix,
    OrbitSolution,
    DataFreshness,
    CDMRecord,
)
from app.schemas.astrodynamics import (
    DataSourceCreate,
    AlgorithmVersionCreate,
    StateVectorCreate,
    CovarianceMatrixCreate,
    OrbitSolutionCreate,
    OEMRecordCreate,
    DataFreshnessBase,
)
from app.schemas.cdm import CDMRecordBase


def test_astrodynamics_model_instantiation():
    # 1. DataSource
    ds = DataSource(
        code="CELESTRAK",
        name="CelesTrak",
        category="EXTERNAL_CATALOG",
        is_authoritative=True,
        description="Public GP/TLE catalog",
    )
    assert ds.code == "CELESTRAK"
    assert ds.is_authoritative is True

    # 2. AlgorithmVersion
    alg = AlgorithmVersion(
        name="FOSTER_PC_2D",
        version="1.0.0",
        author="NASA CARA",
        parameters={"integration_method": "foster_1992"},
        is_active=True,
    )
    assert alg.name == "FOSTER_PC_2D"
    assert alg.parameters["integration_method"] == "foster_1992"

    # 3. StateVector
    now = datetime.now(timezone.utc)
    sv = StateVector(
        norad_id=25544,
        epoch=now,
        reference_frame="TEME",
        x_km=1000.0,
        y_km=2000.0,
        z_km=3000.0,
        vx_kms=1.0,
        vy_kms=2.0,
        vz_kms=3.0,
    )
    assert sv.norad_id == 25544
    assert sv.reference_frame == "TEME"
    assert sv.x_km == 1000.0

    # 4. CovarianceMatrix
    cov = CovarianceMatrix(
        state_vector_id=sv.id,
        reference_frame="RTN",
        cx_x=0.01,
        cy_y=0.02,
        cz_z=0.03,
    )
    assert cov.reference_frame == "RTN"
    assert cov.cx_x == 0.01

    # 5. OrbitSolution
    sol = OrbitSolution(
        norad_id=25544,
        epoch=now,
        solution_type="SGP4_TLE",
        semi_major_axis_km=6780.0,
        eccentricity=0.0001,
        inclination_deg=51.64,
    )
    assert sol.norad_id == 25544
    assert sol.inclination_deg == 51.64

    # 6. CDMRecord
    cdm = CDMRecord(
        primary_norad_id=25544,
        secondary_norad_id=40000,
        tca=now,
        payload={"MISS_DISTANCE": 150.0},
        miss_distance_m=150.0,
        collision_probability=1e-5,
    )
    assert cdm.primary_norad_id == 25544
    assert cdm.miss_distance_m == 150.0


def test_astrodynamics_pydantic_validation():
    now = datetime.now(timezone.utc)
    sv_schema = StateVectorCreate(
        epoch=now,
        reference_frame="ECI_J2000",
        x_km=500.0,
        y_km=600.0,
        z_km=700.0,
        vx_kms=0.5,
        vy_kms=0.6,
        vz_kms=0.7,
        norad_id=25544,
    )
    assert sv_schema.reference_frame == "ECI_J2000"
    assert sv_schema.x_km == 500.0

    cov_schema = CovarianceMatrixCreate(
        reference_frame="RTN",
        cx_x=0.05,
        cy_y=0.05,
        cz_z=0.05,
    )
    assert cov_schema.cx_x == 0.05
    assert cov_schema.cx_y == 0.0

    cdm_schema = CDMRecordBase(
        primary_norad_id=25544,
        secondary_norad_id=99999,
        tca=now,
        payload={"raw": "test"},
        miss_distance_m=42.5,
        collision_probability=0.00012,
    )
    assert cdm_schema.miss_distance_m == 42.5
