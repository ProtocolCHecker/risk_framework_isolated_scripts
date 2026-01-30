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

    Supports both config formats:
    - New format: lending_configs (list of {protocol, chain, token_address, ...})
    - Legacy format: lending_markets.aave (dict)

    Args:
        asset_config: Asset configuration containing lending configs

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")

    # Get AAVE configs from new format (lending_configs list)
    lending_configs = asset_config.get("lending_configs", [])
    aave_configs = [cfg for cfg in lending_configs if cfg.get("protocol") == "aave"]

    # Fall back to legacy format (lending_markets.aave dict)
    if not aave_configs:
        lending_markets = asset_config.get("lending_markets", {})
        legacy_aave = lending_markets.get("aave", {})
        if legacy_aave:
            # Convert legacy format to list format
            for chain_name, chain_data in legacy_aave.items():
                if chain_data.get("token_address"):
                    aave_configs.append({
                        "protocol": "aave",
                        "chain": chain_name,
                        "token_address": chain_data.get("token_address")
                    })

    if not aave_configs:
        result["error"] = "No AAVE configuration"
        return result

    metrics = []
    processed_chains = set()

    # Process each AAVE config (same pattern as streamlit)
    for cfg in aave_configs:
        chain_name = cfg.get("chain", "").capitalize()
        token_address = cfg.get("token_address")

        if not token_address or not chain_name:
            continue

        # Only process each chain once (like streamlit)
        if chain_name in processed_chains:
            continue
        processed_chains.add(chain_name)

        # Get chain config from AAVE_CHAINS
        if chain_name not in AAVE_CHAINS:
            continue

        chain_config = AAVE_CHAINS[chain_name]

        try:
            aave_result = analyze_aave_market(token_address, chain_name, chain_config)

            if aave_result.get("status") in ["success", "partial"]:
                # Market overview metrics
                market = aave_result.get("market_overview", {})
                if market:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "lending_supply",
                        "value": market.get("total_supply", 0),
                        "chain": chain_name.lower(),
                        "metadata": {"protocol": "aave_v3"}
                    })
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "lending_borrow",
                        "value": market.get("total_borrow", 0),
                        "chain": chain_name.lower(),
                        "metadata": {"protocol": "aave_v3"}
                    })
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "utilization_rate",
                        "value": market.get("utilization_rate", 0),
                        "chain": chain_name.lower(),
                        "metadata": {"protocol": "aave_v3"}
                    })

                # RLR metrics
                rlr_data = aave_result.get("rlr", {})
                if rlr_data and "error" not in rlr_data:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "rlr_pct",
                        "value": rlr_data.get("rlr_supply_based", 0),
                        "chain": chain_name.lower(),
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
                        "chain": chain_name.lower(),
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
        result["error"] = f"No AAVE data retrieved (chains: {processed_chains})"

    return result


def fetch_compound_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch Compound V3 lending metrics for an asset.

    Supports both config formats:
    - New format: lending_configs (list of {protocol, chain, token_address, ...})
    - Legacy format: lending_markets.compound (dict)

    Args:
        asset_config: Asset configuration containing lending configs

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")

    # Get Compound configs from new format (lending_configs list)
    lending_configs = asset_config.get("lending_configs", [])
    compound_configs = [cfg for cfg in lending_configs if cfg.get("protocol") == "compound"]

    # Fall back to legacy format (lending_markets.compound dict)
    if not compound_configs:
        lending_markets = asset_config.get("lending_markets", {})
        legacy_compound = lending_markets.get("compound", {})
        if legacy_compound:
            # Convert legacy format to list format
            for chain_name, chain_data in legacy_compound.items():
                token_addr = chain_data.get("collateral_address") or chain_data.get("token_address")
                if token_addr:
                    compound_configs.append({
                        "protocol": "compound",
                        "chain": chain_name,
                        "token_address": token_addr
                    })

    if not compound_configs:
        result["error"] = "No Compound configuration"
        return result

    metrics = []
    processed_chains = set()

    # Process each Compound config (same pattern as streamlit)
    for cfg in compound_configs:
        chain_name = cfg.get("chain", "").capitalize()
        token_address = cfg.get("token_address")

        if not token_address or not chain_name:
            continue

        # Only process each chain once (like streamlit)
        if chain_name in processed_chains:
            continue
        processed_chains.add(chain_name)

        # Get chain config from COMPOUND_MARKETS
        if chain_name not in COMPOUND_MARKETS:
            continue

        chain_config = COMPOUND_MARKETS[chain_name]

        try:
            compound_result = analyze_compound_market(token_address, chain_name, chain_config)

            if compound_result.get("status") == "success":
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
                            "chain": chain_name.lower(),
                            "metadata": {
                                "protocol": "compound_v3",
                                "market": market_name
                            }
                        })
                        metrics.append({
                            "asset_symbol": symbol,
                            "metric_name": "utilization_rate",
                            "value": market_overview.get("utilization", 0),
                            "chain": chain_name.lower(),
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
                            "chain": chain_name.lower(),
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
                            "chain": chain_name.lower(),
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
        result["error"] = f"No Compound data retrieved (chains: {processed_chains})"

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
    # Test with example config (matches actual config format)
    test_config = {
        "asset_symbol": "wstETH",
        "lending_configs": [
            {
                "protocol": "aave",
                "chain": "ethereum",
                "token_address": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"
            },
            {
                "protocol": "compound",
                "chain": "ethereum",
                "token_address": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"
            }
        ]
    }

    print("Testing lending fetcher...")
    result = fetch_all_lending_metrics(test_config)
    print(f"Status: {result['status']}")
    print(f"Metrics: {len(result.get('metrics', []))}")
    if result.get("error"):
        print(f"Error: {result['error']}")
