"""Tests for CDM generator."""
import pytest
from unittest.mock import MagicMock
from models.cdm_generator import generate_cdm, format_cdm_kvn, _infer_object_type


def _make_approach(pri_id=25544, sec_id=99999, miss=5.0, pc=1.5e-5):
    a = MagicMock()
    a.primary_name = "ISS (ZARYA)"
    a.primary_norad_id = pri_id
    a.secondary_name = "COSMOS 2251 DEB"
    a.secondary_norad_id = sec_id
    a.tca = "2026-03-08T12:00:00Z"
    a.miss_distance_km = miss
    a.relative_velocity_km_s = 14.2
    a.radial_km = 2.0
    a.in_track_km = 3.0
    a.cross_track_km = 1.5
    a.collision_probability = pc
    return a


class TestGenerateCDM:
    def test_contains_required_fields(self):
        cdm = generate_cdm(_make_approach())
        assert "CCSDS_CDM_VERS" in cdm
        assert "CREATION_DATE" in cdm
        assert "TCA" in cdm
        assert "MISS_DISTANCE" in cdm
        assert "RELATIVE_SPEED" in cdm
        assert "COLLISION_PROBABILITY" in cdm

    def test_miss_distance_in_meters(self):
        cdm = generate_cdm(_make_approach(miss=5.0))
        assert cdm["MISS_DISTANCE"] == 5000.0  # 5 km → 5000 m

    def test_objects_present(self):
        cdm = generate_cdm(_make_approach())
        assert cdm["OBJECT1_NAME"] == "ISS (ZARYA)"
        assert cdm["OBJECT2_NAME"] == "COSMOS 2251 DEB"

    def test_ric_components(self):
        cdm = generate_cdm(_make_approach())
        assert cdm["RELATIVE_POSITION_R"] == 2000.0
        assert cdm["RELATIVE_POSITION_T"] == 3000.0
        assert cdm["RELATIVE_POSITION_N"] == 1500.0

    def test_message_id_auto_generated(self):
        cdm = generate_cdm(_make_approach())
        assert "25544" in cdm["MESSAGE_ID"]
        assert "99999" in cdm["MESSAGE_ID"]


class TestFormatKVN:
    def test_kvn_is_string(self):
        cdm = generate_cdm(_make_approach())
        kvn = format_cdm_kvn(cdm)
        assert isinstance(kvn, str)

    def test_kvn_contains_header(self):
        cdm = generate_cdm(_make_approach())
        kvn = format_cdm_kvn(cdm)
        assert "CCSDS_CDM_VERS" in kvn
        assert "CREATION_DATE" in kvn

    def test_kvn_contains_objects(self):
        cdm = generate_cdm(_make_approach())
        kvn = format_cdm_kvn(cdm)
        assert "OBJECT1" in kvn
        assert "OBJECT2" in kvn

    def test_kvn_contains_pc(self):
        cdm = generate_cdm(_make_approach(pc=1.5e-5))
        kvn = format_cdm_kvn(cdm)
        assert "COLLISION_PROBABILITY" in kvn


class TestInferObjectType:
    def test_debris(self):
        assert _infer_object_type("COSMOS 2251 DEB") == "DEBRIS"

    def test_rocket_body(self):
        assert _infer_object_type("CZ-2C R/B") == "ROCKET BODY"

    def test_payload(self):
        assert _infer_object_type("ISS (ZARYA)") == "PAYLOAD"
