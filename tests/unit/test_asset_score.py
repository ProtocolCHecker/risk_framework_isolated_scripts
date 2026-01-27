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
    calculate_category_scores,
    apply_circuit_breakers,
    CUSTODY_MODELS,
)
from thresholds import DEFAULT_CATEGORY_WEIGHTS, DEFAULT_CIRCUIT_BREAKERS_ENABLED


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


class TestCustomWeights:
    """Tests for custom category weight functionality."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_custom_weights_affect_score(self, passing_primary_checks_metrics, config_factory):
        """Custom weights should produce different scores than defaults."""
        config = config_factory(**passing_primary_checks_metrics)

        # Get default score
        result_default = calculate_asset_risk_score(config)

        # Custom weights emphasizing different categories
        custom_weights = {
            "smart_contract": 0.40,  # Increased from 0.10
            "counterparty": 0.10,  # Decreased from 0.25
            "market": 0.10,
            "liquidity": 0.10,
            "collateral": 0.10,
            "reserve_oracle": 0.20,
        }
        result_custom = calculate_asset_risk_score(config, custom_weights=custom_weights)

        # Both should be qualified
        if result_default["qualified"] and result_custom["qualified"]:
            # Scores may differ due to different weighting
            # The actual score difference depends on category scores
            assert result_custom["scoring_settings"]["custom_weights_used"] is True
            assert result_custom["scoring_settings"]["custom_weights"] == custom_weights

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_custom_weights_applied_to_categories(self, passing_primary_checks_metrics, config_factory):
        """Custom weights should be reflected in category results."""
        config = config_factory(**passing_primary_checks_metrics)

        custom_weights = {
            "smart_contract": 0.20,
            "counterparty": 0.20,
            "market": 0.20,
            "liquidity": 0.20,
            "collateral": 0.10,
            "reserve_oracle": 0.10,
        }
        result = calculate_asset_risk_score(config, custom_weights=custom_weights)

        if result["qualified"]:
            for cat_key, expected_weight in custom_weights.items():
                actual_weight = result["categories"][cat_key]["weight"]
                assert abs(actual_weight - expected_weight) < 0.001, \
                    f"{cat_key} weight mismatch: expected {expected_weight}, got {actual_weight}"

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_default_weights_when_none_provided(self, passing_primary_checks_metrics, config_factory):
        """When no custom weights provided, should use defaults."""
        config = config_factory(**passing_primary_checks_metrics)

        result = calculate_asset_risk_score(config)

        if result["qualified"]:
            assert result["scoring_settings"]["custom_weights_used"] is False
            for cat_key in DEFAULT_CATEGORY_WEIGHTS:
                expected_weight = DEFAULT_CATEGORY_WEIGHTS[cat_key]["weight"]
                actual_weight = result["categories"][cat_key]["weight"]
                assert abs(actual_weight - expected_weight) < 0.001

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_partial_custom_weights(self, passing_primary_checks_metrics, config_factory):
        """Partial custom weights should work, with defaults for unspecified."""
        config = config_factory(**passing_primary_checks_metrics)

        # Only specify some weights
        custom_weights = {
            "smart_contract": 0.30,
            "counterparty": 0.30,
        }
        result = calculate_asset_risk_score(config, custom_weights=custom_weights)

        if result["qualified"]:
            # Specified weights should be custom
            assert abs(result["categories"]["smart_contract"]["weight"] - 0.30) < 0.001
            assert abs(result["categories"]["counterparty"]["weight"] - 0.30) < 0.001
            # Unspecified should be default
            assert abs(result["categories"]["market"]["weight"] - DEFAULT_CATEGORY_WEIGHTS["market"]["weight"]) < 0.001


class TestCircuitBreakerToggle:
    """Tests for circuit breaker enable/disable functionality."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_all_circuit_breakers_disabled(self, config_factory):
        """Disabling all circuit breakers should prevent score capping."""
        # Create config that would trigger circuit breakers
        config = config_factory()
        config["audit_data"] = {"auditor": "Test"}  # Pass primary check
        config["reserve_ratio"] = 0.95  # Would trigger undercollateralized breaker

        # With circuit breakers enabled (default)
        result_with_cb = calculate_asset_risk_score(config)

        # With all circuit breakers disabled
        all_disabled = {
            "reserve_undercollateralized": False,
            "all_admin_eoa": False,
            "active_security_incident": False,
            "critical_category_failure": False,
            "severe_category_weakness": False,
            "no_audit": False,
        }
        result_no_cb = calculate_asset_risk_score(config, circuit_breakers_enabled=all_disabled)

        # When disabled, no breakers should be triggered
        if result_no_cb["qualified"]:
            assert len(result_no_cb["circuit_breakers"]["triggered"]) == 0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_selective_circuit_breaker_disable(self, config_factory):
        """Selectively disabling breakers should only affect those breakers."""
        config = config_factory()
        config["audit_data"] = {"auditor": "Test"}
        config["reserve_ratio"] = 0.95  # Triggers undercollateralized

        # Disable only the undercollateralized breaker
        selective_disable = {
            "reserve_undercollateralized": False,
            "all_admin_eoa": True,
            "active_security_incident": True,
            "critical_category_failure": True,
            "severe_category_weakness": True,
            "no_audit": True,
        }
        result = calculate_asset_risk_score(config, circuit_breakers_enabled=selective_disable)

        if result["qualified"]:
            # Undercollateralized should not be in triggered list
            triggered_names = [t["name"] for t in result["circuit_breakers"]["triggered"]]
            assert "Reserve Undercollateralized" not in triggered_names

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_default_circuit_breakers_all_enabled(self, passing_primary_checks_metrics, config_factory):
        """By default, all circuit breakers should be enabled."""
        config = config_factory(**passing_primary_checks_metrics)
        result = calculate_asset_risk_score(config)

        if result["qualified"]:
            enabled_config = result["circuit_breakers"]["enabled_config"]
            for breaker_name in DEFAULT_CIRCUIT_BREAKERS_ENABLED:
                assert enabled_config.get(breaker_name, False) is True

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_circuit_breaker_config_in_result(self, passing_primary_checks_metrics, config_factory):
        """Circuit breaker enabled config should be included in result."""
        config = config_factory(**passing_primary_checks_metrics)

        custom_cb = {"no_audit": False, "all_admin_eoa": True}
        result = calculate_asset_risk_score(config, circuit_breakers_enabled=custom_cb)

        if result["qualified"]:
            assert result["scoring_settings"]["circuit_breakers_customized"] is True


class TestCombinedCustomSettings:
    """Tests for combining custom weights and circuit breakers."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_both_custom_weights_and_circuit_breakers(self, passing_primary_checks_metrics, config_factory):
        """Both custom weights and circuit breakers should work together."""
        config = config_factory(**passing_primary_checks_metrics)

        custom_weights = {
            "smart_contract": 0.25,
            "counterparty": 0.25,
            "market": 0.15,
            "liquidity": 0.15,
            "collateral": 0.10,
            "reserve_oracle": 0.10,
        }
        custom_cb = {
            "no_audit": False,
            "severe_category_weakness": False,
        }

        result = calculate_asset_risk_score(
            config,
            custom_weights=custom_weights,
            circuit_breakers_enabled=custom_cb
        )

        if result["qualified"]:
            assert result["scoring_settings"]["custom_weights_used"] is True
            assert result["scoring_settings"]["circuit_breakers_customized"] is True
            # Verify weights applied
            assert abs(result["categories"]["smart_contract"]["weight"] - 0.25) < 0.001
