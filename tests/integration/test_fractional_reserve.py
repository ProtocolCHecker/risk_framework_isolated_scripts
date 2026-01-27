"""
Integration tests for fractional_reserve module.

Tests the external integrations (Web3 calls, oracle queries) with mocked responses.
These tests verify that the fetcher handles various response scenarios correctly.
"""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestFractionalReserveFetcher:
    """Integration tests for the main fetcher function."""

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_fetch_returns_expected_structure(
        self,
        fractional_reserve_por_config,
        mock_vault_contract,
        mock_oracle_contract
    ):
        """Fetcher should return properly structured data."""
        from fractional_reserve import fetch_fractional_reserve_data

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.is_connected.return_value = True

            # Configure contract returns
            def get_contract(address, abi):
                if "totalSupply" in str(abi) and "totalSupplies" not in str(abi):
                    # Token contract
                    return mock_vault_contract
                elif "latestRoundData" in str(abi):
                    # Oracle contract
                    return mock_oracle_contract
                else:
                    # Vault contract
                    return mock_vault_contract

            mock_w3.eth.contract = MagicMock(side_effect=get_contract)
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()
            MockWeb3.to_checksum_address = lambda x: x

            rpc_urls = {"ethereum": "https://fake-rpc.com"}

            result = fetch_fractional_reserve_data(fractional_reserve_por_config, rpc_urls)

            # Verify structure
            assert "status" in result
            assert "total_supply" in result
            assert "backing_assets" in result
            assert "backing_ratio_pct" in result
            assert "overall_utilization_pct" in result
            assert "risk_flags" in result

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_handles_rpc_connection_failure(self, fractional_reserve_por_config):
        """Should handle RPC connection failures gracefully."""
        from fractional_reserve import fetch_fractional_reserve_data

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.is_connected.return_value = False
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()

            rpc_urls = {"ethereum": "https://fake-rpc.com"}

            result = fetch_fractional_reserve_data(fractional_reserve_por_config, rpc_urls)

            assert result["status"] == "error"
            assert "error" in result

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_handles_missing_rpc_url(self, fractional_reserve_por_config):
        """Should handle missing RPC URL gracefully."""
        from fractional_reserve import fetch_fractional_reserve_data

        rpc_urls = {}  # No ethereum RPC

        result = fetch_fractional_reserve_data(fractional_reserve_por_config, rpc_urls)

        assert result["status"] == "error"
        assert "error" in result

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_handles_contract_call_failure(self, fractional_reserve_por_config):
        """Should handle contract call failures gracefully."""
        from fractional_reserve import fetch_fractional_reserve_data

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.is_connected.return_value = True

            # Contract that raises on call
            mock_contract = MagicMock()
            mock_contract.functions.totalSupply.return_value.call.side_effect = Exception("Contract error")

            mock_w3.eth.contract.return_value = mock_contract
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()
            MockWeb3.to_checksum_address = lambda x: x

            rpc_urls = {"ethereum": "https://fake-rpc.com"}

            result = fetch_fractional_reserve_data(fractional_reserve_por_config, rpc_urls)

            # Should return error status, not crash
            assert result["status"] == "error"


class TestVaultQueries:
    """Tests for vault contract queries."""

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_query_total_supply(self, mock_vault_contract):
        """Should correctly query and parse total supply."""
        from fractional_reserve import query_total_supply

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.eth.contract.return_value = mock_vault_contract
            MockWeb3.to_checksum_address = lambda x: x

            vault_address = "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC"
            decimals = 18

            supply = query_total_supply(mock_w3, vault_address, decimals)

            assert supply == 443_000_000.0

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_query_asset_supplies(self, mock_vault_contract):
        """Should correctly query totalSupplies for an asset."""
        from fractional_reserve import query_asset_supplies

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.eth.contract.return_value = mock_vault_contract
            MockWeb3.to_checksum_address = lambda x: x

            vault_address = "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC"
            asset_address = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
            decimals = 6

            supplies = query_asset_supplies(mock_w3, vault_address, asset_address, decimals)

            assert supplies == 438_000_000.0

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_query_asset_borrows(self, mock_vault_contract):
        """Should correctly query totalBorrows for an asset."""
        from fractional_reserve import query_asset_borrows

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.eth.contract.return_value = mock_vault_contract
            MockWeb3.to_checksum_address = lambda x: x

            vault_address = "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC"
            asset_address = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
            decimals = 6

            borrows = query_asset_borrows(mock_w3, vault_address, asset_address, decimals)

            assert borrows == 20_000_000.0


