"""Tests for RAG pipeline — priority-based context assembly."""

import pytest

from legalcopilot.services.rag_pipeline import (
    PRIORITY_AUTHORITY,
    PRIORITY_CONTEXT,
    PRIORITY_STATUTE,
    _allocate_token_budget,
    _assemble_context,
    _estimate_tokens,
    _prioritize_results,
    _truncate_to_tokens,
)


class TestTokenEstimation:
    def test_english_legal_text(self):
        text = "The court held that the defendant was liable."
        tokens = _estimate_tokens(text)
        assert tokens > 0
        assert tokens == len(text) // 4

    def test_empty_string(self):
        assert _estimate_tokens("") == 0


class TestTruncateToTokens:
    def test_truncates_at_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence."
        result = _truncate_to_tokens(text, 10)  # ~40 chars
        assert result.endswith(".") or result.endswith("...")

    def test_preserves_short_text(self):
        text = "Short text."
        result = _truncate_to_tokens(text, 100)
        assert result == text

    def test_empty_string(self):
        assert _truncate_to_tokens("", 100) == ""


class TestPrioritizeResults:
    def test_authorities_get_highest_priority(self):
        results = [
            {"payload": {"type": "commentary"}, "score": 0.8},
            {"payload": {"type": "judgment"}, "score": 0.9},
            {"payload": {"type": "statute"}, "score": 0.7},
        ]
        prioritized = _prioritize_results(results)
        # Authorities first, then statutes, then context
        assert prioritized[0]["priority"] == PRIORITY_AUTHORITY
        assert prioritized[1]["priority"] == PRIORITY_STATUTE
        assert prioritized[2]["priority"] == PRIORITY_CONTEXT

    def test_empty_results(self):
        assert _prioritize_results([]) == []

    def test_case_law_is_authority(self):
        results = [{"payload": {"type": "case_law"}, "score": 0.9}]
        _prioritize_results(results)
        assert results[0]["priority"] == PRIORITY_AUTHORITY


class TestAllocateTokenBudget:
    def test_respects_budget(self):
        results = [
            {"payload": {"text": "A" * 4000}, "priority": PRIORITY_AUTHORITY, "score": 0.9},
            {"payload": {"text": "B" * 4000}, "priority": PRIORITY_CONTEXT, "score": 0.5},
        ]
        chunks, sources, truncated = _allocate_token_budget(results, 1500)
        total_tokens = sum(_estimate_tokens(c) for c in chunks)
        assert total_tokens <= 1500

    def test_returns_truncated_flag(self):
        results = [
            {"payload": {"text": "A" * 40000}, "priority": PRIORITY_CONTEXT, "score": 0.9},
        ]
        _, _, truncated = _allocate_token_budget(results, 100)
        assert truncated is True

    def test_continues_past_large_chunk_to_include_smaller(self):
        """After skipping a chunk that doesn't fit, smaller chunks should still be included."""
        results = [
            {"payload": {"text": "A" * 40000}, "priority": PRIORITY_CONTEXT, "score": 0.9},
            {"payload": {"text": "Small."}, "priority": PRIORITY_CONTEXT, "score": 0.5},
        ]
        chunks, sources, truncated = _allocate_token_budget(results, 100)
        assert truncated is True
        assert len(chunks) == 1
        assert chunks[0] == "Small."

    def test_no_truncation_when_under_budget(self):
        results = [
            {"payload": {"text": "Short."}, "priority": PRIORITY_AUTHORITY, "score": 0.9},
        ]
        _, _, truncated = _allocate_token_budget(results, 6000)
        assert truncated is False


class TestAssembleContext:
    def test_joins_with_separators(self):
        chunks = ["First chunk.", "Second chunk."]
        result = _assemble_context(chunks)
        assert "---" in result
        assert "First chunk." in result
        assert "Second chunk." in result

    def test_empty_chunks(self):
        assert _assemble_context([]) == ""

    def test_single_chunk(self):
        result = _assemble_context(["Only chunk."])
        assert result == "Only chunk."
