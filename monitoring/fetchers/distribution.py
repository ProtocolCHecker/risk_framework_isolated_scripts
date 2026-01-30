"""
Distribution Fetcher - Wrapper for token_distribution.py functions.

Fetches token distribution metrics including:
- HHI (Herfindahl-Hirschman Index)
- Gini Coefficient
- Concentration metrics
- Total supply per chain
"""

import sys
import os
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from token_distribution import analyze_token, gini
from monitoring.core.db import insert_metrics_batch
import numpy as np


def calculate_hhi(balances: List[float]) -> float:
    """
    Calculate Herfindahl-Hirschman Index from holder balances.

    HHI = Sum of (market share)^2 for all holders
    Scale: 0-10000 (10000 = single holder, <1000 = competitive)

    Args:
        balances: List of holder balances

    Returns:
        HHI value (0-10000)
    """
    if not balances or len(balances) == 0:
        return 0.0

    total = sum(balances)
    if total == 0:
        return 0.0

    # Calculate market shares (as percentages, 0-100)
    shares = [(b / total) * 100 for b in balances]

    # HHI = sum of squares of market shares
    hhi = sum(s ** 2 for s in shares)

    return hhi


def fetch_distribution_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch token distribution metrics for an asset across all chains.

    Supports both config formats:
    - New format: token_addresses (list of {chain, address})
    - Legacy format: chains (dict with chain names as keys)

    Args:
        asset_config: Asset configuration containing token addresses per chain

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    token_decimals = asset_config.get("token_decimals", 18)
    blockscout_apis = asset_config.get("blockscout_apis", {})

    # Try new format first: token_addresses list
    token_addresses = asset_config.get("token_addresses", [])

    # Fall back to legacy format: chains dict
    chains_dict = asset_config.get("chains", {})

    if not token_addresses and not chains_dict:
        result["error"] = "No token_addresses or chains configured"
        return result

    metrics = []
    total_supply_all_chains = 0

    # Process new format: token_addresses list
    if token_addresses:
        for ta in token_addresses:
            chain_name = ta.get("chain", "ethereum")
            token_address = ta.get("address")

            if not token_address:
                continue

            # Skip non-EVM chains like Solana for now
            if chain_name.lower() == "solana":
                continue

            decimals = ta.get("decimals") or token_decimals
            blockscout_url = blockscout_apis.get(chain_name)
            use_ankr = chain_name.lower() in ["arbitrum", "ethereum"]

            try:
                dist_result = analyze_token(
                    token_address=token_address,
                    chain_name=chain_name,
                    blockscout_url=blockscout_url,
                    use_ankr=use_ankr,
                    decimals=decimals
                )

                if dist_result.get("status") == "success":
                    metrics_data = dist_result.get("metrics", {})
                    top_holders = dist_result.get("top_holders", [])
                    balances = [h.get("balance", 0) for h in top_holders]

                    total_supply = metrics_data.get("total_supply", 0)
                    total_supply_all_chains += total_supply

                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "total_supply",
                        "value": total_supply,
                        "chain": chain_name,
                        "metadata": {"holders_analyzed": metrics_data.get("holders_analyzed")}
                    })

                    gini_coeff = metrics_data.get("gini_coefficient", 0)
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "gini",
                        "value": gini_coeff,
                        "chain": chain_name,
                        "metadata": {"holders_analyzed": metrics_data.get("holders_analyzed")}
                    })

                    hhi = calculate_hhi(balances)
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "hhi",
                        "value": hhi,
                        "chain": chain_name,
                        "metadata": {"holders_analyzed": len(balances)}
                    })

                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "top_10_concentration_pct",
                        "value": metrics_data.get("top_10_concentration_pct", 0),
                        "chain": chain_name,
                        "metadata": None
                    })

            except Exception as e:
                print(f"Distribution fetch error for {chain_name}: {e}")
                continue

    # Process legacy format: chains dict
    elif chains_dict:
        for chain_name, chain_data in chains_dict.items():
            token_address = chain_data.get("token_address")
            if not token_address:
                continue

            decimals = chain_data.get("decimals", 18)
            blockscout_url = chain_data.get("blockscout_url")
            use_ankr = chain_data.get("use_ankr", False)

            # Force Ankr for certain chains
            if chain_name.lower() in ["arbitrum", "ethereum"]:
                use_ankr = True

            try:
                dist_result = analyze_token(
                    token_address=token_address,
                    chain_name=chain_name,
                    blockscout_url=blockscout_url,
                    use_ankr=use_ankr,
                    decimals=decimals
                )

                if dist_result.get("status") == "success":
                    metrics_data = dist_result.get("metrics", {})
                    top_holders = dist_result.get("top_holders", [])

                    # Extract balances for HHI calculation
                    balances = [h.get("balance", 0) for h in top_holders]

                    # Total supply
                    total_supply = metrics_data.get("total_supply", 0)
                    total_supply_all_chains += total_supply

                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "total_supply",
                        "value": total_supply,
                        "chain": chain_name,
                        "metadata": {
                            "holders_analyzed": metrics_data.get("holders_analyzed")
                        }
                    })

                    # Gini coefficient
                    gini_coeff = metrics_data.get("gini_coefficient", 0)
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "gini",
                        "value": gini_coeff,
                        "chain": chain_name,
                        "metadata": {
                            "holders_analyzed": metrics_data.get("holders_analyzed")
                        }
                    })

                    # HHI
                    hhi = calculate_hhi(balances)
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "hhi",
                        "value": hhi,
                        "chain": chain_name,
                        "metadata": {
                            "holders_analyzed": len(balances)
                        }
                    })

                    # Concentration metrics
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "top_10_concentration_pct",
                        "value": metrics_data.get("top_10_concentration_pct", 0),
                        "chain": chain_name,
                        "metadata": None
                    })

                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "top_50_concentration_pct",
                        "value": metrics_data.get("top_50_concentration_pct", 0),
                        "chain": chain_name,
                        "metadata": None
                    })

            except Exception as e:
                print(f"Distribution fetch error for {chain_name}: {e}")
                continue

    # Add aggregate total supply
    if total_supply_all_chains > 0:
        metrics.append({
            "asset_symbol": symbol,
            "metric_name": "total_supply_aggregate",
            "value": total_supply_all_chains,
            "chain": None,
            "metadata": {
                "chains_counted": len([m for m in metrics if m["metric_name"] == "total_supply"])
            }
        })

    if metrics:
        result["status"] = "success"
        result["metrics"] = metrics
    else:
        result["error"] = "No distribution data retrieved"

    return result


