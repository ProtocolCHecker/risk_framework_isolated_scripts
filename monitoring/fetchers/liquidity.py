"""
Liquidity Fetcher - Wrapper for slippage_check.py functions.

Fetches DEX slippage and pool TVL metrics.
"""

import sys
import os
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from slippage_check import cross_verify_slippage
from monitoring.core.db import insert_metrics_batch


# Stablecoins by chain (matches streamlit pattern)
STABLECOINS = {
    "ethereum": {
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    },
    "base": {
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA"
    },
    "arbitrum": {
        "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9"
    },
    "optimism": {
        "USDC": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
    },
    "polygon": {
        "USDC": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
    },
}


def fetch_slippage_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch slippage metrics from DEX aggregators.

    Follows the same pattern as streamlit:
    - Iterates over token_addresses
    - Only checks chains that have dex_pools
    - Uses stablecoins as quote token

    Args:
        asset_config: Asset configuration

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    # Get config values (same as streamlit)
    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    token_addresses = asset_config.get("token_addresses", [])
    dex_pools = asset_config.get("dex_pools", [])
    price_risk = asset_config.get("price_risk", {})
    token_decimals = asset_config.get("token_decimals", 18)
    coingecko_id = price_risk.get("token_coingecko_id")

    if not token_addresses:
        result["error"] = "No token_addresses configured"
        return result

    if not dex_pools:
        result["error"] = "No dex_pools configured"
        return result

    # Get chains that have DEX pools (only check slippage where liquidity exists)
    dex_chains = {pool.get("chain", "").lower() for pool in dex_pools if pool.get("chain")}

    metrics = []

    # Process each token address (same pattern as streamlit)
    for token_cfg in token_addresses:
        chain = token_cfg.get("chain", "").lower()
        token_addr = token_cfg.get("address")

        # Skip Solana or missing addresses
        if chain == "solana" or not token_addr:
            continue

        # Only check slippage on chains with DEX liquidity
        if chain not in dex_chains:
            continue

        # Skip chains without stablecoin config
        if chain not in STABLECOINS:
            continue

        try:
            # Get first available stablecoin for this chain
            stablecoin_name, stablecoin_addr = next(iter(STABLECOINS[chain].items()))

            # Fetch slippage data (same params as streamlit)
            slippage_result = cross_verify_slippage(
                chain=chain,
                sell_token=token_addr,
                buy_token=stablecoin_addr,
                sell_token_decimals=token_decimals,
                sell_token_coingecko_id=coingecko_id,
                trade_sizes_usd=[100_000, 500_000],
                sell_token_symbol=symbol,
                buy_token_symbol=stablecoin_name
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
                                "sell_token": token_addr,
                                "buy_token": stablecoin_addr
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
    dex_pools = asset_config.get("dex_pools", [])

    if not dex_pools:
        result["error"] = "No dex_pools configured"
        return result

    metrics = []

    # dex_pools is a list of {protocol, chain, pool_address, pool_name, ...}
    for pool in dex_pools:
        chain = pool.get("chain", "unknown")
        tvl = pool.get("tvl_usd")
        pool_address = pool.get("pool_address")
        pool_name = pool.get("pool_name", "Unknown")

        if tvl is not None:
            metrics.append({
                "asset_symbol": symbol,
                "metric_name": "pool_tvl_usd",
                "value": tvl,
                "chain": chain,
                "metadata": {
                    "pool_address": pool_address,
                    "pool_name": pool_name,
                    "protocol": pool.get("protocol")
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
    # Test with example config (matches actual config format)
    test_config = {
        "asset_symbol": "cbBTC",
        "token_decimals": 8,
        "token_addresses": [
            {"chain": "ethereum", "address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"}
        ],
        "dex_pools": [
            {
                "protocol": "uniswap",
                "chain": "ethereum",
                "pool_address": "0x...",
                "pool_name": "cbBTC/USDC"
            }
        ],
        "price_risk": {
            "token_coingecko_id": "coinbase-wrapped-btc"
        }
    }

    print("Testing liquidity fetcher...")
    result = fetch_slippage_metrics(test_config)
    print(f"Status: {result['status']}")
    print(f"Metrics: {len(result.get('metrics', []))}")
    if result.get("error"):
        print(f"Error: {result['error']}")
