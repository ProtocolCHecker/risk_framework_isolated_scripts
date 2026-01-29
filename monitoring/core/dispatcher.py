"""
Metric Dispatcher - Routes assets to appropriate fetchers by frequency category.

Frequency Categories:
- Critical (5 min): PoR ratio, oracle freshness, peg deviation
- High (30 min): TVL, utilization, slippage
- Medium (6 hr): HHI, Gini, CLR, RLR, supply
- Daily (24 hr): Volatility, VaR
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.registry import AssetRegistry
from core.db import insert_metrics_batch
from core.alerts import check_alerts_for_metrics
from fetchers.oracle import fetch_oracle_freshness, fetch_cross_chain_oracle_lag
from fetchers.reserve import fetch_por_metrics
from fetchers.market import fetch_peg_deviation, fetch_price_risk_metrics
from fetchers.liquidity import fetch_slippage_metrics, fetch_pool_tvl
from fetchers.lending import fetch_all_lending_metrics
from fetchers.distribution import fetch_distribution_metrics


def dispatch_critical(asset_configs: List[Dict] = None) -> Dict[str, Any]:
    """
    Dispatch critical frequency metrics (5 min interval).

    Metrics: PoR ratio, oracle freshness, peg deviation

    Args:
        asset_configs: Optional list of asset configs. If None, fetches from registry.

    Returns:
        Dict with dispatch results
    """
    result = {
        "frequency": "critical",
        "timestamp": datetime.utcnow().isoformat(),
        "assets_processed": 0,
        "metrics_collected": 0,
        "alerts_triggered": 0,
        "errors": []
    }

    # Get assets from registry if not provided
    if asset_configs is None:
        assets = AssetRegistry.get_all_assets(enabled_only=True)
        asset_configs = [a['config'] for a in assets]

    all_metrics = []

    for config in asset_configs:
        symbol = config.get("asset_symbol", "UNKNOWN")
        result["assets_processed"] += 1

        try:
            # Oracle freshness
            if config.get("oracles") or config.get("oracle_freshness"):
                # Normalize config for fetcher
                oracle_config = _normalize_oracle_config(config)
                oracle_result = fetch_oracle_freshness(oracle_config)
                if oracle_result.get("status") == "success":
                    all_metrics.extend(oracle_result.get("metrics", []))

            # PoR ratio
            if config.get("proof_of_reserve"):
                por_result = fetch_por_metrics(config)
                if por_result.get("status") == "success":
                    all_metrics.extend(por_result.get("metrics", []))

            # Peg deviation (for pegged assets)
            if config.get("underlying_coingecko_id") or config.get("price_risk", {}).get("underlying_coingecko_id"):
                peg_config = _normalize_market_config(config)
                peg_result = fetch_peg_deviation(peg_config, days=30)
                if peg_result.get("status") == "success":
                    # Only keep current peg deviation for critical
                    peg_metrics = [m for m in peg_result.get("metrics", [])
                                   if m["metric_name"] == "peg_deviation_pct"]
                    all_metrics.extend(peg_metrics)

        except Exception as e:
            result["errors"].append(f"{symbol}: {str(e)}")

    # Store metrics
    if all_metrics:
        try:
            count = insert_metrics_batch(all_metrics)
            result["metrics_collected"] = count

            # Check alerts
            alerts = check_alerts_for_metrics(all_metrics)
            result["alerts_triggered"] = len(alerts)

        except Exception as e:
            result["errors"].append(f"DB insert error: {str(e)}")

    return result


def dispatch_high(asset_configs: List[Dict] = None) -> Dict[str, Any]:
    """
    Dispatch high frequency metrics (30 min interval).

    Metrics: Pool TVL, utilization rate, slippage

    Args:
        asset_configs: Optional list of asset configs.

    Returns:
        Dict with dispatch results
    """
    result = {
        "frequency": "high",
        "timestamp": datetime.utcnow().isoformat(),
        "assets_processed": 0,
        "metrics_collected": 0,
        "alerts_triggered": 0,
        "errors": []
    }

    if asset_configs is None:
        assets = AssetRegistry.get_all_assets(enabled_only=True)
        asset_configs = [a['config'] for a in assets]

    all_metrics = []

    for config in asset_configs:
        symbol = config.get("asset_symbol", "UNKNOWN")
        result["assets_processed"] += 1

        try:
            # Pool TVL
            if config.get("dex_pools"):
                tvl_config = _normalize_dex_config(config)
                tvl_result = fetch_pool_tvl(tvl_config)
                if tvl_result.get("status") == "success":
                    all_metrics.extend(tvl_result.get("metrics", []))

            # Slippage
            if config.get("dex_pools"):
                slippage_config = _normalize_dex_config(config)
                slippage_result = fetch_slippage_metrics(slippage_config)
                if slippage_result.get("status") == "success":
                    all_metrics.extend(slippage_result.get("metrics", []))

            # Utilization (from lending markets)
            if config.get("lending_markets") or config.get("lending_configs"):
                lending_config = _normalize_lending_config(config)
                lending_result = fetch_all_lending_metrics(lending_config)
                if lending_result.get("status") == "success":
                    # Only keep utilization for high frequency
                    util_metrics = [m for m in lending_result.get("metrics", [])
                                    if m["metric_name"] == "utilization_rate"]
                    all_metrics.extend(util_metrics)

        except Exception as e:
            result["errors"].append(f"{symbol}: {str(e)}")

    if all_metrics:
        try:
            count = insert_metrics_batch(all_metrics)
            result["metrics_collected"] = count

            alerts = check_alerts_for_metrics(all_metrics)
            result["alerts_triggered"] = len(alerts)

        except Exception as e:
            result["errors"].append(f"DB insert error: {str(e)}")

    return result


def dispatch_medium(asset_configs: List[Dict] = None) -> Dict[str, Any]:
    """
    Dispatch medium frequency metrics (6 hr interval).

    Metrics: HHI, Gini, CLR, RLR, total supply

    Args:
        asset_configs: Optional list of asset configs.

    Returns:
        Dict with dispatch results
    """
    result = {
        "frequency": "medium",
        "timestamp": datetime.utcnow().isoformat(),
        "assets_processed": 0,
        "metrics_collected": 0,
        "alerts_triggered": 0,
        "errors": []
    }

    if asset_configs is None:
        assets = AssetRegistry.get_all_assets(enabled_only=True)
        asset_configs = [a['config'] for a in assets]

    all_metrics = []

    for config in asset_configs:
        symbol = config.get("asset_symbol", "UNKNOWN")
        result["assets_processed"] += 1

        try:
            # Distribution metrics (HHI, Gini, supply)
            if config.get("chains") or config.get("token_addresses"):
                dist_config = _normalize_distribution_config(config)
                dist_result = fetch_distribution_metrics(dist_config)
                if dist_result.get("status") == "success":
                    all_metrics.extend(dist_result.get("metrics", []))

            # CLR and RLR (from lending markets)
            if config.get("lending_markets") or config.get("lending_configs"):
                lending_config = _normalize_lending_config(config)
                lending_result = fetch_all_lending_metrics(lending_config)
                if lending_result.get("status") == "success":
                    # Keep CLR, RLR, and lending supply/borrow
                    relevant_metrics = [m for m in lending_result.get("metrics", [])
                                        if m["metric_name"] in ["clr_pct", "rlr_pct",
                                                                 "lending_supply", "lending_borrow"]]
                    all_metrics.extend(relevant_metrics)

        except Exception as e:
            result["errors"].append(f"{symbol}: {str(e)}")

    if all_metrics:
        try:
            count = insert_metrics_batch(all_metrics)
            result["metrics_collected"] = count

            alerts = check_alerts_for_metrics(all_metrics)
            result["alerts_triggered"] = len(alerts)

        except Exception as e:
            result["errors"].append(f"DB insert error: {str(e)}")

    return result


def dispatch_daily(asset_configs: List[Dict] = None) -> Dict[str, Any]:
    """
    Dispatch daily frequency metrics (24 hr interval).

    Metrics: Volatility, VaR, CVaR

    Args:
        asset_configs: Optional list of asset configs.

    Returns:
        Dict with dispatch results
    """
    result = {
        "frequency": "daily",
        "timestamp": datetime.utcnow().isoformat(),
        "assets_processed": 0,
        "metrics_collected": 0,
        "alerts_triggered": 0,
        "errors": []
    }

    if asset_configs is None:
        assets = AssetRegistry.get_all_assets(enabled_only=True)
        asset_configs = [a['config'] for a in assets]

    all_metrics = []

    for config in asset_configs:
        symbol = config.get("asset_symbol", "UNKNOWN")
        result["assets_processed"] += 1

        try:
            # Price risk metrics (volatility, VaR)
            coingecko_id = config.get("coingecko_id") or config.get("price_risk", {}).get("token_coingecko_id")
            if coingecko_id:
                market_config = _normalize_market_config(config)
                market_result = fetch_price_risk_metrics(market_config, days=365)
                if market_result.get("status") == "success":
                    all_metrics.extend(market_result.get("metrics", []))

        except Exception as e:
            result["errors"].append(f"{symbol}: {str(e)}")

    if all_metrics:
        try:
            count = insert_metrics_batch(all_metrics)
            result["metrics_collected"] = count

            alerts = check_alerts_for_metrics(all_metrics)
            result["alerts_triggered"] = len(alerts)

        except Exception as e:
            result["errors"].append(f"DB insert error: {str(e)}")

    return result


# =============================================================================
# CONFIG NORMALIZATION HELPERS
# =============================================================================

def _normalize_oracle_config(config: Dict) -> Dict:
    """Normalize asset config to oracle fetcher format."""
    normalized = {
        "asset_symbol": config.get("asset_symbol", "UNKNOWN"),
        "rpc_urls": config.get("rpc_urls", {})
    }

    # Handle different oracle config formats
    if config.get("oracles"):
        normalized["oracles"] = config["oracles"]
    elif config.get("oracle_freshness", {}).get("price_feeds"):
        # Convert from oracle_freshness format
        oracles = {}
        for feed in config["oracle_freshness"]["price_feeds"]:
            chain = feed.get("chain", "ethereum")
            if chain not in oracles:
                oracles[chain] = []
            oracles[chain].append({
                "address": feed.get("address"),
                "name": feed.get("name")
            })
        normalized["oracles"] = oracles

    return normalized


def _normalize_market_config(config: Dict) -> Dict:
    """Normalize asset config to market fetcher format."""
    normalized = {
        "asset_symbol": config.get("asset_symbol", "UNKNOWN"),
    }

    # Handle coingecko_id from different locations
    if config.get("coingecko_id"):
        normalized["coingecko_id"] = config["coingecko_id"]
    elif config.get("price_risk", {}).get("token_coingecko_id"):
        normalized["coingecko_id"] = config["price_risk"]["token_coingecko_id"]

    # Handle underlying for peg deviation
    if config.get("underlying_coingecko_id"):
        normalized["underlying_coingecko_id"] = config["underlying_coingecko_id"]
    elif config.get("price_risk", {}).get("underlying_coingecko_id"):
        normalized["underlying_coingecko_id"] = config["price_risk"]["underlying_coingecko_id"]

    return normalized


def _normalize_dex_config(config: Dict) -> Dict:
    """Normalize asset config to DEX/liquidity fetcher format."""
    normalized = {
        "asset_symbol": config.get("asset_symbol", "UNKNOWN"),
        "dex_pools": {}
    }

    # Convert dex_pools list to dict format
    if isinstance(config.get("dex_pools"), list):
        for pool in config["dex_pools"]:
            chain = pool.get("chain", "ethereum")
            if chain not in normalized["dex_pools"]:
                normalized["dex_pools"][chain] = []
            normalized["dex_pools"][chain].append(pool)
    elif isinstance(config.get("dex_pools"), dict):
        normalized["dex_pools"] = config["dex_pools"]

    return normalized


def _normalize_lending_config(config: Dict) -> Dict:
    """Normalize asset config to lending fetcher format."""
    normalized = {
        "asset_symbol": config.get("asset_symbol", "UNKNOWN"),
        "lending_markets": {},
        "rpc_urls": config.get("rpc_urls", {})
    }

    # Handle lending_markets dict format
    if config.get("lending_markets"):
        normalized["lending_markets"] = config["lending_markets"]

    # Handle lending_configs list format (convert to dict)
    elif config.get("lending_configs"):
        aave_markets = {}
        compound_markets = {}

        for lc in config["lending_configs"]:
            protocol = lc.get("protocol", "").lower()
            chain = lc.get("chain", "ethereum")

            if protocol == "aave":
                aave_markets[chain] = {
                    "token_address": lc.get("token_address"),
                    "pool_address": lc.get("pool")
                }
            elif protocol == "compound":
                compound_markets[chain] = {
                    "collateral_address": lc.get("token_address"),
                    "comet_address": lc.get("comet_address")
                }

        if aave_markets:
            normalized["lending_markets"]["aave"] = aave_markets
        if compound_markets:
            normalized["lending_markets"]["compound"] = compound_markets

    return normalized


def _normalize_distribution_config(config: Dict) -> Dict:
    """Normalize asset config to distribution fetcher format."""
    normalized = {
        "asset_symbol": config.get("asset_symbol", "UNKNOWN"),
        "chains": {}
    }

    # Handle chains dict format
    if config.get("chains"):
        normalized["chains"] = config["chains"]

    # Handle token_addresses list format (convert to dict)
    elif config.get("token_addresses"):
        blockscout_apis = config.get("blockscout_apis", {})

        for ta in config["token_addresses"]:
            chain = ta.get("chain", "ethereum")
            normalized["chains"][chain] = {
                "token_address": ta.get("address"),
                "decimals": config.get("token_decimals", 18),
                "blockscout_url": blockscout_apis.get(chain)
            }

    return normalized


# =============================================================================
# MAIN DISPATCHER ENTRY POINT
# =============================================================================

def dispatch_all() -> Dict[str, Any]:
    """
    Run all dispatchers. Useful for testing or manual runs.

    Returns:
        Combined results from all frequency dispatchers
    """
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "frequencies": {}
    }

    print("Running all dispatchers...")

    for name, dispatcher in [
        ("critical", dispatch_critical),
        ("high", dispatch_high),
        ("medium", dispatch_medium),
        ("daily", dispatch_daily)
    ]:
        print(f"\n  Dispatching {name}...")
        try:
            result = dispatcher()
            results["frequencies"][name] = result
            print(f"    Assets: {result['assets_processed']}, Metrics: {result['metrics_collected']}, Alerts: {result['alerts_triggered']}")
        except Exception as e:
            results["frequencies"][name] = {"error": str(e)}
            print(f"    Error: {e}")

    return results


if __name__ == "__main__":
    # Test dispatcher
    print("Testing dispatcher...")

    # Test with a single asset config
    test_config = {
        "asset_symbol": "TEST",
        "oracle_freshness": {
            "price_feeds": [
                {"chain": "ethereum", "address": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"}
            ]
        },
        "rpc_urls": {
            "ethereum": "https://eth.llamarpc.com"
        }
    }

    result = dispatch_critical([test_config])
    print(f"Result: {result}")
