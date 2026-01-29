"""
Market Fetcher - Wrapper for price_risk.py functions.

Fetches market/price risk metrics including:
- Peg Deviation
- Volatility
- VaR (Value at Risk)
- CVaR (Conditional Value at Risk)
"""

import sys
import os
from typing import Dict, Any, List, Optional
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from price_risk import get_coingecko_data, calculate_metrics, calculate_peg_deviation
from monitoring.core.db import insert_metrics_batch


def fetch_price_risk_metrics(asset_config: Dict[str, Any], days: int = 365) -> Dict[str, Any]:
    """
    Fetch price risk metrics from CoinGecko.

    Args:
        asset_config: Asset configuration containing coingecko_id
        days: Number of days of historical data to analyze

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    coingecko_id = asset_config.get("coingecko_id")

    if not coingecko_id:
        result["error"] = "No coingecko_id configured"
        return result

    metrics = []

    try:
        # Fetch price data
        print(f"Fetching {days}-day price data for {symbol}...")
        timestamps, prices = get_coingecko_data(coingecko_id, days=days)

        if not prices or len(prices) < 30:
            result["error"] = f"Insufficient price data: {len(prices) if prices else 0} points"
            return result

        # Calculate risk metrics
        risk_metrics = calculate_metrics(prices)

        # Parse volatility (remove % and convert)
        volatility_str = risk_metrics.get("Annualized Volatility", "0%")
        volatility = float(volatility_str.replace("%", "")) / 100

        metrics.append({
            "asset_symbol": symbol,
            "metric_name": "volatility_annual",
            "value": volatility,
            "chain": None,
            "metadata": {
                "days_analyzed": days,
                "data_points": len(prices)
            }
        })

        # Parse VaR 95%
        var_95_str = risk_metrics.get("VaR 95%", "0%")
        var_95 = float(var_95_str.replace("%", "")) / 100

        metrics.append({
            "asset_symbol": symbol,
            "metric_name": "var_95",
            "value": var_95,
            "chain": None,
            "metadata": {
                "days_analyzed": days
            }
        })

        # Parse VaR 99%
        var_99_str = risk_metrics.get("VaR 99%", "0%")
        var_99 = float(var_99_str.replace("%", "")) / 100

        metrics.append({
            "asset_symbol": symbol,
            "metric_name": "var_99",
            "value": var_99,
            "chain": None,
            "metadata": {
                "days_analyzed": days
            }
        })

        # Parse CVaR metrics
        cvar_95_str = risk_metrics.get("CVaR 95%", "0%")
        cvar_95 = float(cvar_95_str.replace("%", "")) / 100

        metrics.append({
            "asset_symbol": symbol,
            "metric_name": "cvar_95",
            "value": cvar_95,
            "chain": None,
            "metadata": None
        })

        # Current price
        current_price = prices[-1] if prices else 0
        metrics.append({
            "asset_symbol": symbol,
            "metric_name": "current_price_usd",
            "value": current_price,
            "chain": None,
            "metadata": None
        })

        result["status"] = "success"
        result["metrics"] = metrics

    except Exception as e:
        result["error"] = f"Price fetch error: {str(e)}"

    return result


def fetch_peg_deviation(asset_config: Dict[str, Any], days: int = 365) -> Dict[str, Any]:
    """
    Fetch peg deviation metrics for pegged assets.

    Args:
        asset_config: Asset configuration containing coingecko_id and underlying_id
        days: Number of days of historical data

    Returns:
        Dict with status and peg deviation metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    coingecko_id = asset_config.get("coingecko_id")
    underlying_id = asset_config.get("underlying_coingecko_id")

    if not coingecko_id:
        result["error"] = "No coingecko_id configured"
        return result

    if not underlying_id:
        result["error"] = "No underlying_coingecko_id for peg comparison"
        return result

    metrics = []

    try:
        # Fetch both price series
        print(f"Fetching peg deviation data for {symbol} vs underlying...")
        _, token_prices = get_coingecko_data(coingecko_id, days=days)
        _, underlying_prices = get_coingecko_data(underlying_id, days=days)

        if not token_prices or not underlying_prices:
            result["error"] = "Failed to fetch price data"
            return result

        # Align lengths
        min_len = min(len(token_prices), len(underlying_prices))
        token_prices = token_prices[:min_len]
        underlying_prices = underlying_prices[:min_len]

        if min_len < 30:
            result["error"] = f"Insufficient data points: {min_len}"
            return result

        # Calculate peg deviation
        peg_metrics = calculate_peg_deviation(token_prices, underlying_prices)

        # Parse current deviation
        current_dev_str = peg_metrics.get("Current Deviation", "0%")
        current_deviation = float(current_dev_str.replace("%", ""))

        metrics.append({
            "asset_symbol": symbol,
            "metric_name": "peg_deviation_pct",
            "value": abs(current_deviation),  # Store absolute deviation
            "chain": None,
            "metadata": {
                "underlying": underlying_id,
                "direction": "premium" if current_deviation > 0 else "discount",
                "raw_deviation": current_deviation
            }
        })

        # Max deviation (historical)
        max_dev_str = peg_metrics.get("Max Deviation", "0%")
        max_deviation = float(max_dev_str.replace("%", ""))

        metrics.append({
            "asset_symbol": symbol,
            "metric_name": "peg_max_deviation_pct",
            "value": abs(max_deviation),
            "chain": None,
            "metadata": {
                "days_analyzed": days
            }
        })

        # Standard deviation of peg
        std_dev_str = peg_metrics.get("Std Dev of Deviation", "0%")
        std_deviation = float(std_dev_str.replace("%", ""))

        metrics.append({
            "asset_symbol": symbol,
            "metric_name": "peg_std_deviation",
            "value": std_deviation,
            "chain": None,
            "metadata": None
        })

        result["status"] = "success"
        result["metrics"] = metrics

    except Exception as e:
        result["error"] = f"Peg deviation fetch error: {str(e)}"

    return result


