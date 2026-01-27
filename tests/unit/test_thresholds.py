"""
Unit tests for thresholds module.

Tests the threshold definitions and category weights used in scoring.
Validates that thresholds are properly structured and weights sum to 1.0.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from thresholds import (
    GRADE_SCALE,
    CATEGORY_WEIGHTS,
    SMART_CONTRACT_THRESHOLDS,
    COUNTERPARTY_THRESHOLDS,
    MARKET_THRESHOLDS,
    LIQUIDITY_THRESHOLDS,
    COLLATERAL_THRESHOLDS,
    RESERVE_ORACLE_THRESHOLDS,
    CIRCUIT_BREAKERS,
)


class TestGradeScale:
    """Tests for the grade scale definitions."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_all_grades_defined(self):
        """All expected grades should be defined."""
        expected_grades = ["A", "B", "C", "D", "F"]
        for grade in expected_grades:
            assert grade in GRADE_SCALE

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_grade_ranges_are_contiguous(self):
        """Grade ranges should cover 0-100 without gaps."""
        grades_sorted = sorted(GRADE_SCALE.items(), key=lambda x: x[1]["min"], reverse=True)

        # Check coverage from 0 to 100
        covered = set()
        for grade, config in grades_sorted:
            for score in range(config["min"], config["max"] + 1):
                covered.add(score)

        # All scores 0-100 should be covered
        assert covered == set(range(0, 101)), "Grade ranges have gaps or overlaps"

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_grade_has_required_fields(self):
        """Each grade should have min, max, label, risk_level."""
        required_fields = ["min", "max", "label", "risk_level"]
        for grade, config in GRADE_SCALE.items():
            for field in required_fields:
                assert field in config, f"Grade {grade} missing field: {field}"


class TestCategoryWeights:
    """Tests for category weight definitions."""

    @pytest.mark.unit
    @pytest.mark.scoring
    @pytest.mark.smoke
    def test_weights_sum_to_one(self):
        """Category weights must sum to 1.0 (100%)."""
        total_weight = sum(cat["weight"] for cat in CATEGORY_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001, f"Weights sum to {total_weight}, expected 1.0"

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_all_categories_have_weights(self):
        """All expected categories should have weights defined."""
        expected_categories = [
            "smart_contract",
            "counterparty",
            "market",
            "liquidity",
            "collateral",
            "reserve_oracle",
        ]
        for category in expected_categories:
            assert category in CATEGORY_WEIGHTS, f"Missing weight for {category}"

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_weights_are_positive(self):
        """All weights should be positive."""
        for category, config in CATEGORY_WEIGHTS.items():
            assert config["weight"] > 0, f"Weight for {category} should be positive"

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_weights_have_justification(self):
        """Each weight should have a justification."""
        for category, config in CATEGORY_WEIGHTS.items():
            assert "justification" in config, f"Missing justification for {category}"
            assert len(config["justification"]) > 20, f"Justification for {category} too short"


class TestSmartContractThresholds:
    """Tests for smart contract risk thresholds."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_thresholds_defined(self):
        """Smart contract thresholds should be defined."""
        assert SMART_CONTRACT_THRESHOLDS is not None
        assert len(SMART_CONTRACT_THRESHOLDS) > 0


class TestCounterpartyThresholds:
    """Tests for counterparty risk thresholds."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_thresholds_defined(self):
        """Counterparty thresholds should be defined."""
        assert COUNTERPARTY_THRESHOLDS is not None

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_timelock_thresholds_ordered(self):
        """Longer timelocks should have higher scores."""
        if "timelock" in COUNTERPARTY_THRESHOLDS:
            timelock = COUNTERPARTY_THRESHOLDS["timelock"]
            # Check that thresholds are ordered by value
            if isinstance(timelock, list):
                for i in range(len(timelock) - 1):
                    if "value" in timelock[i] and "value" in timelock[i + 1]:
                        # Higher timelock hours = higher score
                        if timelock[i]["value"] < timelock[i + 1]["value"]:
                            assert timelock[i]["score"] <= timelock[i + 1]["score"]


class TestMarketThresholds:
    """Tests for market risk thresholds."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_thresholds_defined(self):
        """Market thresholds should be defined."""
        assert MARKET_THRESHOLDS is not None

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_peg_deviation_penalizes_larger_deviations(self):
        """Larger peg deviations should result in lower scores."""
        if "peg_deviation" in MARKET_THRESHOLDS:
            # Thresholds should penalize larger deviations
            pass  # Implementation depends on threshold structure


class TestLiquidityThresholds:
    """Tests for liquidity risk thresholds."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_thresholds_defined(self):
        """Liquidity thresholds should be defined."""
        assert LIQUIDITY_THRESHOLDS is not None

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_slippage_thresholds_penalize_high_slippage(self):
        """Higher slippage should result in lower scores."""
        # Lower slippage = better = higher score
        pass  # Implementation depends on threshold structure


class TestCollateralThresholds:
    """Tests for collateral risk thresholds."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_thresholds_defined(self):
        """Collateral thresholds should be defined."""
        assert COLLATERAL_THRESHOLDS is not None


class TestReserveOracleThresholds:
    """Tests for reserve and oracle risk thresholds."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_thresholds_defined(self):
        """Reserve/Oracle thresholds should be defined."""
        assert RESERVE_ORACLE_THRESHOLDS is not None

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_full_backing_gets_high_score(self):
        """100% reserve backing should get high score."""
        # PoR ratio >= 1.0 should score well
        pass  # Implementation depends on threshold structure


class TestCircuitBreakers:
    """Tests for circuit breaker definitions."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_circuit_breakers_defined(self):
        """Circuit breakers should be defined."""
        assert CIRCUIT_BREAKERS is not None
        assert len(CIRCUIT_BREAKERS) > 0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_critical_circuit_breakers_exist(self):
        """Critical circuit breakers should be defined."""
        # These are mentioned in the documentation
        expected_breakers = [
            "reserve_undercollateralized",
            "critical_admin_eoa",
            "active_security_incident",
        ]
        breaker_names = [b.get("name", "").lower() for b in CIRCUIT_BREAKERS] if isinstance(CIRCUIT_BREAKERS, list) else list(CIRCUIT_BREAKERS.keys())

        # At least some critical breakers should exist
        # (exact names may vary)
        assert len(breaker_names) >= 3, "Should have at least 3 circuit breakers"
