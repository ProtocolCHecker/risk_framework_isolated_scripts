"""
Unit tests for fractional_reserve module.

Tests the core calculation logic for PSM/fractional reserve stablecoins
like cUSD. These tests are isolated and don't require blockchain connections.
"""

import pytest
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestBackingRatioCalculation:
    """Tests for backing ratio calculations."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_backing_ratio_fully_backed(self):
        """100% backing ratio when reserves equal supply."""
        from fractional_reserve import calculate_backing_ratio

        total_supply = 100_000_000.0
        total_reserves = 100_000_000.0

        ratio = calculate_backing_ratio(total_reserves, total_supply)

        assert ratio == 100.0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_backing_ratio_over_collateralized(self):
        """Backing ratio > 100% when reserves exceed supply."""
        from fractional_reserve import calculate_backing_ratio

        total_supply = 100_000_000.0
        total_reserves = 110_000_000.0

        ratio = calculate_backing_ratio(total_reserves, total_supply)

        assert abs(ratio - 110.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_backing_ratio_under_collateralized(self):
        """Backing ratio < 100% when reserves less than supply."""
        from fractional_reserve import calculate_backing_ratio

        total_supply = 100_000_000.0
        total_reserves = 95_000_000.0

        ratio = calculate_backing_ratio(total_reserves, total_supply)

        assert ratio == 95.0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_backing_ratio_zero_supply(self):
        """Should handle zero supply gracefully."""
        from fractional_reserve import calculate_backing_ratio

        total_supply = 0.0
        total_reserves = 100_000_000.0

        ratio = calculate_backing_ratio(total_reserves, total_supply)

        # When supply is 0, ratio should be 100% (no tokens to back)
        assert ratio == 100.0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_backing_ratio_zero_reserves(self):
        """Should handle zero reserves."""
        from fractional_reserve import calculate_backing_ratio

        total_supply = 100_000_000.0
        total_reserves = 0.0

        ratio = calculate_backing_ratio(total_reserves, total_supply)

        assert ratio == 0.0


class TestUtilizationCalculation:
    """Tests for utilization rate calculations."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_utilization_normal(self):
        """Normal utilization calculation."""
        from fractional_reserve import calculate_utilization

        total_supplies = 100_000_000.0
        total_borrows = 20_000_000.0

        utilization = calculate_utilization(total_borrows, total_supplies)

        assert utilization == 20.0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_utilization_zero_borrows(self):
        """Zero utilization when nothing borrowed."""
        from fractional_reserve import calculate_utilization

        total_supplies = 100_000_000.0
        total_borrows = 0.0

        utilization = calculate_utilization(total_borrows, total_supplies)

        assert utilization == 0.0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_utilization_full(self):
        """100% utilization when all borrowed."""
        from fractional_reserve import calculate_utilization

        total_supplies = 100_000_000.0
        total_borrows = 100_000_000.0

        utilization = calculate_utilization(total_borrows, total_supplies)

        assert utilization == 100.0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_utilization_zero_supplies(self):
        """Should handle zero supplies gracefully."""
        from fractional_reserve import calculate_utilization

        total_supplies = 0.0
        total_borrows = 0.0

        utilization = calculate_utilization(total_borrows, total_supplies)

        assert utilization == 0.0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_utilization_over_100_percent(self):
        """Handle edge case where borrows > supplies (shouldn't happen but be safe)."""
        from fractional_reserve import calculate_utilization

        total_supplies = 100_000_000.0
        total_borrows = 120_000_000.0  # More borrowed than supplied (edge case)

        utilization = calculate_utilization(total_borrows, total_supplies)

        # Should cap at 100% or return actual value depending on implementation
        assert utilization >= 100.0


