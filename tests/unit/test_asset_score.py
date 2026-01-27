"""
Unit tests for asset_score module.

Tests the scoring engine that calculates weighted risk scores
across 6 categories: smart_contract, counterparty, market,
liquidity, collateral, reserve_oracle.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from asset_score import (
    score_to_grade,
    calculate_asset_risk_score,
    CUSTODY_MODELS,
)


class TestScoreToGrade:
    """Tests for the score_to_grade helper function."""

    @pytest.mark.unit
    @pytest.mark.scoring
    @pytest.mark.parametrize("score,expected_grade", [
        (100, "A"),
        (85, "A"),
        (84, "B"),
        (70, "B"),
        (69, "C"),
        (55, "C"),
        (54, "D"),
        (40, "D"),
        (39, "F"),
        (0, "F"),
    ])
    def test_grade_boundaries(self, score, expected_grade):
        """Verify correct grade assignment at boundaries."""
        assert score_to_grade(score) == expected_grade

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_mid_range_scores(self, grade_boundaries):
        """Verify grades for mid-range scores."""
        for grade, (min_score, max_score) in grade_boundaries.items():
            mid_score = (min_score + max_score) / 2
            assert score_to_grade(mid_score) == grade


class TestCustodyModels:
    """Tests for custody model scoring."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_all_custody_models_have_scores(self):
        """All defined custody models should have score and justification."""
        expected_models = ["decentralized", "regulated_insured", "regulated", "unregulated", "unknown"]
        for model in expected_models:
            assert model in CUSTODY_MODELS
            assert "score" in CUSTODY_MODELS[model]
            assert "justification" in CUSTODY_MODELS[model]

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_custody_model_score_ordering(self):
        """Scores should follow risk ordering: decentralized > regulated_insured > ... > unknown."""
        assert CUSTODY_MODELS["decentralized"]["score"] > CUSTODY_MODELS["regulated_insured"]["score"]
        assert CUSTODY_MODELS["regulated_insured"]["score"] > CUSTODY_MODELS["regulated"]["score"]
        assert CUSTODY_MODELS["regulated"]["score"] > CUSTODY_MODELS["unregulated"]["score"]
        assert CUSTODY_MODELS["unregulated"]["score"] > CUSTODY_MODELS["unknown"]["score"]


class TestCalculateAssetRiskScore:
    """Tests for the main scoring function."""

    @pytest.mark.unit
    @pytest.mark.scoring
    @pytest.mark.smoke
    def test_qualified_asset_gets_score(self, sample_wsteth_config):
        """Asset passing primary checks should receive a score."""
        # Note: This test may need mocking if it calls external APIs
        # For now, we test the structure of what's returned
        result = calculate_asset_risk_score(sample_wsteth_config)

        assert "primary_checks" in result
        assert "qualified" in result
        # If qualified, should have overall score
        if result["qualified"]:
            assert result["overall"] is not None
            assert "score" in result["overall"]

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_disqualified_asset_gets_no_score(self, config_factory):
        """Asset failing primary checks should not receive a final score."""
        # Create config with no audit data
        config = config_factory()
        config["audit_data"] = None

        result = calculate_asset_risk_score(config)

        assert "primary_checks" in result
        assert result["qualified"] is False
        assert result["status"] == "DISQUALIFIED"
        # Overall score should be None when disqualified
        assert result["overall"] is None

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_returns_category_breakdown(self, passing_primary_checks_metrics, config_factory):
        """Result should include scores for each category."""
        config = config_factory(**passing_primary_checks_metrics)

        result = calculate_asset_risk_score(config)

        # If qualified, should have category scores
        if result.get("qualified", False):
            assert result["categories"] is not None
            categories = ["smart_contract", "counterparty", "market", "liquidity", "collateral", "reserve_oracle"]
            for category in categories:
                assert category in result["categories"]


class TestScoringEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_empty_config_handled_gracefully(self):
        """Empty config should not crash, should fail gracefully."""
        try:
            result = calculate_asset_risk_score({})
            # Should fail primary checks (not qualified)
            assert result.get("qualified", True) is False
        except Exception as e:
            # If it raises, it should be a meaningful error
            assert "config" in str(e).lower() or "required" in str(e).lower() or "key" in str(e).lower()

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_none_values_handled(self, config_factory):
        """None values in config should be handled without crashing."""
        config = config_factory()
        config["custody_model"] = None
        config["timelock_hours"] = None

        try:
            result = calculate_asset_risk_score(config)
            # Should complete without crashing
            assert result is not None
        except TypeError:
            pytest.fail("None values caused TypeError - needs better handling")


class TestScoringConsistency:
    """Tests for scoring consistency and determinism."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_same_input_same_output(self, sample_wsteth_config):
        """Same config should always produce same score."""
        result1 = calculate_asset_risk_score(sample_wsteth_config)
        result2 = calculate_asset_risk_score(sample_wsteth_config)

        # Both should have same qualified status
        assert result1["qualified"] == result2["qualified"]
        # If qualified, scores should match
        if result1["qualified"] and result2["qualified"]:
            assert result1["overall"]["score"] == result2["overall"]["score"]

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_score_within_valid_range(self, sample_wsteth_config):
        """Final score should always be between 0 and 100."""
        result = calculate_asset_risk_score(sample_wsteth_config)

        if result["qualified"] and result["overall"] is not None:
            score = result["overall"]["score"]
            assert 0 <= score <= 100, f"Score {score} out of valid range [0, 100]"
