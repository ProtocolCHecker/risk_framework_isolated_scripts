# Test Suite Documentation

> DeFi Risk Assessment Framework - Testing Guide

## Overview

This test suite provides comprehensive coverage for the DeFi Risk Assessment Framework, including:

- **Unit tests** for the scoring engine (`primary_checks`, `asset_score`, `thresholds`)
- **Integration tests** for data fetchers with mocked external APIs

## Quick Start

### Install Test Dependencies

```bash
# Activate virtual environment
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-cov pytest-asyncio pytest-timeout faker
```

### Run All Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=. --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only (fast, no external dependencies)
pytest -m unit

# Integration tests only
pytest -m integration

# Scoring engine tests
pytest -m scoring

# Data fetcher tests
pytest -m fetcher

# Smoke tests (critical path)
pytest -m smoke
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── README.md                # This file
│
├── unit/                    # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── test_primary_checks.py    # Primary qualification checks
│   ├── test_asset_score.py       # Scoring engine
│   └── test_thresholds.py        # Threshold definitions
│
├── integration/             # Integration tests (mocked APIs)
│   ├── __init__.py
│   ├── test_price_risk.py        # CoinGecko integration
│   └── test_data_fetchers.py     # All data fetcher modules
│
└── fixtures/                # Test data factories
    └── __init__.py
```

## Test Markers

| Marker | Description | Speed |
|--------|-------------|-------|
| `@pytest.mark.unit` | Isolated unit tests | Fast |
| `@pytest.mark.integration` | Tests with mocked external APIs | Medium |
| `@pytest.mark.slow` | Tests taking >5 seconds | Slow |
| `@pytest.mark.smoke` | Critical path tests | Fast |
| `@pytest.mark.scoring` | Scoring engine tests | Fast |
| `@pytest.mark.fetcher` | Data fetcher tests | Medium |

## Fixtures

### Configuration Fixtures

| Fixture | Description |
|---------|-------------|
| `sample_wsteth_config` | Full wstETH configuration |
| `sample_cbbtc_config` | Full cbBTC configuration |
| `minimal_config` | Minimal valid configuration |
| `config_factory` | Factory for custom configs |

### Scoring Fixtures

| Fixture | Description |
|---------|-------------|
| `passing_primary_checks_metrics` | Metrics that pass all primary checks |
| `failing_audit_metrics` | Metrics that fail audit check |
| `failing_critical_issues_metrics` | Metrics with unresolved critical issues |
| `grade_boundaries` | Expected grade score boundaries |

### Mock Fixtures

| Fixture | Description |
|---------|-------------|
| `mock_web3` | Mocked Web3 instance |
| `mock_coingecko_response` | Sample CoinGecko API response |
| `mock_requests_get` | Mocked requests.get |
| `mock_aave_data` | Sample Aave market data |
| `mock_dex_pool_data` | Sample DEX pool data |

## Writing Tests

### Unit Test Example

```python
import pytest
from primary_checks import check_has_security_audit, CheckStatus

class TestHasSecurityAudit:
    @pytest.mark.unit
    @pytest.mark.scoring
    def test_passes_with_audit_data(self, passing_primary_checks_metrics):
        result = check_has_security_audit(passing_primary_checks_metrics)
        assert result.status == CheckStatus.PASS
```

### Integration Test Example

```python
import pytest
from unittest.mock import patch

class TestPriceRisk:
    @pytest.mark.integration
    @pytest.mark.fetcher
    def test_handles_api_error(self):
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("API Error")
            result = get_coingecko_data("ethereum")
            assert result is None
```

### Using Config Factory

```python
def test_custom_config(config_factory):
    # Create config with specific overrides
    config = config_factory(
        asset_type="liquid_staking",
        custody_model="decentralized",
        has_timelock=True,
        timelock_hours=72
    )

    result = calculate_risk_score(config)
    assert result["grade"] in ["A", "B"]
```

## Coverage Goals

| Module | Target Coverage |
|--------|----------------|
| `primary_checks.py` | 90%+ |
| `asset_score.py` | 80%+ |
| `thresholds.py` | 70%+ |
| Data fetchers | 60%+ (mocked) |

## CI Integration

Add to your CI pipeline:

```yaml
# GitHub Actions example
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.13'
    - run: pip install -r requirements-test.txt
    - run: pytest --cov=. --cov-report=xml -m "not slow"
    - uses: codecov/codecov-action@v4
```

## Best Practices

1. **Isolate tests** - Each test should be independent
2. **Mock external calls** - Never hit real APIs in CI
3. **Use fixtures** - Avoid duplicating test data
4. **Mark tests** - Use markers for selective execution
5. **Test edge cases** - Include boundary conditions
6. **Keep tests fast** - Unit tests should run in <100ms each

## Troubleshooting

### Import Errors

If you see import errors, ensure the project root is in your Python path:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Missing Dependencies

Install all test dependencies:

```bash
pip install pytest pytest-cov pytest-asyncio pytest-timeout faker
```

### Flaky Tests

Tests that fail intermittently should be marked:

```python
@pytest.mark.flaky(reruns=3)
def test_sometimes_fails():
    ...
```

## Future Improvements

- [ ] Add property-based testing with Hypothesis
- [ ] Add Streamlit component tests
- [ ] Add load testing for data fetchers
- [ ] Add contract tests for external APIs (Pact)
