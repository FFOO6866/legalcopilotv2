"""Tests for SOP template service."""

import pytest

from legalcopilot.services.sop_service import (
    DEFAULT_TEMPLATES,
    get_max_iterations,
    get_quality_threshold,
    get_sop_template,
    list_sop_templates,
)


class TestGetSOPTemplate:
    def test_returns_contract_dispute(self):
        template = get_sop_template("contract_dispute")
        assert template["case_type"] == "contract_dispute"
        assert template["practice_area"] == "contract"
        assert "skills" in template
        assert "knowledge_sources" in template

    def test_returns_employment_dispute(self):
        template = get_sop_template("employment_dispute")
        assert template["case_type"] == "employment_dispute"
        assert template["practice_area"] == "employment"

    def test_returns_family_law(self):
        template = get_sop_template("family_law")
        assert template["case_type"] == "family_law"

    def test_returns_criminal_defence(self):
        template = get_sop_template("criminal_defence")
        assert template["practice_area"] == "criminal"

    def test_returns_general_for_unknown(self):
        template = get_sop_template("unknown_case_type")
        assert template["case_type"] == "general"

    def test_template_has_required_keys(self):
        for t in DEFAULT_TEMPLATES:
            assert "name" in t
            assert "practice_area" in t
            assert "case_type" in t
            assert "skills" in t
            assert "knowledge_sources" in t
            assert "quality_threshold" in t
            assert "max_iterations" in t


class TestListSOPTemplates:
    def test_list_all(self):
        templates = list_sop_templates()
        assert len(templates) == len(DEFAULT_TEMPLATES)

    def test_filter_by_practice_area(self):
        templates = list_sop_templates("criminal")
        assert all(t["practice_area"] == "criminal" for t in templates)
        assert len(templates) >= 1

    def test_filter_nonexistent_area(self):
        templates = list_sop_templates("nonexistent")
        assert templates == []


class TestQualityThreshold:
    def test_contract_dispute_threshold(self):
        assert get_quality_threshold("contract_dispute") == 0.85

    def test_criminal_defence_threshold(self):
        assert get_quality_threshold("criminal_defence") == 0.90

    def test_general_threshold(self):
        assert get_quality_threshold("general") == 0.80

    def test_unknown_falls_back_to_general(self):
        assert get_quality_threshold("unknown") == 0.80


class TestMaxIterations:
    def test_default_is_3(self):
        assert get_max_iterations("general") == 3

    def test_property_is_2(self):
        assert get_max_iterations("property_conveyancing") == 2
