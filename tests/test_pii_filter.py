"""Tests for Singapore-specific PII filter."""

import pytest

from legalcopilot.services.pii_filter import detect_pii, has_pii, redact_pii


class TestNRICDetection:
    """NRIC/FIN pattern: [STFGM] + 7 digits + [A-Z]."""

    def test_redacts_nric(self):
        text = "The applicant S1234567A filed the claim."
        result = redact_pii(text)
        assert "S1234567A" not in result
        assert "[REDACTED_NRIC]" in result

    def test_redacts_fin(self):
        text = "Foreign worker FIN: G9876543B."
        result = redact_pii(text)
        assert "G9876543B" not in result

    def test_redacts_m_series_nric(self):
        text = "New citizen M1234567C registered."
        result = redact_pii(text)
        assert "M1234567C" not in result

    def test_preserves_case_citations(self):
        """Case citations like [2024] SGHC 123 should NOT be redacted."""
        text = "As held in [2024] SGHC 123 at paragraph 45."
        result = redact_pii(text)
        assert "[2024] SGHC 123" in result


class TestPhoneDetection:
    """Singapore phone: +65 followed by 8 digits."""

    def test_redacts_sg_phone(self):
        text = "Contact: +65 9123 4567 for details."
        result = redact_pii(text)
        assert "9123 4567" not in result

    def test_redacts_sg_phone_no_space(self):
        text = "Call +6591234567."
        result = redact_pii(text)
        assert "91234567" not in result


class TestEmailDetection:
    def test_redacts_email(self):
        text = "Send to lawyer@example.com for review."
        result = redact_pii(text)
        assert "lawyer@example.com" not in result
        assert "[REDACTED_EMAIL]" in result


class TestUENDetection:
    """UEN format: digits + letter (e.g., 202012345A)."""

    def test_redacts_uen(self):
        text = "Company UEN: 202012345A is registered."
        result = redact_pii(text)
        assert "202012345A" not in result


class TestDetectPII:
    def test_detect_returns_findings(self):
        text = "Mr Tan, NRIC S1234567A, email tan@law.sg, phone +65 91234567."
        findings = detect_pii(text)
        assert len(findings) >= 3

    def test_has_pii_true(self):
        assert has_pii("Contact S1234567A immediately.")

    def test_has_pii_false(self):
        assert not has_pii("The court held that the appeal was dismissed.")


class TestEdgeCases:
    def test_empty_string(self):
        assert redact_pii("") == ""

    def test_no_pii(self):
        text = "The defendant submitted written submissions on 1 January 2024."
        assert redact_pii(text) == text

    def test_multiple_pii_types(self):
        text = "S1234567A contacted via +65 91234567 and tan@law.sg."
        result = redact_pii(text)
        assert "S1234567A" not in result
        assert "91234567" not in result
        assert "tan@law.sg" not in result
