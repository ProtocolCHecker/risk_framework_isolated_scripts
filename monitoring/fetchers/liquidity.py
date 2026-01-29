"""
Liquidity Fetcher - Wrapper for slippage_check.py functions.

Fetches DEX slippage and pool TVL metrics.
"""

import sys
import os
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from slippage_check import cross_verify_slippage, get_token_price
from monitoring.core.db import insert_metrics_batch


def fetch_slippage_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch slippage metrics from DEX aggregators.

    Args:
        asset_config: Asset configuration containing dex_pools info

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    dex_pools = asset_config.get("dex_pools", {})

    if not dex_pools:
        result["error"] = "No dex_pools configured"
        return result

    metrics = []

    # Process each chain's DEX pools
    for chain, pools in dex_pools.items():
        if not pools:
            continue

        for pool in pools:
            # Extract pool configuration
            sell_token = pool.get("token_address") or pool.get("sell_token")
            buy_token = pool.get("quote_token") or pool.get("buy_token")

            if not sell_token or not buy_token:
                continue

            sell_decimals = pool.get("decimals", 18)
            sell_symbol = pool.get("symbol", symbol)
            buy_symbol = pool.get("quote_symbol", "USDC")
            coingecko_id = pool.get("coingecko_id")
            price_usd = pool.get("price_usd")

            # Define trade sizes
            trade_sizes = pool.get("trade_sizes_usd", [100_000, 500_000])

            try:
                # Fetch slippage data
                slippage_result = cross_verify_slippage(
                    chain=chain,
                    sell_token=sell_token,
                    buy_token=buy_token,
                    sell_token_decimals=sell_decimals,
                    sell_token_price_usd=price_usd,
                    sell_token_coingecko_id=coingecko_id,
                    trade_sizes_usd=trade_sizes,
                    sell_token_symbol=sell_symbol,
                    buy_token_symbol=buy_symbol
                )

                if slippage_result.get("status") == "success":
                    for trade_data in slippage_result.get("trade_sizes", []):
                        size_usd = trade_data.get("size_usd", 0)
                        median_slippage = trade_data.get("median_slippage")

                        if median_slippage is not None:
                            # Name metric based on size
                            size_label = f"{size_usd // 1000}k"
                            metric_name = f"slippage_{size_label}_pct"

                            metrics.append({
                                "asset_symbol": symbol,
                                "metric_name": metric_name,
                                "value": median_slippage,
                                "chain": chain,
                                "metadata": {
                                    "trade_size_usd": size_usd,
                                    "best_aggregator": trade_data.get("best_aggregator"),
                                    "successful_quotes": trade_data.get("successful_quotes"),
                                    "sell_token": sell_token,
                                    "buy_token": buy_token
                                }
                            })

            except Exception as e:
                print(f"Slippage fetch error for {chain}: {e}")
                continue

    if metrics:
        result["status"] = "success"
        result["metrics"] = metrics
    else:
        result["error"] = "No slippage data retrieved"

    return result


def fetch_pool_tvl(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch DEX pool TVL metrics.

    Note: Currently extracts TVL from dex_pools config if available.
    For live TVL, would need integration with DEX subgraphs.

    Args:
        asset_config: Asset configuration

    Returns:
        Dict with status and TVL metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    dex_pools = asset_config.get("dex_pools", {})

    if not dex_pools:
        result["error"] = "No dex_pools configured"
        return result

    metrics = []

    for chain, pools in dex_pools.items():
        if not pools:
            continue

        for pool in pools:
            tvl = pool.get("tvl_usd")
            pool_address = pool.get("pool_address")
            pool_name = pool.get("name", "Unknown")

            if tvl is not None:
                metrics.append({
                    "asset_symbol": symbol,
                    "metric_name": "pool_tvl_usd",
                    "value": tvl,
                    "chain": chain,
                    "metadata": {
                        "pool_address": pool_address,
                        "pool_name": pool_name
                    }
                })

    if metrics:
        result["status"] = "success"
        result["metrics"] = metrics
    else:
        result["error"] = "No TVL data in config"

    return result


def fetch_and_store_liquidity_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch liquidity metrics and store to database.

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

    all_metrics = []

    # Fetch slippage
    slippage_result = fetch_slippage_metrics(asset_config)
    if slippage_result.get("status") == "success":
        all_metrics.extend(slippage_result.get("metrics", []))

    # Fetch TVL
    tvl_result = fetch_pool_tvl(asset_config)
    if tvl_result.get("status") == "success":
        all_metrics.extend(tvl_result.get("metrics", []))

    if all_metrics:
        try:
            count = insert_metrics_batch(all_metrics)
            result["status"] = "success"
            result["metrics_stored"] = count
        except Exception as e:
            result["error"] = f"Database insert failed: {str(e)}"
    else:
        result["error"] = "No metrics to store"

    return result


if __name__ == "__main__":
    # Test with example config
    test_config = {
        "asset_symbol": "cbBTC",
        "dex_pools": {
            "ethereum": [
                {
                    "token_address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
                    "quote_token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    "decimals": 8,
                    "symbol": "cbBTC",
                    "quote_symbol": "USDC",
                    "coingecko_id": "coinbase-wrapped-btc"
                }
            ]
        }
    }

    print("Testing liquidity fetcher...")
    result = fetch_slippage_metrics(test_config)
    print(f"Status: {result['status']}")
    print(f"Metrics: {len(result.get('metrics', []))}")
    if result.get("error"):
        print(f"Error: {result['error']}")