class TestRiskFlagDetection:
    """Tests for risk flag generation."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_no_risk_flags_healthy_state(self):
        """No flags when all metrics are healthy."""
        from fractional_reserve import calculate_risk_flags

        data = {
            "backing_ratio_pct": 105.0,
            "overall_utilization_pct": 10.0,
            "oracle_staleness_seconds": 300,  # 5 minutes
            "asset_allocations": [
                {"symbol": "USDC", "allocation_pct": 60.0},
                {"symbol": "USDT", "allocation_pct": 40.0}
            ]
        }

        thresholds = {
            "min_backing_ratio_pct": 100,
            "max_utilization_pct": 80,
            "max_single_asset_pct": 70,
            "max_staleness_seconds": 3600
        }

        flags = calculate_risk_flags(data, thresholds)

        assert len(flags) == 0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_flag_undercollateralized(self):
        """Flag when backing ratio below threshold."""
        from fractional_reserve import calculate_risk_flags

        data = {
            "backing_ratio_pct": 95.0,  # Below 100%
            "overall_utilization_pct": 10.0,
            "oracle_staleness_seconds": 300,
            "asset_allocations": []
        }

        thresholds = {
            "min_backing_ratio_pct": 100,
            "max_utilization_pct": 80,
            "max_single_asset_pct": 70,
            "max_staleness_seconds": 3600
        }

        flags = calculate_risk_flags(data, thresholds)

        assert "UNDERCOLLATERALIZED" in flags

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_flag_high_utilization(self):
        """Flag when utilization exceeds threshold."""
        from fractional_reserve import calculate_risk_flags

        data = {
            "backing_ratio_pct": 105.0,
            "overall_utilization_pct": 85.0,  # Above 80%
            "oracle_staleness_seconds": 300,
            "asset_allocations": []
        }

        thresholds = {
            "min_backing_ratio_pct": 100,
            "max_utilization_pct": 80,
            "max_single_asset_pct": 70,
            "max_staleness_seconds": 3600
        }

        flags = calculate_risk_flags(data, thresholds)

        assert "HIGH_UTILIZATION" in flags

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_flag_concentration_risk(self):
        """Flag when single asset exceeds concentration threshold."""
        from fractional_reserve import calculate_risk_flags

        data = {
            "backing_ratio_pct": 105.0,
            "overall_utilization_pct": 10.0,
            "oracle_staleness_seconds": 300,
            "asset_allocations": [
                {"symbol": "USDC", "allocation_pct": 80.0},  # Above 70%
                {"symbol": "USDT", "allocation_pct": 20.0}
            ]
        }

        thresholds = {
            "min_backing_ratio_pct": 100,
            "max_utilization_pct": 80,
            "max_single_asset_pct": 70,
            "max_staleness_seconds": 3600
        }

        flags = calculate_risk_flags(data, thresholds)

        assert "CONCENTRATION_RISK" in flags

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_flag_stale_oracle(self):
        """Flag when oracle data is stale."""
        from fractional_reserve import calculate_risk_flags

        data = {
            "backing_ratio_pct": 105.0,
            "overall_utilization_pct": 10.0,
            "oracle_staleness_seconds": 7200,  # 2 hours, above threshold
            "asset_allocations": []
        }

        thresholds = {
            "min_backing_ratio_pct": 100,
            "max_utilization_pct": 80,
            "max_single_asset_pct": 70,
            "max_staleness_seconds": 3600
        }

        flags = calculate_risk_flags(data, thresholds)

        assert "ORACLE_STALE" in flags

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_multiple_risk_flags(self):
        """Can have multiple risk flags simultaneously."""
        from fractional_reserve import calculate_risk_flags

        data = {
            "backing_ratio_pct": 90.0,        # Under threshold
            "overall_utilization_pct": 90.0,  # Over threshold
            "oracle_staleness_seconds": 7200,  # Stale
            "asset_allocations": [
                {"symbol": "USDC", "allocation_pct": 100.0}  # Concentrated
            ]
        }

        thresholds = {
            "min_backing_ratio_pct": 100,
            "max_utilization_pct": 80,
            "max_single_asset_pct": 70,
            "max_staleness_seconds": 3600
        }

        flags = calculate_risk_flags(data, thresholds)

        assert len(flags) == 4
        assert "UNDERCOLLATERALIZED" in flags
        assert "HIGH_UTILIZATION" in flags
        assert "CONCENTRATION_RISK" in flags
        assert "ORACLE_STALE" in flags


class TestOraclePriceValidation:
    """Tests for oracle price validation."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_price_within_peg(self):
        """Price close to $1 is considered healthy."""
        from fractional_reserve import is_price_depegged

        price = 0.9997
        threshold_pct = 1.0  # 1% deviation allowed

        is_depegged = is_price_depegged(price, threshold_pct)

        assert is_depegged is False

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_price_depegged_low(self):
        """Price too far below $1 is flagged."""
        from fractional_reserve import is_price_depegged

        price = 0.95  # 5% below peg
        threshold_pct = 1.0

        is_depegged = is_price_depegged(price, threshold_pct)

        assert is_depegged is True

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_price_depegged_high(self):
        """Price too far above $1 is flagged."""
        from fractional_reserve import is_price_depegged

        price = 1.05  # 5% above peg
        threshold_pct = 1.0

        is_depegged = is_price_depegged(price, threshold_pct)

        assert is_depegged is True

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_price_exactly_one(self):
        """Price exactly $1 is healthy."""
        from fractional_reserve import is_price_depegged

        price = 1.0
        threshold_pct = 1.0

        is_depegged = is_price_depegged(price, threshold_pct)

        assert is_depegged is False