class TestOracleQueries:
    """Tests for oracle contract queries."""

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_query_oracle_price(self, mock_oracle_contract):
        """Should correctly query and parse oracle price."""
        from fractional_reserve import query_oracle_price

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.eth.contract.return_value = mock_oracle_contract
            MockWeb3.to_checksum_address = lambda x: x

            oracle_address = "0x9A5a3c3Ed0361505cC1D4e824B3854De5724434A"
            decimals = 8

            price, timestamp = query_oracle_price(mock_w3, oracle_address, decimals)

            assert abs(price - 0.9997) < 0.0001
            assert timestamp > 0

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_detect_stale_oracle(self, mock_oracle_stale):
        """Should detect when oracle data is stale."""
        from fractional_reserve import query_oracle_price, is_oracle_stale

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.eth.contract.return_value = mock_oracle_stale
            MockWeb3.to_checksum_address = lambda x: x

            oracle_address = "0x9A5a3c3Ed0361505cC1D4e824B3854De5724434A"
            decimals = 8
            max_staleness = 3600  # 1 hour

            price, timestamp = query_oracle_price(mock_w3, oracle_address, decimals)
            staleness_seconds = int(time.time()) - timestamp

            is_stale = is_oracle_stale(staleness_seconds, max_staleness)

            assert is_stale is True

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_fresh_oracle_not_stale(self, mock_oracle_contract):
        """Fresh oracle should not be flagged as stale."""
        from fractional_reserve import query_oracle_price, is_oracle_stale

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.eth.contract.return_value = mock_oracle_contract
            MockWeb3.to_checksum_address = lambda x: x

            oracle_address = "0x9A5a3c3Ed0361505cC1D4e824B3854De5724434A"
            decimals = 8
            max_staleness = 3600

            price, timestamp = query_oracle_price(mock_w3, oracle_address, decimals)
            staleness_seconds = int(time.time()) - timestamp

            is_stale = is_oracle_stale(staleness_seconds, max_staleness)

            assert is_stale is False


