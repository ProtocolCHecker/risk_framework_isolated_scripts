"""
Lending Fetcher - Wrapper for aave_data.py and compound.py functions.

Fetches lending market metrics including:
- Total Supply / Borrow
- Utilization Rate
- CLR (Cascade Liquidation Risk)
- RLR (Recursive Lending Ratio)
"""

import sys
import os
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aave_data import analyze_aave_market, CHAINS as AAVE_CHAINS
from compound import analyze_compound_market, MARKETS as COMPOUND_MARKETS
from monitoring.core.db import insert_metrics_batch


def fetch_aave_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch AAVE V3 lending metrics for an asset.

    Args:
        asset_config: Asset configuration containing lending_markets info

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    lending_markets = asset_config.get("lending_markets", {})
    aave_config = lending_markets.get("aave", {})

    if not aave_config:
        result["error"] = "No AAVE configuration"
        return result

    metrics = []
    chains_processed = 0

    # Process each chain
    for chain_name, chain_data in aave_config.items():
        token_address = chain_data.get("token_address")
        if not token_address:
            continue

        # Get chain config from AAVE_CHAINS or use custom
        if chain_name.capitalize() in AAVE_CHAINS:
            chain_config = AAVE_CHAINS[chain_name.capitalize()]
        else:
            # Custom chain config from asset config
            rpc_urls = asset_config.get("rpc_urls", {})
            chain_config = {
                "rpc": rpc_urls.get(chain_name.lower()),
                "pool": chain_data.get("pool_address"),
                "blockscout": chain_data.get("blockscout_url")
            }

        if not chain_config.get("rpc") or not chain_config.get("pool"):
            continue

        try:
            aave_result = analyze_aave_market(token_address, chain_name, chain_config)

            if aave_result.get("status") in ["success", "partial"]:
                chains_processed += 1

                # Market overview metrics
                market = aave_result.get("market_overview", {})
                if market:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "lending_supply",
                        "value": market.get("total_supply", 0),
                        "chain": chain_name,
                        "metadata": {"protocol": "aave_v3"}
                    })
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "lending_borrow",
                        "value": market.get("total_borrow", 0),
                        "chain": chain_name,
                        "metadata": {"protocol": "aave_v3"}
                    })
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "utilization_rate",
                        "value": market.get("utilization_rate", 0),
                        "chain": chain_name,
                        "metadata": {"protocol": "aave_v3"}
                    })

                # RLR metrics
                rlr_data = aave_result.get("rlr", {})
                if rlr_data and "error" not in rlr_data:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "rlr_pct",
                        "value": rlr_data.get("rlr_supply_based", 0),
                        "chain": chain_name,
                        "metadata": {
                            "protocol": "aave_v3",
                            "loopers_count": rlr_data.get("loopers_count"),
                            "rlr_borrow_based": rlr_data.get("rlr_borrow_based")
                        }
                    })

                # CLR metrics
                clr_data = aave_result.get("clr", {})
                if clr_data and "error" not in clr_data:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "clr_pct",
                        "value": clr_data.get("clr_by_value", 0),
                        "chain": chain_name,
                        "metadata": {
                            "protocol": "aave_v3",
                            "clr_by_count": clr_data.get("clr_by_count"),
                            "positions_analyzed": clr_data.get("positions_analyzed"),
                            "risk_distribution": clr_data.get("risk_distribution")
                        }
                    })

        except Exception as e:
            print(f"AAVE fetch error for {chain_name}: {e}")
            continue

    if metrics:
        result["status"] = "success"
        result["metrics"] = metrics
    else:
        result["error"] = f"No AAVE data retrieved (chains processed: {chains_processed})"

    return result