class TestAssetAllocationCalculation:
    """Tests for asset allocation percentage calculations."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_allocation_single_asset(self):
        """Single asset should be 100% allocation."""
        from fractional_reserve import calculate_asset_allocations

        assets = [
            {"symbol": "USDC", "total_supplies": 100_000_000.0}
        ]

        allocations = calculate_asset_allocations(assets)

        assert len(allocations) == 1
        assert allocations[0]["allocation_pct"] == 100.0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_allocation_multiple_assets(self):
        """Multiple assets should sum to 100%."""
        from fractional_reserve import calculate_asset_allocations

        assets = [
            {"symbol": "USDC", "total_supplies": 60_000_000.0},
            {"symbol": "USDT", "total_supplies": 40_000_000.0}
        ]

        allocations = calculate_asset_allocations(assets)

        total_allocation = sum(a["allocation_pct"] for a in allocations)
        assert abs(total_allocation - 100.0) < 0.01

        usdc_alloc = next(a for a in allocations if a["symbol"] == "USDC")
        assert abs(usdc_alloc["allocation_pct"] - 60.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_allocation_zero_total(self):
        """Handle zero total supplies gracefully."""
        from fractional_reserve import calculate_asset_allocations

        assets = [
            {"symbol": "USDC", "total_supplies": 0.0},
            {"symbol": "USDT", "total_supplies": 0.0}
        ]

        allocations = calculate_asset_allocations(assets)

        # When total is 0, allocations should be 0 or evenly distributed
        for alloc in allocations:
            assert alloc["allocation_pct"] >= 0.0


class TestResultStructure:
    """Tests for the result data structure."""

    @pytest.mark.unit
    def test_result_has_required_fields(self, mock_fractional_reserve_data):
        """Result should contain all required fields."""
        required_fields = [
            "status",
            "total_supply",
            "backing_assets",
            "total_reserves_usd",
            "backing_ratio_pct",
            "overall_utilization_pct",
            "oracle_price",
            "is_fully_backed",
            "risk_flags"
        ]

        for field in required_fields:
            assert field in mock_fractional_reserve_data

    @pytest.mark.unit
    def test_backing_asset_structure(self, mock_fractional_reserve_data):
        """Each backing asset should have required fields."""
        required_asset_fields = [
            "symbol",
            "total_supplies",
            "total_borrows",
            "utilization_pct"
        ]

        for asset in mock_fractional_reserve_data["backing_assets"]:
            for field in required_asset_fields:
                assert field in asset

    @pytest.mark.unit
    def test_is_fully_backed_logic(self, mock_fractional_reserve_data, mock_fractional_reserve_healthy):
        """is_fully_backed should reflect backing ratio."""
        # Under-collateralized
        assert mock_fractional_reserve_data["is_fully_backed"] is False
        assert mock_fractional_reserve_data["backing_ratio_pct"] < 100.0

        # Over-collateralized
        assert mock_fractional_reserve_healthy["is_fully_backed"] is True
        assert mock_fractional_reserve_healthy["backing_ratio_pct"] >= 100.0


class TestEdgeCases:
    """Edge case handling tests."""

    @pytest.mark.unit
    def test_negative_values_handled(self):
        """Should handle negative values safely."""
        from fractional_reserve import calculate_backing_ratio, calculate_utilization

        # Negative values shouldn't crash
        ratio = calculate_backing_ratio(-100, 100)
        assert ratio <= 0 or ratio >= 0  # Just shouldn't crash

        util = calculate_utilization(-10, 100)
        assert util <= 0 or util >= 0

    @pytest.mark.unit
    def test_very_large_values(self):
        """Should handle very large values."""
        from fractional_reserve import calculate_backing_ratio

        large_supply = 1_000_000_000_000_000.0  # 1 quadrillion
        large_reserves = 1_000_000_000_000_000.0

        ratio = calculate_backing_ratio(large_reserves, large_supply)

        assert ratio == 100.0

    @pytest.mark.unit
    def test_very_small_values(self):
        """Should handle very small (dust) values."""
        from fractional_reserve import calculate_backing_ratio

        tiny_supply = 0.000001
        tiny_reserves = 0.000001

        ratio = calculate_backing_ratio(tiny_reserves, tiny_supply)

        assert ratio == 100.0

    @pytest.mark.unit
    def test_empty_asset_list(self):
        """Should handle empty asset list."""
        from fractional_reserve import calculate_asset_allocations

        assets = []
        allocations = calculate_asset_allocations(assets)

        assert allocations == []
