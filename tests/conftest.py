"""
Pytest configuration and fixtures for DeFi Risk Assessment Framework.

This file contains shared fixtures used across all test modules.
Fixtures follow the pattern: factory functions with auto-cleanup.
"""

import pytest
import json
import os
from pathlib import Path
from typing import Dict, Any, Generator
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# =============================================================================
# PATH FIXTURES
# =============================================================================

@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def config_dir(project_root: Path) -> Path:
    """Return the directory containing example config files."""
    return project_root


# =============================================================================
# CONFIG FIXTURES
# =============================================================================

@pytest.fixture
def sample_wsteth_config(project_root: Path) -> Dict[str, Any]:
    """Load the wstETH example configuration."""
    config_path = project_root / "example_wsteth_config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    # Convert deployment_date string to datetime
    if "deployment_date" in config and isinstance(config["deployment_date"], str):
        config["deployment_date"] = datetime.fromisoformat(config["deployment_date"]).replace(tzinfo=timezone.utc)
    # Convert multisig_configs from list to dict (keyed by role_name)
    if "multisig_configs" in config and isinstance(config["multisig_configs"], list):
        config["multisig_configs"] = {
            item.get("role_name", f"role_{i}"): item
            for i, item in enumerate(config["multisig_configs"])
        }
    return config


@pytest.fixture
def sample_cbbtc_config(project_root: Path) -> Dict[str, Any]:
    """Load the cbBTC example configuration."""
    config_path = project_root / "example_cbbtc_config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    # Convert deployment_date string to datetime
    if "deployment_date" in config and isinstance(config["deployment_date"], str):
        config["deployment_date"] = datetime.fromisoformat(config["deployment_date"]).replace(tzinfo=timezone.utc)
    # Convert multisig_configs from list to dict (keyed by role_name)
    if "multisig_configs" in config and isinstance(config["multisig_configs"], list):
        config["multisig_configs"] = {
            item.get("role_name", f"role_{i}"): item
            for i, item in enumerate(config["multisig_configs"])
        }
    return config


@pytest.fixture
def minimal_config() -> Dict[str, Any]:
    """
    Minimal valid configuration for unit testing.
    Contains only required fields with sensible defaults.
    """
    return {
        "asset_name": "Test Asset",
        "asset_symbol": "TEST",
        "asset_type": "wrapped_btc",
        "underlying": "BTC",
        "token_decimals": 8,
        "token_addresses": [
            {"chain": "ethereum", "address": "0x" + "a" * 40}
        ],
        "audit_data": {
            "auditors": ["TestAuditor"],
            "total_audits": {"main": 1}
        },
        "deployment_date": datetime(2023, 1, 1, tzinfo=timezone.utc),
        "incidents": [],
        "multisig_configs": {
            "owner": {
                "role_name": "owner",
                "is_multisig": True,
                "threshold": 3,
                "owners_count": 5
            }
        },
        "has_timelock": True,
        "timelock_hours": 48,
        "custody_model": "regulated_insured",
        "has_blacklist": False
    }


@pytest.fixture
def config_factory():
    """
    Factory fixture for creating custom configurations.

    Usage:
        def test_something(config_factory):
            config = config_factory(asset_type="liquid_staking", has_audit=False)
    """
    def _create_config(**overrides) -> Dict[str, Any]:
        base = {
            "asset_name": "Factory Asset",
            "asset_symbol": "FACT",
            "asset_type": "wrapped_btc",
            "underlying": "BTC",
            "token_decimals": 8,
            "token_addresses": [
                {"chain": "ethereum", "address": "0x" + "b" * 40}
            ],
            "audit_data": {
                "auditors": ["FactoryAuditor"],
                "total_audits": {"main": 1}
            },
            "deployment_date": datetime(2023, 6, 1, tzinfo=timezone.utc),
            "incidents": [],
            "multisig_configs": {},
            "has_timelock": False,
            "timelock_hours": 0,
            "custody_model": "unknown",
            "has_blacklist": False
        }

        # Deep merge overrides
        for key, value in overrides.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                base[key].update(value)
            else:
                base[key] = value

        return base

    return _create_config


# =============================================================================
# SCORING FIXTURES
# =============================================================================