def fetch_compound_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch Compound V3 lending metrics for an asset.

    Args:
        asset_config: Asset configuration containing lending_markets info

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    lending_markets = asset_config.get("lending_markets", {})
    compound_config = lending_markets.get("compound", {})

    if not compound_config:
        result["error"] = "No Compound configuration"
        return result

    metrics = []
    chains_processed = 0

    # Process each chain
    for chain_name, chain_data in compound_config.items():
        collateral_address = chain_data.get("collateral_address") or chain_data.get("token_address")
        if not collateral_address:
            continue

        # Get chain config from COMPOUND_MARKETS or use custom
        if chain_name.capitalize() in COMPOUND_MARKETS:
            chain_config = COMPOUND_MARKETS[chain_name.capitalize()]
        else:
            # Custom chain config from asset config
            rpc_urls = asset_config.get("rpc_urls", {})
            chain_config = {
                "rpc": rpc_urls.get(chain_name.lower()),
                "markets": chain_data.get("markets", {}),
                "subgraph": chain_data.get("subgraph_url")
            }

        if not chain_config.get("rpc"):
            continue

        try:
            compound_result = analyze_compound_market(collateral_address, chain_name, chain_config)

            if compound_result.get("status") == "success":
                chains_processed += 1

                # Process each market (USDC, USDT, WETH, etc.)
                for market_data in compound_result.get("markets", []):
                    if not market_data.get("supported"):
                        continue

                    market_name = market_data.get("market_name", "UNKNOWN")
                    market_overview = market_data.get("market_overview", {})
                    collateral_info = market_data.get("collateral_info", {})

                    if market_overview:
                        metrics.append({
                            "asset_symbol": symbol,
                            "metric_name": "lending_supply",
                            "value": market_overview.get("total_supply", 0),
                            "chain": chain_name,
                            "metadata": {
                                "protocol": "compound_v3",
                                "market": market_name
                            }
                        })
                        metrics.append({
                            "asset_symbol": symbol,
                            "metric_name": "utilization_rate",
                            "value": market_overview.get("utilization", 0),
                            "chain": chain_name,
                            "metadata": {
                                "protocol": "compound_v3",
                                "market": market_name
                            }
                        })

                    if collateral_info:
                        metrics.append({
                            "asset_symbol": symbol,
                            "metric_name": "collateral_supplied",
                            "value": collateral_info.get("total_supplied", 0),
                            "chain": chain_name,
                            "metadata": {
                                "protocol": "compound_v3",
                                "market": market_name,
                                "cap_utilization": collateral_info.get("cap_utilization")
                            }
                        })

                    # CLR metrics
                    clr_data = market_data.get("clr", {})
                    if clr_data and "error" not in clr_data:
                        metrics.append({
                            "asset_symbol": symbol,
                            "metric_name": "clr_pct",
                            "value": clr_data.get("clr_by_value", 0),
                            "chain": chain_name,
                            "metadata": {
                                "protocol": "compound_v3",
                                "market": market_name,
                                "clr_by_count": clr_data.get("clr_by_count"),
                                "positions_analyzed": clr_data.get("positions_analyzed")
                            }
                        })

        except Exception as e:
            print(f"Compound fetch error for {chain_name}: {e}")
            continue

    if metrics:
        result["status"] = "success"
        result["metrics"] = metrics
    else:
        result["error"] = f"No Compound data retrieved (chains processed: {chains_processed})"

    return result


def fetch_all_lending_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch lending metrics from all configured protocols.

    Args:
        asset_config: Asset configuration

    Returns:
        Dict with combined metrics from all lending protocols
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    all_metrics = []

    # Fetch AAVE metrics
    aave_result = fetch_aave_metrics(asset_config)
    if aave_result.get("status") == "success":
        all_metrics.extend(aave_result.get("metrics", []))

    # Fetch Compound metrics
    compound_result = fetch_compound_metrics(asset_config)
    if compound_result.get("status") == "success":
        all_metrics.extend(compound_result.get("metrics", []))

    if all_metrics:
        result["status"] = "success"
        result["metrics"] = all_metrics
    else:
        errors = []
        if aave_result.get("error"):
            errors.append(f"AAVE: {aave_result['error']}")
        if compound_result.get("error"):
            errors.append(f"Compound: {compound_result['error']}")
        result["error"] = "; ".join(errors) if errors else "No lending data"

    return result


def fetch_and_store_lending_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch lending metrics and store to database.

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

    lending_result = fetch_all_lending_metrics(asset_config)

    if lending_result.get("status") == "success":
        metrics = lending_result.get("metrics", [])
        if metrics:
            try:
                count = insert_metrics_batch(metrics)
                result["status"] = "success"
                result["metrics_stored"] = count
            except Exception as e:
                result["error"] = f"Database insert failed: {str(e)}"
    else:
        result["error"] = lending_result.get("error", "No metrics to store")

    return result


if __name__ == "__main__":
    # Test with example config
    test_config = {
        "asset_symbol": "cbBTC",
        "lending_markets": {
            "aave": {
                "ethereum": {
                    "token_address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"
                }
            }
        }
    }

    print("Testing lending fetcher...")
    result = fetch_aave_metrics(test_config)
    print(f"Status: {result['status']}")
    print(f"Metrics: {len(result.get('metrics', []))}")
    if result.get("error"):
        print(f"Error: {result['error']}")