def fetch_single_chain_distribution(
    token_address: str,
    chain_name: str,
    symbol: str = "UNKNOWN",
    decimals: int = 18,
    blockscout_url: str = None,
    use_ankr: bool = False
) -> Dict[str, Any]:
    """
    Fetch distribution metrics for a single chain.
    Convenience function for targeted fetching.

    Args:
        token_address: Token contract address
        chain_name: Chain name
        symbol: Asset symbol
        decimals: Token decimals
        blockscout_url: Blockscout API URL (optional)
        use_ankr: Force Ankr API

    Returns:
        Dict with metrics for this chain
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    try:
        dist_result = analyze_token(
            token_address=token_address,
            chain_name=chain_name,
            blockscout_url=blockscout_url,
            use_ankr=use_ankr,
            decimals=decimals
        )

        if dist_result.get("status") == "success":
            metrics_data = dist_result.get("metrics", {})
            top_holders = dist_result.get("top_holders", [])
            balances = [h.get("balance", 0) for h in top_holders]

            metrics = [
                {
                    "asset_symbol": symbol,
                    "metric_name": "total_supply",
                    "value": metrics_data.get("total_supply", 0),
                    "chain": chain_name,
                    "metadata": None
                },
                {
                    "asset_symbol": symbol,
                    "metric_name": "gini",
                    "value": metrics_data.get("gini_coefficient", 0),
                    "chain": chain_name,
                    "metadata": None
                },
                {
                    "asset_symbol": symbol,
                    "metric_name": "hhi",
                    "value": calculate_hhi(balances),
                    "chain": chain_name,
                    "metadata": None
                }
            ]

            result["status"] = "success"
            result["metrics"] = metrics
        else:
            result["error"] = dist_result.get("error", "Analysis failed")

    except Exception as e:
        result["error"] = str(e)

    return result


def fetch_and_store_distribution_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch distribution metrics and store to database.

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

    dist_result = fetch_distribution_metrics(asset_config)

    if dist_result.get("status") == "success":
        metrics = dist_result.get("metrics", [])
        if metrics:
            try:
                count = insert_metrics_batch(metrics)
                result["status"] = "success"
                result["metrics_stored"] = count
            except Exception as e:
                result["error"] = f"Database insert failed: {str(e)}"
    else:
        result["error"] = dist_result.get("error", "No metrics to store")

    return result


if __name__ == "__main__":
    # Test with example config
    test_config = {
        "asset_symbol": "cbBTC",
        "chains": {
            "ethereum": {
                "token_address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
                "decimals": 8,
                "blockscout_url": "https://eth.blockscout.com"
            }
        }
    }

    print("Testing distribution fetcher...")
    result = fetch_distribution_metrics(test_config)
    print(f"Status: {result['status']}")
    print(f"Metrics: {len(result.get('metrics', []))}")
    if result.get("error"):
        print(f"Error: {result['error']}")