class TestConfigValidation:
    """Tests for configuration validation."""

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_validates_required_config_fields(self):
        """Should validate required configuration fields."""
        from fractional_reserve import validate_config

        # Valid config
        valid_config = {
            "verification_type": "fractional_reserve",
            "vault_address": "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC",
            "chain": "ethereum",
            "backing_assets": [
                {"symbol": "USDC", "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "decimals": 6}
            ]
        }

        is_valid, error = validate_config(valid_config)
        assert is_valid is True
        assert error is None

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_rejects_missing_vault_address(self):
        """Should reject config missing vault address."""
        from fractional_reserve import validate_config

        invalid_config = {
            "verification_type": "fractional_reserve",
            "chain": "ethereum",
            "backing_assets": []
        }

        is_valid, error = validate_config(invalid_config)
        assert is_valid is False
        assert "vault_address" in error.lower()

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_rejects_empty_backing_assets(self):
        """Should reject config with no backing assets."""
        from fractional_reserve import validate_config

        invalid_config = {
            "verification_type": "fractional_reserve",
            "vault_address": "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC",
            "chain": "ethereum",
            "backing_assets": []
        }

        is_valid, error = validate_config(invalid_config)
        assert is_valid is False
        assert "backing_assets" in error.lower()


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_healthy_reserve_scenario(self):
        """Test a healthy reserve state produces expected results."""
        from fractional_reserve import (
            calculate_backing_ratio,
            calculate_utilization,
            calculate_risk_flags
        )

        # Simulate healthy state
        total_supply = 100_000_000.0
        total_reserves = 110_000_000.0  # 110% backed
        total_borrows = 5_000_000.0     # 4.5% utilization

        backing_ratio = calculate_backing_ratio(total_reserves, total_supply)
        utilization = calculate_utilization(total_borrows, total_reserves)

        data = {
            "backing_ratio_pct": backing_ratio,
            "overall_utilization_pct": utilization,
            "oracle_staleness_seconds": 300,
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

        assert abs(backing_ratio - 110.0) < 0.01
        assert utilization < 10.0
        assert len(flags) == 0

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_stressed_reserve_scenario(self):
        """Test a stressed reserve state produces expected warnings."""
        from fractional_reserve import (
            calculate_backing_ratio,
            calculate_utilization,
            calculate_risk_flags
        )

        # Simulate stressed state
        total_supply = 100_000_000.0
        total_reserves = 90_000_000.0   # 90% backed (undercollateralized)
        total_borrows = 80_000_000.0    # 89% utilization (high)

        backing_ratio = calculate_backing_ratio(total_reserves, total_supply)
        utilization = calculate_utilization(total_borrows, total_reserves)

        data = {
            "backing_ratio_pct": backing_ratio,
            "overall_utilization_pct": utilization,
            "oracle_staleness_seconds": 300,
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

        assert backing_ratio == 90.0
        assert utilization > 80.0
        assert "UNDERCOLLATERALIZED" in flags
        assert "HIGH_UTILIZATION" in flags
        assert "CONCENTRATION_RISK" in flags


class TestErrorRecovery:
    """Tests for error recovery and resilience."""

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_partial_asset_failure(self, fractional_reserve_por_config):
        """Should continue processing if one asset query fails."""
        from fractional_reserve import fetch_fractional_reserve_data

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.is_connected.return_value = True

            call_count = [0]

            def mock_contract_call(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 2:  # Fail on second asset
                    raise Exception("Asset query failed")
                return 100_000_000 * 10**6

            mock_contract = MagicMock()
            mock_contract.functions.totalSupply.return_value.call.return_value = 100_000_000 * 10**18
            mock_contract.functions.totalSupplies.return_value.call = mock_contract_call
            mock_contract.functions.totalBorrows.return_value.call.return_value = 5_000_000 * 10**6

            mock_oracle = MagicMock()
            mock_oracle.functions.latestRoundData.return_value.call.return_value = (
                1, 99970000, int(time.time()), int(time.time()), 1
            )

            def get_contract(address, abi):
                if "latestRoundData" in str(abi):
                    return mock_oracle
                return mock_contract

            mock_w3.eth.contract = MagicMock(side_effect=get_contract)
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()
            MockWeb3.to_checksum_address = lambda x: x

            rpc_urls = {"ethereum": "https://fake-rpc.com"}

            result = fetch_fractional_reserve_data(fractional_reserve_por_config, rpc_urls)

            # Should still return partial results or handle gracefully
            assert result is not None
            # Status could be "success" with partial data or "partial_error"

    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_oracle_failure_uses_fallback(self, fractional_reserve_por_config):
        """Should handle oracle failure gracefully."""
        from fractional_reserve import fetch_fractional_reserve_data

        with patch("web3.Web3") as MockWeb3:
            mock_w3 = MagicMock()
            mock_w3.is_connected.return_value = True

            mock_vault = MagicMock()
            mock_vault.functions.totalSupply.return_value.call.return_value = 100_000_000 * 10**18
            mock_vault.functions.totalSupplies.return_value.call.return_value = 100_000_000 * 10**6
            mock_vault.functions.totalBorrows.return_value.call.return_value = 5_000_000 * 10**6

            mock_oracle = MagicMock()
            mock_oracle.functions.latestRoundData.return_value.call.side_effect = Exception("Oracle down")

            def get_contract(address, abi):
                if "latestRoundData" in str(abi):
                    return mock_oracle
                return mock_vault

            mock_w3.eth.contract = MagicMock(side_effect=get_contract)
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()
            MockWeb3.to_checksum_address = lambda x: x

            rpc_urls = {"ethereum": "https://fake-rpc.com"}

            result = fetch_fractional_reserve_data(fractional_reserve_por_config, rpc_urls)

            # Should still return data, with oracle_price as None or 0
            assert result is not None
            # Oracle failure should be reflected in result
            assert result.get("oracle_price") is None or result.get("oracle_price") == 0 or "ORACLE" in str(result.get("risk_flags", []))