def fetch_all_market_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch all market/price risk metrics for an asset.

    Args:
        asset_config: Asset configuration

    Returns:
        Dict with combined market metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    all_metrics = []

    # Fetch price risk metrics
    risk_result = fetch_price_risk_metrics(asset_config)
    if risk_result.get("status") == "success":
        all_metrics.extend(risk_result.get("metrics", []))

    # Fetch peg deviation if underlying is configured
    if asset_config.get("underlying_coingecko_id"):
        peg_result = fetch_peg_deviation(asset_config)
        if peg_result.get("status") == "success":
            all_metrics.extend(peg_result.get("metrics", []))

    if all_metrics:
        result["status"] = "success"
        result["metrics"] = all_metrics
    else:
        errors = []
        if risk_result.get("error"):
            errors.append(risk_result["error"])
        result["error"] = "; ".join(errors) if errors else "No market data"

    return result


def fetch_and_store_market_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch market metrics and store to database.

    Args:
        asset_config: Asset configuration

    Returns:
        Dict with status and count of stored metrics
    """
    result = {
        "status": "error",
        "metrics_stored": 0,
        "error": None
    }

    market_result = fetch_all_market_metrics(asset_config)

    if market_result.get("status") == "success":
        metrics = market_result.get("metrics", [])
        if metrics:
            try:
                count = insert_metrics_batch(metrics)
                result["status"] = "success"
                result["metrics_stored"] = count
            except Exception as e:
                result["error"] = f"Database insert failed: {str(e)}"
    else:
        result["error"] = market_result.get("error", "No metrics to store")

    return result


if __name__ == "__main__":
    # Test with example config
    test_config = {
        "asset_symbol": "wstETH",
        "coingecko_id": "wrapped-steth",
        "underlying_coingecko_id": "ethereum"
    }

    print("Testing market fetcher...")
    result = fetch_all_market_metrics(test_config)
    print(f"Status: {result['status']}")
    print(f"Metrics: {len(result.get('metrics', []))}")
    for m in result.get("metrics", []):
        print(f"  - {m['metric_name']}: {m['value']}")
    if result.get("error"):
        print(f"Error: {result['error']}")