@pytest.fixture
def passing_primary_checks_metrics() -> Dict[str, Any]:
    """
    Metrics that will pass all primary checks.
    Use this when you want to test secondary scoring.
    """
    return {
        "audit_data": {
            "auditors": ["OpenZeppelin", "Trail of Bits"],
            "total_audits": {"main": 5},
            "latest_protocol_audit": {
                "auditor": "OpenZeppelin",
                "date": "2024-01-01",
                "issues": {"critical": 0, "high": 0, "medium": 2},
                "unresolved": {"critical": 0, "high": 0}
            }
        },
        "incidents": []  # No recent incidents
    }


@pytest.fixture
def failing_audit_metrics() -> Dict[str, Any]:
    """Metrics that will fail the 'has security audit' check."""
    return {
        "audit_data": None,
        "incidents": []
    }


@pytest.fixture
def failing_critical_issues_metrics() -> Dict[str, Any]:
    """Metrics that will fail the 'no critical issues' check."""
    return {
        "audit_data": {
            "auditors": ["SomeAuditor"],
            "latest_protocol_audit": {
                "issues": {"critical": 2, "high": 1},
                "unresolved": {"critical": 2}
            }
        },
        "incidents": []
    }


# =============================================================================
# MOCK FIXTURES FOR EXTERNAL APIS
# =============================================================================

@pytest.fixture
def mock_web3():
    """Mock Web3 instance for testing without blockchain connection."""
    mock = MagicMock()
    mock.eth.contract.return_value = MagicMock()
    mock.is_connected.return_value = True
    return mock


@pytest.fixture
def mock_coingecko_response() -> Dict[str, Any]:
    """Sample CoinGecko API response for price risk testing."""
    return {
        "prices": [
            [1704067200000, 2300.50],  # timestamp, price
            [1704153600000, 2315.75],
            [1704240000000, 2298.00],
            [1704326400000, 2342.25],
            [1704412800000, 2380.00],
        ],
        "market_caps": [],
        "total_volumes": []
    }


@pytest.fixture
def mock_requests_get(mock_coingecko_response):
    """
    Mock requests.get for API testing.

    Usage:
        def test_price_fetching(mock_requests_get):
            # requests.get is already mocked
            result = fetch_price_data("ethereum")
    """
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_coingecko_response
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_aave_data() -> Dict[str, Any]:
    """Sample Aave market data for testing."""
    return {
        "chain": "ethereum",
        "protocol": "aave",
        "tvl": 1_500_000_000,  # $1.5B
        "utilization": 0.65,  # 65%
        "supply_apy": 0.025,  # 2.5%
        "borrow_apy": 0.045,  # 4.5%
        "ltv": 0.80,
        "liquidation_threshold": 0.825,
        "rlr": 0.08,  # Recursive lending ratio
        "clr": 0.03,  # Cascade liquidation risk
    }


@pytest.fixture
def mock_dex_pool_data() -> Dict[str, Any]:
    """Sample DEX pool data for testing."""
    return {
        "protocol": "uniswap",
        "chain": "ethereum",
        "tvl": 250_000_000,  # $250M
        "volume_24h": 15_000_000,  # $15M
        "fee_tier": 0.0001,  # 0.01%
        "token0_reserve": 50000,
        "token1_reserve": 115000000,  # ~$2300 price
        "hhi": 1200,  # LP concentration
    }


# =============================================================================
# THRESHOLD FIXTURES
# =============================================================================

@pytest.fixture
def grade_boundaries() -> Dict[str, tuple]:
    """Expected grade boundaries for validation."""
    return {
        "A": (85, 100),
        "B": (70, 84),
        "C": (55, 69),
        "D": (40, 54),
        "F": (0, 39),
    }


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def reset_module_state():
    """
    Auto-cleanup fixture that resets any module-level state after each test.
    This ensures test isolation.
    """
    yield
    # Add cleanup logic here if modules have global state


# =============================================================================
# PARAMETRIZE HELPERS
# =============================================================================

# Common test scenarios for parametrized tests
CUSTODY_MODELS = ["decentralized", "regulated_insured", "regulated", "unregulated", "unknown"]
ASSET_TYPES = ["wrapped_btc", "liquid_staking", "stablecoin", "synthetic"]
CHAINS = ["ethereum", "base", "arbitrum", "polygon", "optimism"]
