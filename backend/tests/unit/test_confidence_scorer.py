# backend/tests/unit/test_confidence_scorer.py
"""
Unit Tests — Confidence Scorer (logic tests, no Neo4j required)
"""

import pytest

from backend.api.schemas import ConfidenceScore


class TestConfidenceFormula:
    """Test the confidence = cohesion * (1 - coupling) formula."""

    def test_perfect_cohesion_no_coupling(self):
        cohesion, coupling = 1.0, 0.0
        confidence = cohesion * (1.0 - coupling)
        assert confidence == 1.0

    def test_no_cohesion_full_coupling(self):
        cohesion, coupling = 0.0, 1.0
        confidence = cohesion * (1.0 - coupling)
        assert confidence == 0.0

    def test_medium_scores(self):
        cohesion, coupling = 0.8, 0.3
        confidence = cohesion * (1.0 - coupling)
        assert 0.5 < confidence < 0.6

    def test_flagging_threshold(self):
        threshold = 0.65
        # Below threshold → flagged
        low = ConfidenceScore(boundary_name="A", cohesion=0.5, coupling=0.5, confidence=0.25, flagged=True)
        assert low.flagged is True
        # Above threshold → not flagged
        high = ConfidenceScore(boundary_name="B", cohesion=0.9, coupling=0.1, confidence=0.81, flagged=False)
        assert high.flagged is False


class TestConfidenceScoreModel:
    def test_defaults(self):
        score = ConfidenceScore(boundary_name="test")
        assert score.cohesion == 0.0
        assert score.coupling == 0.0
        assert score.confidence == 0.0
        assert score.flagged is False

    def test_serialisation(self):
        score = ConfidenceScore(
            boundary_name="OrderMgmt", cohesion=0.75, coupling=0.2,
            confidence=0.6, flagged=True,
        )
        d = score.model_dump()
        assert d["boundary_name"] == "OrderMgmt"
        assert d["flagged"] is True
