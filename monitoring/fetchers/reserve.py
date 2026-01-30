"""
Reserve Fetcher - Wrapper for proof_of_reserve.py functions.

Fetches proof-of-reserve and backing ratio metrics.
Supports: chainlink_por, liquid_staking, fractional, nav_based, apostro_scraper
"""

import sys
import os
import requests
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from proof_of_reserve import analyze_proof_of_reserve
from fractional_reserve import fetch_fractional_reserve_data
from rlp_reserve_scrapper import ResolvReservesScraper
from monitoring.core.db import insert_metrics_batch

try:
    from web3 import Web3
    HAS_WEB3 = True
except ImportError:
    HAS_WEB3 = False


def fetch_por_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch Proof of Reserve metrics for an asset.

    Supports verification types:
    - chainlink_por: For wrapped assets with Chainlink PoR feeds (cbBTC, WBTC)
    - liquid_staking: For LSTs (wstETH, rETH, cbETH)
    - fractional: For fractional reserve assets (cUSD)
    - nav_based: For NAV-based vaults
    - apostro_scraper: For Resolv RLP (scrapes Apostro dashboard + NAV oracle)

    Args:
        asset_config: Asset configuration containing proof_of_reserve info

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    por_config = asset_config.get("proof_of_reserve", {})
    rpc_urls = asset_config.get("rpc_urls", {})

    if not por_config:
        result["error"] = "No proof_of_reserve configuration"
        return result

    metrics = []

    # Get verification type (handle both 'type' and 'verification_type' keys)
    por_type = por_config.get("verification_type") or por_config.get("type", "chainlink_por")

    # Handle fractional reserve separately (uses different function)
    if por_type in ["fractional", "fractional_reserve"]:
        por_result = fetch_fractional_reserve_data(por_config, rpc_urls)

        if por_result.get("status") == "success":
            chain = por_config.get("chain", "unknown")

            metrics.append({
                "asset_symbol": symbol,
                "metric_name": "por_ratio",
                "value": por_result.get("backing_ratio_pct", 0) / 100,
                "chain": chain,
                "metadata": {
                    "type": "fractional",
                    "is_fully_backed": por_result.get("is_fully_backed"),
                    "total_supply": por_result.get("total_supply"),
                    "total_reserves": por_result.get("total_reserves_usd")
                }
            })

            if por_result.get("overall_utilization_pct") is not None:
                metrics.append({
                    "asset_symbol": symbol,
                    "metric_name": "reserve_utilization_pct",
                    "value": por_result.get("overall_utilization_pct", 0),
                    "chain": chain,
                    "metadata": None
                })

            risk_flags = por_result.get("risk_flags", [])
            if risk_flags:
                metrics.append({
                    "asset_symbol": symbol,
                    "metric_name": "por_risk_flags_count",
                    "value": len(risk_flags),
                    "chain": chain,
                    "metadata": {"flags": risk_flags}
                })
        else:
            result["error"] = por_result.get("error", "Fractional reserve fetch failed")
            return result

    elif por_type == "apostro_scraper":
        # NAV-based token (RLP) - scrape from Apostro dashboard
        # RLP price = NAV = backing per token by definition
        try:
            # 1. Get RLP backing data from Apostro scraper
            scraper = ResolvReservesScraper()
            scraper_data = scraper.scrape_data()
            general_metrics = scraper_data.get("general_metrics", {})
            rlp_tvl_usd = general_metrics.get("rlp_tvl", 0)

            # 2. Get NAV price from on-chain oracle (Resolv AggregatorV3)
            nav_price = 0
            nav_oracle_address = por_config.get("nav_oracle_address")
            nav_oracle_chain = por_config.get("nav_oracle_chain", "ethereum")
            nav_oracle_decimals = por_config.get("nav_oracle_decimals", 8)

            if nav_oracle_address and HAS_WEB3:
                try:
                    rpc_url = rpc_urls.get(nav_oracle_chain)
                    if rpc_url:
                        w3 = Web3(Web3.HTTPProvider(rpc_url))
                        oracle_contract = w3.eth.contract(
                            address=Web3.to_checksum_address(nav_oracle_address),
                            abi=[{
                                "inputs": [],
                                "name": "latestRoundData",
                                "outputs": [
                                    {"name": "roundId", "type": "uint80"},
                                    {"name": "answer", "type": "int256"},
                                    {"name": "startedAt", "type": "uint256"},
                                    {"name": "updatedAt", "type": "uint256"},
                                    {"name": "answeredInRound", "type": "uint80"}
                                ],
                                "stateMutability": "view",
                                "type": "function"
                            }]
                        )
                        round_data = oracle_contract.functions.latestRoundData().call()
                        nav_price = round_data[1] / (10 ** nav_oracle_decimals)
                except Exception as e:
                    print(f"Error fetching NAV from oracle: {e}")

            # 3. Get Market price from CoinGecko
            market_price = 0
            token_coingecko_id = por_config.get("token_coingecko_id")
            if token_coingecko_id:
                try:
                    price_url = f"https://api.coingecko.com/api/v3/simple/price?ids={token_coingecko_id}&vs_currencies=usd"
                    price_response = requests.get(price_url, timeout=10)
                    price_data = price_response.json()
                    market_price = price_data.get(token_coingecko_id, {}).get("usd", 0)
                except Exception as e:
                    print(f"Error fetching market price: {e}")

            # 4. Calculate NAV vs Market deviation
            nav_market_deviation_pct = 0
            if nav_price > 0 and market_price > 0:
                nav_market_deviation_pct = ((market_price - nav_price) / nav_price) * 100

            # 5. Create metrics - NAV-based means reserve_ratio is 1.0 by definition
            chain = nav_oracle_chain

            # Main reserve ratio (always 1.0 for NAV-based)
            metrics.append({
                "asset_symbol": symbol,
                "metric_name": "por_ratio",
                "value": 1.0,  # NAV-based = always 1:1 by definition
                "chain": chain,
                "metadata": {
                    "type": "nav_based",
                    "protocol": "resolv",
                    "is_fully_backed": True
                }
            })

            # TVL metric
            if rlp_tvl_usd > 0:
                metrics.append({
                    "asset_symbol": symbol,
                    "metric_name": "por_total_reserves",
                    "value": rlp_tvl_usd,
                    "chain": chain,
                    "metadata": {"source": "apostro_scraper"}
                })

            # NAV price metric
            if nav_price > 0:
                metrics.append({
                    "asset_symbol": symbol,
                    "metric_name": "nav_price_usd",
                    "value": nav_price,
                    "chain": chain,
                    "metadata": {"oracle_address": nav_oracle_address}
                })

            # Market price metric
            if market_price > 0:
                metrics.append({
                    "asset_symbol": symbol,
                    "metric_name": "market_price_usd",
                    "value": market_price,
                    "chain": chain,
                    "metadata": {"source": "coingecko", "coingecko_id": token_coingecko_id}
                })

            # NAV vs Market deviation metric
            if nav_price > 0 and market_price > 0:
                metrics.append({
                    "asset_symbol": symbol,
                    "metric_name": "nav_market_deviation_pct",
                    "value": abs(nav_market_deviation_pct),
                    "chain": chain,
                    "metadata": {
                        "direction": "premium" if nav_market_deviation_pct > 0 else "discount",
                        "raw_deviation": nav_market_deviation_pct
                    }
                })

        except Exception as e:
            result["error"] = f"Apostro scraper error: {str(e)}"
            return result

    else:
        # Use unified analyze_proof_of_reserve for chainlink_por, liquid_staking, nav_based
        # Merge rpc_urls into config (like streamlit does)
        por_config_with_rpcs = {**por_config, "rpc_urls": rpc_urls}

        try:
            por_result = analyze_proof_of_reserve(config=por_config_with_rpcs)

            if por_result.get("status") == "success":
                # Extract backing ratio
                backing_ratio = por_result.get("backing_ratio")
                if backing_ratio is None:
                    # Try metrics dict
                    por_metrics = por_result.get("metrics", {})
                    backing_ratio = por_metrics.get("reserve_ratio") or por_metrics.get("backing_ratio")

                if backing_ratio is not None:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "por_ratio",
                        "value": backing_ratio,
                        "chain": por_config.get("chain", "global"),
                        "metadata": {
                            "type": por_type,
                            "verification_type": por_result.get("verification_type"),
                            "protocol": por_result.get("protocol")
                        }
                    })

                # Extract total reserves and supply if available
                total_reserves = por_result.get("total_reserves") or por_result.get("metrics", {}).get("reserves")
                total_supply = por_result.get("total_supply") or por_result.get("metrics", {}).get("total_supply")

                if total_reserves is not None:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "por_total_reserves",
                        "value": total_reserves,
                        "chain": por_config.get("chain", "global"),
                        "metadata": None
                    })

                if total_supply is not None:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "por_total_supply",
                        "value": total_supply,
                        "chain": por_config.get("chain", "global"),
                        "metadata": None
                    })

                # Check for risk flags
                is_fully_backed = por_result.get("is_fully_backed") or por_result.get("metrics", {}).get("is_fully_backed")
                if is_fully_backed is False:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "por_risk_flags_count",
                        "value": 1,
                        "chain": por_config.get("chain", "global"),
                        "metadata": {"flags": ["not_fully_backed"]}
                    })

            else:
                result["error"] = por_result.get("error", "PoR analysis failed")
                return result

        except Exception as e:
            result["error"] = f"PoR analysis error: {str(e)}"
            return result

    if metrics:
        result["status"] = "success"
        result["metrics"] = metrics
    else:
        if not result.get("error"):
            result["error"] = "No PoR data retrieved"

    return result


def fetch_and_store_reserve_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch reserve metrics and store to database.

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

    por_result = fetch_por_metrics(asset_config)

    if por_result.get("status") == "success":
        metrics = por_result.get("metrics", [])
        if metrics:
            try:
                count = insert_metrics_batch(metrics)
                result["status"] = "success"
                result["metrics_stored"] = count
            except Exception as e:
                result["error"] = f"Database insert failed: {str(e)}"
    else:
        result["error"] = por_result.get("error", "No metrics to store")

    return result


if __name__ == "__main__":
    # Test with example config
    test_config = {
        "asset_symbol": "cUSD",
        "proof_of_reserve": {
            "type": "fractional",
            "vault_address": "0x...",
            "chain": "celo",
            "backing_assets": [
                {"symbol": "USDC", "address": "0x...", "decimals": 6}
            ]
        },
        "rpc_urls": {
            "celo": "https://forno.celo.org"
        }
    }

    print("Testing reserve fetcher...")
    result = fetch_por_metrics(test_config)
    print(f"Status: {result['status']}")
    print(f"Metrics: {len(result.get('metrics', []))}")
    if result.get("error"):
        print(f"Error: {result['error']}")
