"""
Token Risk Dashboard - Streamlit Application.

A comprehensive risk analysis dashboard for DeFi tokens featuring:
- JSON configuration upload or manual form entry
- Two-stage risk scoring (primary checks + weighted categories)
- Live quantitative data fetching from on-chain sources
- Detailed methodology explanation

Run with: streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
import json
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import traceback
import time
import plotly.express as px
import plotly.graph_objects as go

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Token Risk Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# IMPORTS
# =============================================================================

IMPORTS_OK = False
IMPORT_ERROR = ""

try:
    from thresholds import (
        GRADE_SCALE,
        CATEGORY_WEIGHTS,
        SMART_CONTRACT_THRESHOLDS,
        COUNTERPARTY_THRESHOLDS,
        MARKET_THRESHOLDS,
        LIQUIDITY_THRESHOLDS,
        COLLATERAL_THRESHOLDS,
        RESERVE_ORACLE_THRESHOLDS,
        CIRCUIT_BREAKERS,
    )
    from primary_checks import run_primary_checks, CheckStatus, PRIMARY_CHECKS
    from asset_score import calculate_asset_risk_score, CUSTODY_MODELS
    IMPORTS_OK = True
except ImportError as e:
    IMPORT_ERROR = f"ImportError: {str(e)}"
except Exception as e:
    IMPORT_ERROR = f"Error: {str(e)}"

# Import data fetching scripts (optional - for live data)
DATA_SCRIPTS_OK = False
try:
    from aave_data import analyze_aave_market, CHAINS as AAVE_CHAINS
    from compound import analyze_compound_market, MARKETS as COMPOUND_MARKETS
    from uniswap import UniswapV3Analyzer
    from curve import CurveFinanceAnalyzer
    from proof_of_reserve import analyze_proof_of_reserve
    from price_risk import get_coingecko_data, calculate_peg_deviation, calculate_metrics
    from oracle_lag import analyze_oracle_lag, get_oracle_freshness
    from token_distribution import analyze_token as analyze_token_distribution
    from slippage_check import cross_verify_slippage
    # Data accuracy check scripts
    from uniswap_check import verify_uniswap_v3_accuracy
    from pancakeswap_check import verify_pancakeswap_v3_accuracy
    from curve_check import verify_curve_lp_accuracy
    DATA_SCRIPTS_OK = True
except:
    pass

# =============================================================================
# CONSTANTS
# =============================================================================

SUPPORTED_CHAINS = ["ethereum", "base", "arbitrum", "polygon", "optimism", "avalanche", "bsc", "gnosis"]
CUSTODY_MODEL_OPTIONS = ["decentralized", "regulated_insured", "regulated", "unregulated", "unknown"]
BLACKLIST_CONTROLS = ["none", "governance", "multisig", "eoa"]
ASSET_TYPES = ["wrapped_btc", "wrapped_eth", "stablecoin", "lst", "lrt", "synthetic", "native", "other"]

GRADE_COLORS = {
    "A": "#22c55e",
    "B": "#84cc16",
    "C": "#eab308",
    "D": "#f97316",
    "F": "#ef4444",
}

GRAPH_API_KEY = "db5921ae7c7116289958d028661c86b3"


# =============================================================================
# SESSION STATE
# =============================================================================

def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "config": None,
        "risk_score": None,
        "analysis_run": False,
        "fetched_data": {
            "supply": None,
            "lending": None,
            "dex": None,
            "slippage": None,
            "data_accuracy": None,
            "price_risk": None,
            "proof_of_reserve": None,
            "token_distribution": None,
            "oracle": None,
        },
        "scoring_metrics": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_grade_color(grade: str) -> str:
    return GRADE_COLORS.get(grade, "#6b7280")


def format_number(value, decimals=2):
    """Format large numbers with commas."""
    if value is None:
        return "N/A"
    if isinstance(value, str):
        return value
    return f"{value:,.{decimals}f}"


def format_percentage(value, decimals=2):
    """Format as percentage."""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def days_since(date_str):
    """Calculate days since a date string."""
    if not date_str:
        return None
    try:
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - date).days
    except:
        return None


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def fetch_price_data(config: dict) -> dict:
    """Fetch price data from CoinGecko."""
    result = {"token_price": None, "underlying_price": None, "peg_deviation": None,
              "volatility": None, "var_95": None, "error": None}

    price_risk = config.get("price_risk", {})
    if not price_risk:
        result["error"] = "No price_risk configuration"
        return result

    try:
        token_id = price_risk.get("token_coingecko_id")
        underlying_id = price_risk.get("underlying_coingecko_id")

        if token_id and underlying_id:
            _, token_prices = get_coingecko_data(token_id, days=30)
            _, underlying_prices = get_coingecko_data(underlying_id, days=30)

            if token_prices and underlying_prices:
                result["token_price"] = token_prices[-1]
                result["underlying_price"] = underlying_prices[-1]

                # Calculate peg deviation
                min_len = min(len(token_prices), len(underlying_prices))
                peg_metrics = calculate_peg_deviation(token_prices[:min_len], underlying_prices[:min_len])
                result["peg_deviation"] = float(peg_metrics.get("Current Deviation", "0%").replace("%", ""))

                # Calculate risk metrics
                # Note: calculate_metrics returns formatted strings like "40.92%" (already percentages)
                risk_metrics = calculate_metrics(token_prices)
                result["volatility"] = float(risk_metrics.get("Annualized Volatility", "0%").replace("%", ""))
                result["var_95"] = abs(float(risk_metrics.get("VaR 95%", "0%").replace("%", "")))
                result["var_99"] = abs(float(risk_metrics.get("VaR 99%", "0%").replace("%", "")))
                result["cvar_95"] = abs(float(risk_metrics.get("CVaR 95%", "0%").replace("%", "")))
                result["cvar_99"] = abs(float(risk_metrics.get("CVaR 99%", "0%").replace("%", "")))
    except Exception as e:
        result["error"] = str(e)

    return result


def fetch_proof_of_reserve(config: dict) -> dict:
    """Fetch Proof of Reserve data with per-chain supply breakdown."""
    result = {
        "reserve_ratio": None,
        "reserves": None,
        "total_supply": None,
        "chain_supply": {},  # Per-chain supply breakdown
        "error": None
    }

    por_config = config.get("proof_of_reserve", {})
    token_addresses = config.get("token_addresses", [])

    # Build extended evm_chains list that includes all chains from token_addresses
    evm_chains = list(por_config.get("evm_chains", []))
    por_chain_names = {c.get("name", "").lower() for c in evm_chains}

    # Add chains from token_addresses that don't have PoR config (for supply only)
    for token_cfg in token_addresses:
        chain_name = token_cfg.get("chain", "").lower()
        token_addr = token_cfg.get("address")

        if chain_name == "solana" or not token_addr:
            continue

        if chain_name not in por_chain_names:
            evm_chains.append({
                "name": chain_name,
                "token": token_addr,
                "por": None  # No PoR feed, will only fetch supply
            })

    solana_token = por_config.get("solana_token") or config.get("solana_token")

    try:
        por_result = analyze_proof_of_reserve(
            evm_chains=evm_chains,
            solana_token=solana_token
        )

        if por_result.get("status") == "success":
            metrics = por_result.get("metrics", {})
            result["reserve_ratio"] = metrics.get("reserve_ratio", 1.0)
            result["reserves"] = metrics.get("reserves", 0)
            result["total_supply"] = metrics.get("total_supply", 0)
            result["is_fully_backed"] = metrics.get("is_fully_backed", True)

            # Extract per-chain supply data
            chain_data = por_result.get("chain_data", [])
            for chain in chain_data:
                chain_name = chain.get("name", "unknown")
                if chain.get("supply"):
                    result["chain_supply"][chain_name] = chain["supply"]

            # Add Solana supply if present
            supply_data = por_result.get("supply", {})
            if supply_data.get("solana"):
                result["chain_supply"]["solana"] = supply_data["solana"]

    except Exception as e:
        result["error"] = str(e)

    return result


def fetch_token_distribution(config: dict) -> dict:
    """Fetch token holder distribution data per chain."""
    result = {"chains": {}, "error": None}

    token_addresses = config.get("token_addresses", [])
    blockscout_apis = config.get("blockscout_apis", {})
    token_decimals = config.get("token_decimals", 8)
    solana_token = config.get("solana_token")

    # Track if we've processed Solana
    solana_processed = False

    # Process all chains from token_addresses
    for token_cfg in token_addresses:
        chain = token_cfg.get("chain", "").lower()
        address = token_cfg.get("address")

        if not address:
            continue

        try:
            # Handle Solana separately
            if chain == "solana":
                solana_processed = True
                dist_result = analyze_token_distribution(
                    token_address=address,
                    chain_name="Solana"
                )
            else:
                # EVM chains
                blockscout_url = blockscout_apis.get(chain)
                use_ankr = chain in ["arbitrum"]  # Use Ankr for chains with unreliable Blockscout

                dist_result = analyze_token_distribution(
                    token_address=address,
                    chain_name=chain.title(),
                    blockscout_url=blockscout_url,
                    use_ankr=use_ankr,
                    decimals=token_decimals
                )

            if dist_result.get("status") == "success":
                result["chains"][chain] = {
                    "gini_coefficient": dist_result.get("metrics", {}).get("gini_coefficient"),
                    "top_10_concentration": dist_result.get("metrics", {}).get("top_10_concentration_pct"),
                    "top_50_concentration": dist_result.get("metrics", {}).get("top_50_concentration_pct"),
                    "holders_analyzed": dist_result.get("metrics", {}).get("holders_analyzed"),
                    "top_holders": dist_result.get("top_holders", []),
                    "data_source": dist_result.get("data_source")
                }
        except Exception as e:
            result["chains"][chain] = {"error": str(e)}

    # Process Solana from solana_token field if not already processed
    if solana_token and not solana_processed:
        try:
            dist_result = analyze_token_distribution(
                token_address=solana_token,
                chain_name="Solana"
            )

            if dist_result.get("status") == "success":
                result["chains"]["solana"] = {
                    "gini_coefficient": dist_result.get("metrics", {}).get("gini_coefficient"),
                    "top_10_concentration": dist_result.get("metrics", {}).get("top_10_concentration_pct"),
                    "top_50_concentration": dist_result.get("metrics", {}).get("top_50_concentration_pct"),
                    "holders_analyzed": dist_result.get("metrics", {}).get("holders_analyzed"),
                    "top_holders": dist_result.get("top_holders", []),
                    "data_source": dist_result.get("data_source")
                }
        except Exception as e:
            result["chains"]["solana"] = {"error": str(e)}

    return result


def fetch_lending_data(config: dict) -> dict:
    """Fetch lending protocol data (AAVE + Compound) with TVL-weighted aggregation."""
    result = {"aave": [], "compound": [], "aggregated": {}, "error": None}

    lending_configs = config.get("lending_configs", [])
    if not lending_configs:
        result["error"] = "No lending configurations"
        return result

    # Collect (value, tvl) tuples for TVL-weighted averaging
    rlr_data = []  # [(rlr_pct, tvl), ...]
    clr_data = []  # [(clr_pct, tvl), ...]
    util_data = []  # [(util_pct, tvl), ...]

    # Track processed chains to avoid duplicates
    processed_aave_chains = set()
    processed_compound_chains = set()

    for cfg in lending_configs:
        try:
            protocol = cfg.get("protocol")
            chain = cfg.get("chain", "").capitalize()
            token_addr = cfg.get("token_address")

            if protocol == "aave" and chain in AAVE_CHAINS:
                # Only process each AAVE chain once
                if chain in processed_aave_chains:
                    continue
                processed_aave_chains.add(chain)

                market_result = analyze_aave_market(token_addr, chain, AAVE_CHAINS[chain])
                result["aave"].append(market_result)

                if market_result.get("status") == "success":
                    overview = market_result.get("market_overview", {})
                    tvl = overview.get("total_supply", 0)

                    rlr = market_result.get("rlr", {})
                    if rlr.get("rlr_supply_based") is not None and tvl > 0:
                        rlr_data.append((rlr["rlr_supply_based"], tvl))

                    clr = market_result.get("clr", {})
                    if clr.get("clr_by_value") is not None and tvl > 0:
                        clr_data.append((clr["clr_by_value"], tvl))

                    if overview.get("utilization_rate") is not None and tvl > 0:
                        util_data.append((overview["utilization_rate"], tvl))

            elif protocol == "compound" and chain in COMPOUND_MARKETS:
                # Only process each Compound chain once
                if chain in processed_compound_chains:
                    continue
                processed_compound_chains.add(chain)

                market_result = analyze_compound_market(token_addr, chain, COMPOUND_MARKETS[chain])
                result["compound"].append(market_result)

                if market_result.get("status") == "success":
                    for market in market_result.get("markets", []):
                        if market.get("supported"):
                            tvl = market.get("total_supply", 0)

                            clr = market.get("clr", {})
                            if clr.get("clr_by_value") is not None and tvl > 0:
                                clr_data.append((clr["clr_by_value"], tvl))
        except Exception as e:
            continue

    # Calculate TVL-weighted averages
    def weighted_avg(data):
        """Calculate TVL-weighted average from [(value, tvl), ...] pairs."""
        if not data:
            return None
        total_tvl = sum(tvl for _, tvl in data)
        if total_tvl == 0:
            return None
        return sum(value * tvl for value, tvl in data) / total_tvl

    if rlr_data:
        result["aggregated"]["rlr_pct"] = weighted_avg(rlr_data)
    if clr_data:
        result["aggregated"]["clr_pct"] = weighted_avg(clr_data)
    if util_data:
        result["aggregated"]["utilization_pct"] = weighted_avg(util_data)

    return result


def fetch_dex_data(config: dict) -> dict:
    """Fetch DEX pool data with detailed concentration metrics."""
    result = {"pools": [], "aggregated": {}, "error": None}

    dex_pools = config.get("dex_pools", [])
    if not dex_pools:
        result["error"] = "No DEX pool configurations"
        return result

    all_hhi = []
    total_tvl = 0

    for pool in dex_pools:
        try:
            protocol = pool.get("protocol", "").lower()
            chain = pool.get("chain")
            pool_addr = pool.get("pool_address")
            pool_name = pool.get("pool_name", "Unknown")

            pool_result = None

            if protocol == "uniswap":
                analyzer = UniswapV3Analyzer(chain, GRAPH_API_KEY)
                pool_result = analyzer.analyze_pool(pool_addr)
                pool_result["protocol"] = "Uniswap V3"
                pool_result["pool_name"] = pool_name
                pool_result["chain"] = chain

            elif protocol == "pancakeswap":
                # PancakeSwap uses the same subgraph format as Uniswap V3
                try:
                    from pancakeswap import PancakeSwapV3Analyzer
                    analyzer = PancakeSwapV3Analyzer(chain, GRAPH_API_KEY)
                    pool_result = analyzer.analyze_pool(pool_addr)
                    pool_result["protocol"] = "PancakeSwap V3"
                except ImportError:
                    # Fallback: use Uniswap analyzer with PancakeSwap subgraph
                    pool_result = {
                        "protocol": "PancakeSwap V3",
                        "pool_name": pool_name,
                        "chain": chain,
                        "pool_address": pool_addr,
                        "status": "error",
                        "error": "PancakeSwap analyzer not available"
                    }
                pool_result["pool_name"] = pool_name
                pool_result["chain"] = chain

            elif protocol == "curve":
                analyzer = CurveFinanceAnalyzer(chain)
                pool_result = analyzer.analyze_pool(pool_addr)
                pool_result["protocol"] = "Curve"
                pool_result["pool_name"] = pool_name
                pool_result["chain"] = chain

            if pool_result:
                result["pools"].append(pool_result)

                if pool_result.get("status") == "success":
                    conc = pool_result.get("concentration_metrics") or {}
                    if conc.get("hhi"):
                        tvl = pool_result.get("tvl_usd", 0)
                        all_hhi.append((conc["hhi"], tvl))
                        total_tvl += tvl

        except Exception as e:
            # Add error entry for this pool
            result["pools"].append({
                "protocol": pool.get("protocol", "Unknown"),
                "pool_name": pool.get("pool_name", "Unknown"),
                "chain": pool.get("chain", "unknown"),
                "pool_address": pool.get("pool_address", ""),
                "status": "error",
                "error": str(e)
            })

    if all_hhi and total_tvl > 0:
        result["aggregated"]["hhi"] = sum(h * t for h, t in all_hhi) / total_tvl
        result["aggregated"]["tvl_usd"] = total_tvl

    return result


def fetch_slippage_data(config: dict) -> dict:
    """Fetch slippage data from DEX aggregators."""
    result = {"chains": {}, "error": None}

    # Get token info
    token_addresses = config.get("token_addresses", [])
    price_risk = config.get("price_risk", {})
    token_decimals = config.get("token_decimals", 8)
    symbol = config.get("asset_symbol", "TOKEN")
    coingecko_id = price_risk.get("token_coingecko_id")

    # Common stablecoins to swap to
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
        }
    }

    for token_cfg in token_addresses:
        chain = token_cfg.get("chain", "").lower()
        token_addr = token_cfg.get("address")

        if chain == "solana" or not token_addr:
            continue

        if chain not in STABLECOINS:
            continue

        try:
            # Get first available stablecoin for this chain
            stablecoin_name, stablecoin_addr = next(iter(STABLECOINS[chain].items()))

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

            result["chains"][chain] = slippage_result

        except Exception as e:
            result["chains"][chain] = {"status": "error", "error": str(e)}

    return result


def fetch_data_accuracy(config: dict) -> dict:
    """Fetch data accuracy verification for DEX pools and slippage."""
    result = {"dex_accuracy": [], "slippage_accuracy": [], "error": None}

    dex_pools = config.get("dex_pools", [])

    # Verify DEX pool data accuracy
    for pool in dex_pools:
        try:
            protocol = pool.get("protocol", "").lower()
            chain = pool.get("chain", "").lower()
            pool_addr = pool.get("pool_address")
            pool_name = pool.get("pool_name", "Unknown")

            accuracy_result = {
                "protocol": protocol.title(),
                "pool_name": pool_name,
                "chain": chain,
                "pool_address": pool_addr,
                "status": "error"
            }

            if protocol == "uniswap":
                try:
                    verification = verify_uniswap_v3_accuracy(chain, pool_addr, top_n=5)
                    accuracy_result["accuracy_pct"] = verification.get("accuracy", 0)
                    accuracy_result["total_deviation_pct"] = verification.get("total_deviation", 0)
                    accuracy_result["positions_matched"] = verification.get("matched", 0)
                    accuracy_result["status"] = "success"
                    accuracy_result["data_source"] = "The Graph Subgraph"
                except Exception as e:
                    accuracy_result["error"] = str(e)

            elif protocol == "pancakeswap":
                try:
                    verification = verify_pancakeswap_v3_accuracy(chain, pool_addr, top_n=5)
                    accuracy_result["accuracy_pct"] = verification.get("accuracy", 0)
                    accuracy_result["total_deviation_pct"] = verification.get("total_deviation", 0)
                    accuracy_result["positions_matched"] = verification.get("matched", 0)
                    accuracy_result["status"] = "success"
                    accuracy_result["data_source"] = "The Graph Subgraph"
                except Exception as e:
                    accuracy_result["error"] = str(e)

            elif protocol == "curve":
                try:
                    # For Curve, we verify the gauge/LP token accuracy
                    gauge_addr = pool.get("gauge_address", pool_addr)
                    verification = verify_curve_lp_accuracy(chain, gauge_addr, top_n=5)
                    accuracy_result["accuracy_pct"] = verification.get("accuracy", 0)
                    accuracy_result["total_deviation_pct"] = verification.get("total_deviation", 0)
                    accuracy_result["positions_matched"] = verification.get("matched", 0)
                    accuracy_result["status"] = "success"
                    accuracy_result["data_source"] = "Blockscout API"
                except Exception as e:
                    accuracy_result["error"] = str(e)

            result["dex_accuracy"].append(accuracy_result)

        except Exception as e:
            result["dex_accuracy"].append({
                "protocol": pool.get("protocol", "Unknown"),
                "pool_name": pool.get("pool_name", "Unknown"),
                "chain": pool.get("chain", "unknown"),
                "status": "error",
                "error": str(e)
            })

    return result


def fetch_oracle_data(config: dict) -> dict:
    """Fetch oracle freshness and cross-chain lag data."""
    result = {
        "freshness": [],
        "lag": None,
        "error": None
    }

    # Get oracle freshness config
    oracle_freshness_config = config.get("oracle_freshness", {})
    price_feeds = oracle_freshness_config.get("price_feeds", [])

    # Get oracle lag config
    oracle_lag_config = config.get("oracle_lag", {})
    por_feed_1 = oracle_lag_config.get("por_feed_1", {})
    por_feed_2 = oracle_lag_config.get("por_feed_2", {})

    # Fetch freshness for each price feed
    for feed in price_feeds:
        chain = feed.get("chain", "ethereum")
        address = feed.get("address")
        name = feed.get("name", "Unknown")

        if not address:
            continue

        try:
            freshness_result = get_oracle_freshness(
                oracle_addresses=[address],
                chain_name=chain
            )

            if freshness_result.get("status") == "success":
                oracles = freshness_result.get("oracles", [])
                if oracles:
                    oracle = oracles[0]
                    result["freshness"].append({
                        "name": name,
                        "chain": chain,
                        "address": address,
                        "price": oracle.get("price"),
                        "minutes_since_update": oracle.get("minutes_since_update"),
                        "hours_since_update": oracle.get("hours_since_update"),
                        "last_update": oracle.get("last_update_datetime"),
                        "status": "success"
                    })
            else:
                result["freshness"].append({
                    "name": name,
                    "chain": chain,
                    "address": address,
                    "status": "error",
                    "error": freshness_result.get("error", "Unknown error")
                })
        except Exception as e:
            result["freshness"].append({
                "name": name,
                "chain": chain,
                "address": address,
                "status": "error",
                "error": str(e)
            })

    # Fetch cross-chain oracle lag (comparing PoR feeds)
    if por_feed_1.get("address") and por_feed_2.get("address"):
        try:
            lag_result = analyze_oracle_lag(
                chain1_name=por_feed_1.get("chain", "ethereum"),
                oracle1_address=por_feed_1.get("address"),
                chain2_name=por_feed_2.get("chain", "base"),
                oracle2_address=por_feed_2.get("address")
            )

            if lag_result.get("status") == "success":
                result["lag"] = {
                    "chain1": lag_result.get("chain1", {}).get("name"),
                    "chain2": lag_result.get("chain2", {}).get("name"),
                    "lag_seconds": lag_result.get("lag_seconds"),
                    "lag_minutes": lag_result.get("lag_minutes"),
                    "ahead_chain": lag_result.get("ahead_chain"),
                    "chain1_data": lag_result.get("chain1", {}).get("data"),
                    "chain2_data": lag_result.get("chain2", {}).get("data"),
                    "status": "success"
                }
            else:
                result["lag"] = {
                    "status": "error",
                    "error": lag_result.get("error", "Unknown error")
                }
        except Exception as e:
            result["lag"] = {
                "status": "error",
                "error": str(e)
            }

    return result


def build_scoring_metrics(config: dict, fetched_data: dict) -> dict:
    """Build scoring metrics from config and fetched data."""
    metrics = {}

    # Asset metadata
    metrics["asset_name"] = config.get("asset_name", "Unknown")
    metrics["asset_symbol"] = config.get("asset_symbol", "???")
    metrics["asset_type"] = config.get("asset_type", "other")
    metrics["underlying"] = config.get("underlying")

    # Audit data
    metrics["audit_data"] = config.get("audit_data")

    # Deployment date
    if config.get("deployment_date"):
        try:
            metrics["deployment_date"] = datetime.fromisoformat(config["deployment_date"]).replace(tzinfo=timezone.utc)
        except:
            metrics["deployment_date"] = None
    else:
        metrics["deployment_date"] = None

    # Incidents
    metrics["incidents"] = config.get("incidents", [])

    # Multisig configs
    multisig = {}
    for cfg in config.get("multisig_configs", []):
        if cfg.get("role_name"):
            multisig[cfg["role_name"]] = {
                "is_multisig": cfg.get("is_multisig", False),
                "is_eoa": cfg.get("is_eoa", False),
                "threshold": cfg.get("threshold", 1),
                "owners_count": cfg.get("owners_count", 1),
            }
    metrics["multisig_configs"] = multisig

    metrics["has_timelock"] = config.get("has_timelock", False)
    metrics["timelock_hours"] = config.get("timelock_hours", 0)
    metrics["custody_model"] = config.get("custody_model", "unknown")
    metrics["has_blacklist"] = config.get("has_blacklist", False)
    metrics["blacklist_control"] = config.get("blacklist_control", "none")
    metrics["critical_roles"] = config.get("critical_roles", ["owner", "admin"])
    metrics["role_weights"] = config.get("role_weights")

    # From fetched price data
    price_data = fetched_data.get("price_risk", {}) or {}
    metrics["peg_deviation_pct"] = price_data.get("peg_deviation", 0.1)
    metrics["volatility_annualized_pct"] = price_data.get("volatility", 50)
    metrics["var_95_pct"] = price_data.get("var_95", 5)

    # From fetched DEX data
    dex_data = fetched_data.get("dex", {}) or {}
    dex_agg = dex_data.get("aggregated", {}) or {}
    metrics["hhi"] = dex_agg.get("hhi", 2000)
    metrics["slippage_100k_pct"] = 0.5  # Would need aggregator API
    metrics["slippage_500k_pct"] = 1.0
    metrics["chain_distribution"] = {}

    # From fetched lending data
    lending_data = fetched_data.get("lending", {}) or {}
    lending_agg = lending_data.get("aggregated", {}) or {}
    metrics["clr_pct"] = lending_agg.get("clr_pct", 5)
    metrics["rlr_pct"] = lending_agg.get("rlr_pct", 10)
    metrics["utilization_pct"] = lending_agg.get("utilization_pct", 50)

    # From fetched PoR data
    por_data = fetched_data.get("proof_of_reserve", {}) or {}
    metrics["reserve_ratio"] = por_data.get("reserve_ratio", 1.0)
    metrics["oracle_freshness_minutes"] = 30  # Would need oracle query
    metrics["cross_chain_lag_minutes"] = 15

    return metrics


# =============================================================================
# TAB 0: CONFIGURATION
# =============================================================================

def render_tab_configuration():
    st.header("⚙️ Configuration")
    st.markdown("Load token configuration for analysis.")

    config_method = st.radio("Configuration Method", ["Upload JSON", "Manual Entry"], horizontal=True)

    if config_method == "Upload JSON":
        uploaded_file = st.file_uploader("Choose a JSON file", type=["json"])

        if uploaded_file is not None:
            try:
                config = json.load(uploaded_file)
                st.session_state.config = config
                st.success(f"✅ Loaded configuration for: **{config.get('asset_name', 'Unknown')}**")

                with st.expander("View Configuration", expanded=False):
                    st.json(config)
            except Exception as e:
                st.error(f"Error loading JSON: {e}")
    else:
        st.info("Manual entry form - fill in required fields below")
        render_manual_form()

    # Run Analysis
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        fetch_live = st.checkbox("Fetch live data from chains", value=False,
                                  help="If checked, will fetch real data from AAVE, Compound, DEX pools, etc. This may take several minutes.")

        if st.button("🚀 Run Full Analysis", type="primary", use_container_width=True):
            run_full_analysis(fetch_live_data=fetch_live)


def render_manual_form():
    """Simplified manual form."""
    st.subheader("Asset Information")
    col1, col2 = st.columns(2)
    with col1:
        asset_name = st.text_input("Asset Name", key="form_asset_name")
        asset_type = st.selectbox("Asset Type", ASSET_TYPES, key="form_asset_type")
    with col2:
        asset_symbol = st.text_input("Asset Symbol", key="form_asset_symbol")
        underlying = st.text_input("Underlying Asset", key="form_underlying")

    st.subheader("Security")
    col1, col2 = st.columns(2)
    with col1:
        auditor = st.text_input("Auditor", key="form_auditor")
        audit_date = st.text_input("Audit Date (YYYY-MM)", key="form_audit_date")
    with col2:
        deployment_date = st.date_input("Deployment Date", key="form_deployment_date", value=None)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        critical = st.number_input("Critical Issues", min_value=0, key="form_critical")
    with col2:
        high = st.number_input("High Issues", min_value=0, key="form_high")
    with col3:
        medium = st.number_input("Medium Issues", min_value=0, key="form_medium")
    with col4:
        low = st.number_input("Low Issues", min_value=0, key="form_low")

    st.subheader("Governance")
    col1, col2 = st.columns(2)
    with col1:
        custody = st.selectbox("Custody Model", CUSTODY_MODEL_OPTIONS, key="form_custody")
        has_timelock = st.checkbox("Has Timelock", key="form_timelock")
        timelock_hours = st.number_input("Timelock Hours", min_value=0.0, key="form_timelock_hours")
    with col2:
        has_blacklist = st.checkbox("Has Blacklist", key="form_blacklist")
        blacklist_control = st.selectbox("Blacklist Control", BLACKLIST_CONTROLS, key="form_blacklist_control")

    if st.button("Save Configuration"):
        config = {
            "asset_name": asset_name,
            "asset_symbol": asset_symbol,
            "asset_type": asset_type,
            "underlying": underlying,
            "audit_data": {
                "auditor": auditor,
                "date": audit_date,
                "issues": {"critical": critical, "high": high, "medium": medium, "low": low}
            } if auditor else None,
            "deployment_date": deployment_date.isoformat() if deployment_date else None,
            "multisig_configs": [],
            "has_timelock": has_timelock,
            "timelock_hours": timelock_hours,
            "custody_model": custody,
            "has_blacklist": has_blacklist,
            "blacklist_control": blacklist_control,
        }
        st.session_state.config = config
        st.success("Configuration saved!")


def run_full_analysis(fetch_live_data: bool = False):
    """Run the complete analysis."""
    config = st.session_state.get("config")

    if not config:
        st.error("Please load a configuration first.")
        return

    if not IMPORTS_OK:
        st.error(f"Import error: {IMPORT_ERROR}")
        return

    progress = st.progress(0, text="Starting analysis...")
    fetched_data = {}

    try:
        if fetch_live_data and DATA_SCRIPTS_OK:
            # Fetch live data
            progress.progress(8, text="Fetching price data from CoinGecko...")
            fetched_data["price_risk"] = fetch_price_data(config)

            progress.progress(20, text="Fetching Proof of Reserve data...")
            fetched_data["proof_of_reserve"] = fetch_proof_of_reserve(config)

            progress.progress(32, text="Fetching token distribution data...")
            fetched_data["token_distribution"] = fetch_token_distribution(config)

            progress.progress(44, text="Fetching lending protocol data...")
            fetched_data["lending"] = fetch_lending_data(config)

            progress.progress(56, text="Fetching DEX pool data...")
            fetched_data["dex"] = fetch_dex_data(config)

            progress.progress(68, text="Fetching slippage data from aggregators...")
            fetched_data["slippage"] = fetch_slippage_data(config)

            progress.progress(72, text="Verifying data accuracy...")
            fetched_data["data_accuracy"] = fetch_data_accuracy(config)

            progress.progress(78, text="Fetching oracle data...")
            fetched_data["oracle"] = fetch_oracle_data(config)
        else:
            # Use defaults
            fetched_data = {
                "price_risk": {"peg_deviation": 0.1, "volatility": 50, "var_95": 5},
                "proof_of_reserve": {"reserve_ratio": 1.0, "chain_supply": {}},
                "token_distribution": {"chains": {}},
                "lending": {"aggregated": {"clr_pct": 5, "rlr_pct": 10, "utilization_pct": 50}},
                "dex": {"aggregated": {"hhi": 2000}, "pools": []},
                "slippage": {"chains": {}},
                "data_accuracy": {"dex_accuracy": []},
                "oracle": {"freshness": [], "lag": None},
            }

        progress.progress(80, text="Building scoring metrics...")
        scoring_metrics = build_scoring_metrics(config, fetched_data)

        progress.progress(90, text="Calculating risk score...")
        risk_score = calculate_asset_risk_score(scoring_metrics)

        # Save to session state
        st.session_state.fetched_data = fetched_data
        st.session_state.scoring_metrics = scoring_metrics
        st.session_state.risk_score = risk_score
        st.session_state.analysis_run = True

        progress.progress(100, text="Analysis complete!")
        time.sleep(0.5)
        progress.empty()

        st.success("✅ Analysis complete! Navigate to the **Risk Score** tab to view results.")

    except Exception as e:
        progress.empty()
        st.error(f"Error during analysis: {e}")
        st.code(traceback.format_exc())


# =============================================================================
# TAB 1: RISK SCORE
# =============================================================================

def render_tab_risk_score():
    st.header("📊 Risk Score")

    if not st.session_state.get("analysis_run"):
        st.info("👈 Run an analysis first in the **Configuration** tab.")
        return

    risk_score = st.session_state.risk_score
    config = st.session_state.config

    # Asset header
    asset = risk_score.get("asset", {})
    st.markdown(f"## {asset.get('name', 'Unknown')} ({asset.get('symbol', '???')})")

    # Stage 1: Primary Checks
    st.subheader("Stage 1: Qualification Checklist")
    primary = risk_score.get("primary_checks", {})

    if not risk_score.get("qualified"):
        st.error(f"⛔ **DISQUALIFIED** - {primary.get('summary', '')}")
    else:
        st.success(f"✅ **QUALIFIED** - {primary.get('summary', '')}")

    cols = st.columns(3)
    for i, check in enumerate(primary.get("checks", [])):
        with cols[i]:
            status = check.get("status", "unknown")
            icon = "✅" if status == "pass" else "❌"
            st.markdown(f"{icon} **{check.get('name')}**")
            st.caption(check.get("condition", ""))

    if not risk_score.get("qualified"):
        return

    st.divider()

    # Stage 2: Score
    st.subheader("Stage 2: Secondary Scoring")
    overall = risk_score.get("overall", {})
    grade = overall.get("grade", "?")
    score = overall.get("score", 0)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        color = get_grade_color(grade)
        st.markdown(f"""
        <div style="text-align: center; padding: 20px; background-color: {color}; border-radius: 10px; color: white;">
            <h1 style="margin: 0;">{grade}</h1>
            <h2 style="margin: 0;">{score:.1f} / 100</h2>
            <p style="margin: 5px 0 0 0;">{overall.get('label', '')} - {overall.get('risk_level', '')}</p>
        </div>
        """, unsafe_allow_html=True)

    # Circuit breakers
    cb = risk_score.get("circuit_breakers", {})
    triggered = cb.get("triggered", [])
    if triggered:
        st.warning(f"⚠️ **{len(triggered)} Circuit Breaker(s) Triggered**")
        for breaker in triggered:
            st.markdown(f"- **{breaker.get('name')}**: {breaker.get('effect')}")

    st.divider()

    # Category breakdown
    st.subheader("Category Breakdown")
    categories = risk_score.get("categories", {})

    cols = st.columns(3)
    for i, (key, cat) in enumerate(categories.items()):
        with cols[i % 3]:
            cat_grade = cat.get("grade", "?")
            cat_score = cat.get("score", 0)
            cat_color = get_grade_color(cat_grade)
            st.markdown(f"""
            <div style="padding: 10px; border-left: 4px solid {cat_color}; margin-bottom: 10px;">
                <strong>{cat.get('category', key)}</strong><br>
                <span style="font-size: 24px; color: {cat_color};">{cat_grade}</span>
                <span>({cat_score:.1f})</span><br>
                <small>Weight: {cat.get('weight', 0)*100:.0f}%</small>
            </div>
            """, unsafe_allow_html=True)

    # Detailed breakdown
    st.subheader("Score Justifications")
    for key, cat in categories.items():
        with st.expander(f"{cat.get('category', key)} - {cat.get('grade', '?')} ({cat.get('score', 0):.1f})"):
            st.caption(cat.get("weight_justification", ""))

            breakdown = cat.get("breakdown", {})
            for metric_key, metric in breakdown.items():
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.metric(metric_key.replace("_", " ").title(), f"{metric.get('score', 0):.1f}")
                with col2:
                    st.markdown(metric.get("justification", ""))


# =============================================================================
# TAB 2: SCORING METHODOLOGY
# =============================================================================

def render_tab_methodology_scoring():
    st.header("📖 Scoring Methodology")

    st.markdown("""
    ## Two-Stage Risk Evaluation

    ### Stage 1: Qualification Checklist (Binary Pass/Fail)

    These checks must ALL pass before scoring:
    """)

    if IMPORTS_OK:
        for check_id, info in PRIMARY_CHECKS.items():
            st.markdown(f"- **{info['name']}**: {info['condition']}")

    st.markdown("""
    ### Stage 2: Weighted Category Scoring

    Six risk categories are evaluated:
    """)

    if IMPORTS_OK:
        df = pd.DataFrame([
            {"Category": k.replace("_", " ").title(), "Weight": f"{v['weight']*100:.0f}%"}
            for k, v in CATEGORY_WEIGHTS.items()
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### Grade Scale")

    if IMPORTS_OK:
        df = pd.DataFrame([
            {"Grade": g, "Range": f"{info['min']}-{info['max']}", "Label": info['label'], "Risk Level": info['risk_level']}
            for g, info in GRADE_SCALE.items()
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### Circuit Breakers")

    if IMPORTS_OK:
        for name, breaker in CIRCUIT_BREAKERS.items():
            effect = f"Max Grade: {breaker.get('max_grade')}" if 'max_grade' in breaker else f"Multiplier: {breaker.get('multiplier')}"
            st.markdown(f"- **{name.replace('_', ' ').title()}**: {effect}")
            st.caption(f"  {breaker.get('justification', '')[:100]}...")


# =============================================================================
# TAB 3: PROTOCOL INFO
# =============================================================================

def render_tab_protocol_info():
    st.header("🏛️ Protocol Info")

    config = st.session_state.get("config")
    if not config:
        st.info("Load a configuration first.")
        return

    # Protocol Age
    st.subheader("Protocol Age")
    deployment = config.get("deployment_date")
    if deployment:
        days = days_since(deployment)
        st.metric("Days Since Launch", days if days else "N/A")
        st.caption(f"Deployment Date: {deployment}")
    else:
        st.caption("Deployment date not specified")

    st.divider()

    # Security
    st.subheader("Security")
    col1, col2 = st.columns(2)

    with col1:
        audit = config.get("audit_data")
        if audit:
            st.markdown("**Audit Information**")
            st.markdown(f"- Auditor: **{audit.get('auditor', 'N/A')}**")
            st.markdown(f"- Date: {audit.get('date', 'N/A')}")
            issues = audit.get("issues", {})
            st.markdown(f"- Critical Issues: {issues.get('critical', 0)}")
            st.markdown(f"- High Issues: {issues.get('high', 0)}")
            st.markdown(f"- Medium Issues: {issues.get('medium', 0)}")
            st.markdown(f"- Low Issues: {issues.get('low', 0)}")
        else:
            st.warning("No audit data available")

    with col2:
        incidents = config.get("incidents", [])
        st.markdown("**Incident History**")
        if incidents:
            for inc in incidents:
                st.markdown(f"- {inc.get('description', 'Unknown incident')}")
        else:
            st.success("No security incidents recorded")

    st.divider()

    # Token Details
    st.subheader("Token Details")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"- **Symbol**: {config.get('asset_symbol', 'N/A')}")
        st.markdown(f"- **Type**: {config.get('asset_type', 'N/A')}")
        st.markdown(f"- **Decimals**: {config.get('token_decimals', 'N/A')}")
    with col2:
        st.markdown(f"- **Underlying**: {config.get('underlying', 'N/A')}")
        price_risk = config.get("price_risk", {})
        st.markdown(f"- **CoinGecko ID**: {price_risk.get('token_coingecko_id', 'N/A')}")

    st.divider()

    # Governance & Custody
    st.subheader("Governance & Custody")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Custody**")
        st.markdown(f"- Model: **{config.get('custody_model', 'unknown').replace('_', ' ').title()}**")
        st.markdown(f"- Custodian: {config.get('custodian', 'N/A')}")
        st.markdown(f"- Has Insurance: {'Yes' if config.get('has_insurance') else 'No'}")

    with col2:
        st.markdown("**Security Features**")
        st.markdown(f"- Timelock: {'Yes' if config.get('has_timelock') else 'No'} ({config.get('timelock_hours', 0)}h)")
        st.markdown(f"- Blacklist: {'Yes' if config.get('has_blacklist') else 'No'} ({config.get('blacklist_control', 'none')})")

    # Admin Roles
    st.markdown("**Admin Roles**")
    multisig_configs = config.get("multisig_configs", [])
    if multisig_configs:
        df = pd.DataFrame([
            {
                "Role": cfg.get("role_name", "N/A"),
                "Address": cfg.get("address", "N/A")[:10] + "..." if cfg.get("address") else "N/A",
                "Type": "Multisig" if cfg.get("is_multisig") else ("EOA" if cfg.get("is_eoa") else "Unknown"),
                "Threshold": f"{cfg.get('threshold', 1)}/{cfg.get('owners_count', 1)}" if cfg.get("is_multisig") else "N/A"
            }
            for cfg in multisig_configs
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("No admin roles configured")

    st.divider()

    # Oracle Feeds
    st.subheader("Oracle Feeds")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Price Feeds**")
        oracle_freshness = config.get("oracle_freshness", {})
        feeds = oracle_freshness.get("price_feeds", [])
        if feeds:
            for feed in feeds:
                st.markdown(f"- {feed.get('name', feed.get('chain', 'Unknown'))}: `{feed.get('address', 'N/A')[:20]}...`")
        else:
            st.caption("No price feeds configured")

    with col2:
        st.markdown("**Proof of Reserve Feeds**")
        por = config.get("proof_of_reserve", {})
        chains = por.get("evm_chains", [])
        if chains:
            for chain in chains:
                st.markdown(f"- {chain.get('name', 'Unknown').title()}: `{chain.get('por', 'N/A')[:20]}...`")
        else:
            st.caption("No PoR feeds configured")


# =============================================================================
# TAB 4: SUPPLY & DISTRIBUTION
# =============================================================================

def render_tab_supply():
    st.header("💰 Supply & Distribution")

    config = st.session_state.get("config")
    fetched = st.session_state.get("fetched_data") or {}

    if not config:
        st.info("Load a configuration first.")
        return

    por = fetched.get("proof_of_reserve") or {}
    chain_supply = por.get("chain_supply") or {}
    token_dist = fetched.get("token_distribution") or {}
    dist_chains = token_dist.get("chains") or {}

    # =========================================================================
    # CROSS-CHAIN SUPPLY SECTION
    # =========================================================================
    st.subheader("Cross-Chain Supply")

    col1, col2 = st.columns(2)

    with col1:
        # Build supply data from proof_of_reserve chain_supply
        if chain_supply:
            supply_data = []
            for chain_name, supply in chain_supply.items():
                supply_data.append({
                    "Chain": chain_name.title(),
                    "Supply": supply
                })

            if supply_data:
                df_supply = pd.DataFrame(supply_data)
                total_supply = df_supply["Supply"].sum()

                # Add percentage column
                df_supply["% of Total"] = (df_supply["Supply"] / total_supply * 100).round(2)
                df_supply["Supply"] = df_supply["Supply"].apply(lambda x: f"{x:,.4f}")

                # Display pie chart
                fig = px.pie(
                    values=[d["Supply"] for d in supply_data],
                    names=[d["Chain"] for d in supply_data],
                    title="Supply Distribution by Chain",
                    hole=0.4
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(showlegend=True, height=350)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{id(fig)}")
        else:
            st.info("No per-chain supply data available. Enable live data fetching.")

    with col2:
        # Display supply table
        if chain_supply:
            st.markdown("**Supply by Chain**")

            # Build detailed table
            table_data = []
            for chain_name, supply in chain_supply.items():
                # Get token address for this chain
                addr = "N/A"
                for token_cfg in config.get("token_addresses", []):
                    if token_cfg.get("chain", "").lower() == chain_name.lower():
                        addr = token_cfg.get("address", "N/A")[:16] + "..."
                        break

                # Check for Solana
                if chain_name.lower() == "solana" and config.get("solana_token"):
                    addr = config.get("solana_token", "")[:16] + "..."

                table_data.append({
                    "Chain": chain_name.title(),
                    "Supply": f"{supply:,.4f}",
                    "Address": addr
                })

            df_table = pd.DataFrame(table_data)
            st.dataframe(df_table, use_container_width=True, hide_index=True)

            # Total supply metric
            total = sum(chain_supply.values())
            st.metric("Total Supply", f"{total:,.4f}")
        else:
            # Fallback to showing token addresses from config
            token_addrs = config.get("token_addresses", [])
            solana_token = config.get("solana_token")

            table_data = []
            for addr in token_addrs:
                table_data.append({
                    "Chain": addr.get("chain", "N/A").title(),
                    "Address": addr.get("address", "N/A")[:20] + "..."
                })
            if solana_token:
                table_data.append({
                    "Chain": "Solana",
                    "Address": solana_token[:20] + "..."
                })

            if table_data:
                df = pd.DataFrame(table_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

            if por.get("total_supply"):
                st.metric("Total Supply", format_number(por["total_supply"], 4))

    st.divider()

    # =========================================================================
    # TOKEN DISTRIBUTION SECTION
    # =========================================================================
    st.subheader("Token Distribution")

    if dist_chains:
        col1, col2 = st.columns(2)

        with col1:
            # Gini Coefficient per chain
            st.markdown("**Gini Coefficient by Chain**")

            gini_data = []
            for chain_name, data in dist_chains.items():
                if data.get("gini_coefficient") is not None:
                    gini_data.append({
                        "Chain": chain_name.title(),
                        "Gini": data["gini_coefficient"],
                        "Holders": data.get("holders_analyzed", 0),
                        "Source": data.get("data_source", "N/A")
                    })

            if gini_data:
                df_gini = pd.DataFrame(gini_data)
                st.dataframe(
                    df_gini.style.format({"Gini": "{:.4f}"}),
                    use_container_width=True,
                    hide_index=True
                )

                # Interpretation
                avg_gini = df_gini["Gini"].mean()
                if avg_gini < 0.5:
                    st.success(f"Average Gini: {avg_gini:.4f} - Relatively even distribution")
                elif avg_gini < 0.7:
                    st.warning(f"Average Gini: {avg_gini:.4f} - Moderate concentration")
                else:
                    st.error(f"Average Gini: {avg_gini:.4f} - High concentration")
            else:
                st.info("No Gini data available")

        with col2:
            # Whale Concentration Bar Chart
            st.markdown("**Whale Concentration by Chain**")

            conc_data = []
            for chain_name, data in dist_chains.items():
                if data.get("top_10_concentration") is not None:
                    conc_data.append({
                        "Chain": chain_name.title(),
                        "Top 10%": data.get("top_10_concentration", 0),
                        "Top 50%": data.get("top_50_concentration", 0)
                    })

            if conc_data:
                chains = [d["Chain"] for d in conc_data]
                top_10 = [d["Top 10%"] for d in conc_data]
                top_50 = [d["Top 50%"] for d in conc_data]

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name='Top 10 Holders',
                    x=chains,
                    y=top_10,
                    marker_color='#ef4444'
                ))
                fig.add_trace(go.Bar(
                    name='Top 50 Holders',
                    x=chains,
                    y=top_50,
                    marker_color='#3b82f6'
                ))

                fig.update_layout(
                    barmode='group',
                    title="Holder Concentration (%)",
                    yaxis_title="% of Supply",
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{id(fig)}")

                # Summary table
                df_conc = pd.DataFrame(conc_data)
                st.dataframe(
                    df_conc.style.format({"Top 10%": "{:.2f}%", "Top 50%": "{:.2f}%"}),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No concentration data available")
    else:
        st.info("Token distribution data requires live chain queries. Enable 'Fetch live data' and run analysis.")


# =============================================================================
# TAB 5: LENDING
# =============================================================================

def render_tab_lending():
    st.header("🏦 Lending (Aave + Compound)")

    config = st.session_state.get("config")
    fetched = st.session_state.get("fetched_data") or {}

    if not config:
        st.info("Load a configuration first.")
        return

    lending_data = fetched.get("lending") or {}
    symbol = config.get("asset_symbol", "Token")

    # =========================================================================
    # AAVE V3 SECTION
    # =========================================================================
    st.subheader("Aave V3")
    aave_markets = lending_data.get("aave", [])

    if aave_markets:
        for market in aave_markets:
            if market.get("status") == "success":
                chain_name = market.get("chain", "Unknown")
                market_symbol = market.get("symbol", symbol)

                with st.expander(f"📊 {chain_name} - {market_symbol}", expanded=True):
                    overview = market.get("market_overview") or {}

                    # Market Overview
                    st.markdown("##### Market Overview")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Supply", f"{overview.get('total_supply', 0):,.4f} {market_symbol}")
                        st.metric("Supply APY", format_percentage(overview.get("supply_apy", 0)))
                    with col2:
                        st.metric("Total Borrow", f"{overview.get('total_borrow', 0):,.4f} {market_symbol}")
                        st.metric("Borrow APY", format_percentage(overview.get("borrow_apy", 0)))
                    with col3:
                        st.metric("Utilization Rate", format_percentage(overview.get("utilization_rate", 0)))
                        col3a, col3b = st.columns(2)
                        with col3a:
                            st.metric("LTV", f"{overview.get('ltv', 0):.0f}%")
                        with col3b:
                            st.metric("Liq. Threshold", f"{overview.get('liquidation_threshold', 0):.0f}%")

                    st.divider()

                    # RLR Section
                    rlr = market.get("rlr") or {}
                    if rlr and not rlr.get("error"):
                        st.markdown("##### 🔄 Recursive Lending Ratio (RLR)")

                        col1, col2 = st.columns(2)

                        with col1:
                            # RLR Table
                            rlr_data = [
                                {"Metric": "Loopers Detected", "Value": f"{rlr.get('loopers_count', 0)} addresses"},
                                {"Metric": "Looped Borrow", "Value": f"{rlr.get('looped_borrow', 0):,.4f} {market_symbol}"},
                                {"Metric": "RLR (Supply-based)", "Value": f"{rlr.get('rlr_supply_based', 0):.2f}%"},
                                {"Metric": "RLR (Borrow-based)", "Value": f"{rlr.get('rlr_borrow_based', 0):.2f}%"},
                            ]
                            df_rlr = pd.DataFrame(rlr_data)
                            st.dataframe(df_rlr, use_container_width=True, hide_index=True)

                        with col2:
                            # Leverage Statistics Table
                            leverage_stats = rlr.get("leverage_stats") or {}
                            if leverage_stats:
                                st.markdown("**Looper Leverage Statistics**")
                                lev_data = [
                                    {"Statistic": "Average Leverage", "Value": f"{leverage_stats.get('average', 0):.2f}x"},
                                    {"Statistic": "Max Leverage", "Value": f"{leverage_stats.get('max', 0):.2f}x"},
                                    {"Statistic": "Min Leverage", "Value": f"{leverage_stats.get('min', 0):.2f}x"},
                                ]
                                df_lev = pd.DataFrame(lev_data)
                                st.dataframe(df_lev, use_container_width=True, hide_index=True)

                        # Top Loopers Table
                        top_loopers = rlr.get("top_loopers", [])
                        if top_loopers:
                            st.markdown("**Top Loopers by Leverage**")
                            looper_data = []
                            for i, looper in enumerate(top_loopers[:10], 1):
                                addr = looper.get("address", "")
                                looper_data.append({
                                    "#": i,
                                    "Address": f"{addr[:10]}...{addr[-8:]}" if len(addr) > 18 else addr,
                                    f"Supply ({market_symbol})": f"{looper.get('supply', 0):,.4f}",
                                    f"Borrow ({market_symbol})": f"{looper.get('borrow', 0):,.4f}",
                                    "Leverage": f"{looper.get('leverage', 0):.2f}x"
                                })
                            df_loopers = pd.DataFrame(looper_data)
                            st.dataframe(df_loopers, use_container_width=True, hide_index=True)

                    st.divider()

                    # CLR Section
                    clr = market.get("clr") or {}
                    if clr and not clr.get("error"):
                        st.markdown("##### ⚠️ Cascade Liquidation Risk (CLR)")

                        col1, col2 = st.columns(2)

                        with col1:
                            # CLR Table
                            clr_data = [
                                {"Metric": "CLR (by count)", "Value": f"{clr.get('clr_by_count', 0):.2f}%"},
                                {"Metric": "CLR (by value)", "Value": f"{clr.get('clr_by_value', 0):.2f}%"},
                                {"Metric": "Positions Analyzed", "Value": f"{clr.get('positions_analyzed', 0)}"},
                                {"Metric": "Debt Analyzed", "Value": f"${clr.get('debt_analyzed_usd', 0):,.2f}"},
                                {"Metric": "Debt at Risk", "Value": f"${clr.get('debt_at_risk_usd', 0):,.2f}"},
                            ]
                            df_clr = pd.DataFrame(clr_data)
                            st.dataframe(df_clr, use_container_width=True, hide_index=True)

                        with col2:
                            # Health Factor Distribution Bar Chart
                            risk_dist = clr.get("risk_distribution") or {}
                            if risk_dist:
                                st.markdown("**Health Factor Distribution**")

                                hf_categories = ["Critical\n(HF<1.0)", "High Risk\n(1.0-1.05)", "At Risk\n(1.05-1.1)", "Moderate\n(1.1-1.25)", "Safe\n(HF≥1.25)"]
                                hf_values = [
                                    risk_dist.get("critical", 0),
                                    risk_dist.get("high_risk", 0),
                                    risk_dist.get("at_risk", 0),
                                    risk_dist.get("moderate", 0),
                                    risk_dist.get("safe", 0)
                                ]
                                hf_colors = ["#ef4444", "#f97316", "#eab308", "#84cc16", "#22c55e"]

                                fig = go.Figure(data=[
                                    go.Bar(
                                        x=hf_categories,
                                        y=hf_values,
                                        marker_color=hf_colors,
                                        text=hf_values,
                                        textposition='auto'
                                    )
                                ])
                                fig.update_layout(
                                    title=f"Health Factor Distribution ({chain_name})",
                                    yaxis_title="Number of Positions",
                                    height=300,
                                    showlegend=False
                                )
                                st.plotly_chart(fig, use_container_width=True, key=f"chart_{id(fig)}")
    else:
        st.info("No AAVE data available. Enable live data fetching to retrieve lending metrics.")

    st.divider()

    # =========================================================================
    # COMPOUND V3 SECTION
    # =========================================================================
    st.subheader("Compound V3")
    compound_markets = lending_data.get("compound", [])

    if compound_markets:
        for chain_result in compound_markets:
            if chain_result.get("status") == "success":
                chain_name = chain_result.get("chain", "Unknown")

                for market in chain_result.get("markets", []):
                    if not market.get("supported"):
                        continue

                    market_name = market.get("market_name", "Unknown")
                    base_asset = market.get("base_asset", market_name)

                    with st.expander(f"📊 {chain_name} - {market_name} Market", expanded=True):
                        overview = market.get("market_overview") or {}
                        collateral_info = market.get("collateral_info") or {}

                        # Market Overview
                        st.markdown("##### Market Overview")
                        col1, col2 = st.columns(2)

                        with col1:
                            overview_data = [
                                {"Metric": "Base Asset", "Value": base_asset},
                                {"Metric": "Total Supply", "Value": f"{overview.get('total_supply', 0):,.2f} {base_asset}"},
                                {"Metric": "Total Borrow", "Value": f"{overview.get('total_borrow', 0):,.2f} {base_asset}"},
                                {"Metric": "Supply APY", "Value": f"{overview.get('supply_apy', 0):.2f}%"},
                                {"Metric": "Borrow APY", "Value": f"{overview.get('borrow_apy', 0):.2f}%"},
                                {"Metric": "Utilization", "Value": f"{overview.get('utilization', 0):.2f}%"},
                            ]
                            df_overview = pd.DataFrame(overview_data)
                            st.dataframe(df_overview, use_container_width=True, hide_index=True)

                        with col2:
                            # Collateral Info
                            st.markdown(f"**{symbol} Collateral**")
                            coll_data = [
                                {"Metric": "Total Supplied", "Value": f"{collateral_info.get('total_supplied', 0):,.4f} {symbol}"},
                                {"Metric": "Supply Cap", "Value": f"{collateral_info.get('supply_cap', 0):,.4f} {symbol}"},
                                {"Metric": "Cap Utilization", "Value": f"{collateral_info.get('cap_utilization', 0):.2f}%"},
                                {"Metric": "LTV", "Value": f"{collateral_info.get('ltv', 0):.0f}%"},
                                {"Metric": "Liquidation CF", "Value": f"{collateral_info.get('liquidation_cf', 0):.0f}%"},
                            ]
                            df_coll = pd.DataFrame(coll_data)
                            st.dataframe(df_coll, use_container_width=True, hide_index=True)

                        st.divider()

                        # CLR Section
                        clr = market.get("clr") or {}
                        if clr and not clr.get("error"):
                            st.markdown("##### ⚠️ Cascade Liquidation Risk (CLR)")

                            col1, col2 = st.columns(2)

                            with col1:
                                # CLR Table
                                clr_data = [
                                    {"Metric": "CLR (by count)", "Value": f"{clr.get('clr_by_count', 0):.2f}%"},
                                    {"Metric": "CLR (by value)", "Value": f"{clr.get('clr_by_value', 0):.2f}%"},
                                    {"Metric": "Positions Analyzed", "Value": f"{clr.get('positions_analyzed', 0)}"},
                                    {"Metric": "Debt Analyzed", "Value": f"{clr.get('debt_analyzed', 0):,.2f} {base_asset}"},
                                    {"Metric": "Debt at Risk", "Value": f"{clr.get('debt_at_risk', 0):,.2f} {base_asset}"},
                                ]
                                df_clr = pd.DataFrame(clr_data)
                                st.dataframe(df_clr, use_container_width=True, hide_index=True)

                            with col2:
                                # Health Factor Distribution Bar Chart
                                risk_dist = clr.get("risk_distribution") or {}
                                if risk_dist:
                                    st.markdown("**Health Factor Distribution**")

                                    hf_categories = ["Critical\n(HF<1.0)", "High Risk\n(1.0-1.05)", "At Risk\n(1.05-1.1)", "Moderate\n(1.1-1.25)", "Safe\n(HF≥1.25)"]
                                    hf_values = [
                                        risk_dist.get("critical", 0),
                                        risk_dist.get("high_risk", 0),
                                        risk_dist.get("at_risk", 0),
                                        risk_dist.get("moderate", 0),
                                        risk_dist.get("safe", 0)
                                    ]
                                    hf_colors = ["#ef4444", "#f97316", "#eab308", "#84cc16", "#22c55e"]

                                    fig = go.Figure(data=[
                                        go.Bar(
                                            x=hf_categories,
                                            y=hf_values,
                                            marker_color=hf_colors,
                                            text=hf_values,
                                            textposition='auto'
                                        )
                                    ])
                                    fig.update_layout(
                                        title=f"Health Factor Distribution ({chain_name} - {market_name})",
                                        yaxis_title="Number of Positions",
                                        height=300,
                                        showlegend=False
                                    )
                                    st.plotly_chart(fig, use_container_width=True, key=f"chart_{id(fig)}")
                        else:
                            clr_error = clr.get("error", "No CLR data") if clr else "No CLR data"
                            st.info(f"CLR: {clr_error}")
    else:
        st.info("No Compound data available. Enable live data fetching to retrieve lending metrics.")


# =============================================================================
# TAB 6: DEX LIQUIDITY
# =============================================================================

def render_tab_dex():
    st.header("💱 DEX Liquidity")

    config = st.session_state.get("config")
    fetched = st.session_state.get("fetched_data") or {}

    if not config:
        st.info("Load a configuration first.")
        return

    dex_data = fetched.get("dex") or {}
    slippage_data = fetched.get("slippage") or {}
    pools = dex_data.get("pools", [])
    agg = dex_data.get("aggregated") or {}

    # =========================================================================
    # AGGREGATE METRICS
    # =========================================================================
    st.subheader("Aggregate Metrics")

    col1, col2, col3 = st.columns(3)
    with col1:
        if agg.get("tvl_usd"):
            st.metric("Total TVL", f"${agg['tvl_usd']:,.2f}")
        else:
            st.metric("Total TVL", "N/A")
    with col2:
        if agg.get("hhi"):
            st.metric("TVL-Weighted HHI", f"{agg['hhi']:,.0f}")
        else:
            st.metric("TVL-Weighted HHI", "N/A")
    with col3:
        if agg.get("hhi"):
            if agg["hhi"] < 1500:
                st.success("Highly Competitive")
            elif agg["hhi"] < 2500:
                st.warning("Moderately Concentrated")
            else:
                st.error("Highly Concentrated")
        else:
            st.info("No HHI data")

    st.divider()

    # =========================================================================
    # POOL DETAILS
    # =========================================================================
    st.subheader("Pool Details")

    if pools:
        for pool in pools:
            protocol = pool.get("protocol", "Unknown")
            pool_name = pool.get("pool_name") or pool.get("pair", "Unknown")
            chain = pool.get("chain", "unknown")
            status = pool.get("status", "error")

            with st.expander(f"📊 {protocol} - {pool_name} ({chain.title()})", expanded=True):
                if status == "error":
                    st.error(f"Error: {pool.get('error', 'Unknown error')}")
                    continue

                col1, col2 = st.columns(2)

                with col1:
                    # Pool Overview
                    st.markdown("##### Pool Overview")
                    overview_data = [
                        {"Metric": "Protocol", "Value": protocol},
                        {"Metric": "Chain", "Value": chain.title()},
                        {"Metric": "Pair", "Value": pool.get("pair", pool_name)},
                        {"Metric": "TVL (USD)", "Value": f"${pool.get('tvl_usd', 0):,.2f}"},
                    ]
                    if pool.get("fee_tier"):
                        overview_data.append({"Metric": "Fee Tier", "Value": f"{pool['fee_tier']}%"})

                    df_overview = pd.DataFrame(overview_data)
                    st.dataframe(df_overview, use_container_width=True, hide_index=True)

                    # Token Amounts
                    token_amounts = pool.get("token_amounts", [])
                    if token_amounts:
                        st.markdown("**Token Amounts**")
                        token_data = []
                        for token in token_amounts:
                            symbol = token.get("symbol", "?")
                            amount = token.get("amount") or token.get("balance", 0)
                            token_data.append({"Token": symbol, "Amount": f"{amount:,.4f}"})
                        df_tokens = pd.DataFrame(token_data)
                        st.dataframe(df_tokens, use_container_width=True, hide_index=True)

                with col2:
                    # Concentration Metrics
                    conc = pool.get("concentration_metrics") or {}
                    if conc:
                        st.markdown("##### LP Concentration")

                        conc_data = [
                            {"Metric": "Unique LPs", "Value": f"{conc.get('unique_holders', 0):,}"},
                            {"Metric": "HHI", "Value": f"{conc.get('hhi', 0):,.2f}"},
                            {"Metric": "HHI Category", "Value": conc.get("hhi_category", "N/A")},
                            {"Metric": "Top 1 LP", "Value": f"{conc.get('top_1_pct', 0):.2f}%"},
                            {"Metric": "Top 3 LPs", "Value": f"{conc.get('top_3_pct', 0):.2f}%"},
                            {"Metric": "Top 5 LPs", "Value": f"{conc.get('top_5_pct', 0):.2f}%"},
                            {"Metric": "Top 10 LPs", "Value": f"{conc.get('top_10_pct', 0):.2f}%"},
                        ]
                        df_conc = pd.DataFrame(conc_data)
                        st.dataframe(df_conc, use_container_width=True, hide_index=True)

                        # LP Concentration Bar Chart
                        lp_labels = ["Top 1", "Top 3", "Top 5", "Top 10"]
                        lp_values = [
                            conc.get("top_1_pct", 0),
                            conc.get("top_3_pct", 0),
                            conc.get("top_5_pct", 0),
                            conc.get("top_10_pct", 0)
                        ]

                        fig = go.Figure(data=[
                            go.Bar(
                                x=lp_labels,
                                y=lp_values,
                                marker_color=['#ef4444', '#f97316', '#eab308', '#22c55e'],
                                text=[f"{v:.1f}%" for v in lp_values],
                                textposition='auto'
                            )
                        ])
                        fig.update_layout(
                            title="LP Concentration",
                            yaxis_title="% of Liquidity",
                            height=250,
                            showlegend=False
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"chart_{id(fig)}")

                # Top LPs Table
                top_lps = pool.get("top_lps", [])
                if top_lps:
                    st.markdown("**Top Liquidity Providers**")
                    lp_data = []
                    for i, lp in enumerate(top_lps[:10], 1):
                        addr = lp.get("address", "")
                        lp_data.append({
                            "#": i,
                            "Address": f"{addr[:10]}...{addr[-8:]}" if len(addr) > 18 else addr,
                            "Share": f"{lp.get('share_pct', 0):.2f}%"
                        })
                    df_lps = pd.DataFrame(lp_data)
                    st.dataframe(df_lps, use_container_width=True, hide_index=True)
    else:
        st.info("No pool data available. Enable live data fetching to retrieve DEX metrics.")

    st.divider()

    # =========================================================================
    # SLIPPAGE ANALYSIS
    # =========================================================================
    st.subheader("Slippage Analysis")

    slippage_chains = slippage_data.get("chains", {})
    if slippage_chains:
        for chain_name, chain_data in slippage_chains.items():
            if chain_data.get("status") == "error":
                st.warning(f"**{chain_name.title()}**: {chain_data.get('error', 'Unknown error')}")
                continue

            with st.expander(f"📊 {chain_name.title()} - {chain_data.get('sell_token_symbol', '???')} → {chain_data.get('buy_token_symbol', '???')}", expanded=True):
                trade_sizes = chain_data.get("trade_sizes", [])

                if not trade_sizes:
                    st.info("No trade size data available")
                    continue

                for trade in trade_sizes:
                    size_usd = trade.get("size_usd", 0)
                    st.markdown(f"##### Trade Size: ${size_usd:,}")

                    if trade.get("error"):
                        st.error(trade["error"])
                        continue

                    col1, col2 = st.columns(2)

                    with col1:
                        # Summary metrics
                        median_slippage = trade.get("median_slippage")
                        best_agg = trade.get("best_aggregator", "N/A")
                        successful = trade.get("successful_quotes", 0)

                        summary_data = [
                            {"Metric": "Median Slippage", "Value": f"{median_slippage:.4f}%" if median_slippage else "N/A"},
                            {"Metric": "Best Aggregator", "Value": best_agg},
                            {"Metric": "Successful Quotes", "Value": f"{successful}/5"},
                        ]
                        df_summary = pd.DataFrame(summary_data)
                        st.dataframe(df_summary, use_container_width=True, hide_index=True)

                    with col2:
                        # Aggregator quotes
                        quotes = trade.get("aggregator_quotes", {})
                        if quotes:
                            quote_data = []
                            for agg_name in ["CowSwap", "1inch", "0x", "KyberSwap", "Odos"]:
                                agg_quote = quotes.get(agg_name, {})
                                if agg_quote.get("status") == "success":
                                    slippage = agg_quote.get("slippage_pct", 0)
                                    is_best = agg_quote.get("is_best", False)
                                    status = "⭐ BEST" if is_best else "OK"
                                    quote_data.append({
                                        "Aggregator": agg_name,
                                        "Slippage": f"{slippage:.4f}%",
                                        "Status": status
                                    })
                                else:
                                    quote_data.append({
                                        "Aggregator": agg_name,
                                        "Slippage": "N/A",
                                        "Status": "Failed"
                                    })

                            df_quotes = pd.DataFrame(quote_data)
                            st.dataframe(df_quotes, use_container_width=True, hide_index=True)
    else:
        st.info("Slippage data requires live data fetching. Enable 'Fetch live data' and run analysis.")
        st.markdown("""
        **Methodology:**
        - Query 5 aggregators: CowSwap, 1inch, 0x, KyberSwap, Odos
        - Trade sizes: $100K and $500K
        - Compare prices to identify best execution
        - Calculate median slippage across sources
        """)


# =============================================================================
# TAB 7: DATA ACCURACY
# =============================================================================

def render_tab_data_accuracy():
    st.header("🔬 Data Accuracy Verification")

    config = st.session_state.get("config")
    fetched = st.session_state.get("fetched_data") or {}

    if not config:
        st.info("Load a configuration first.")
        return

    data_accuracy = fetched.get("data_accuracy") or {}
    dex_accuracy = data_accuracy.get("dex_accuracy", [])

    st.markdown("""
    This tab verifies the accuracy of data fetched from external sources (subgraphs, APIs)
    by cross-referencing with on-chain data. A higher accuracy score indicates more reliable data.
    """)

    st.divider()

    # =========================================================================
    # DEX POOL DATA ACCURACY
    # =========================================================================
    st.subheader("DEX Pool Data Accuracy")

    if dex_accuracy:
        # Summary metrics
        successful = [d for d in dex_accuracy if d.get("status") == "success"]
        avg_accuracy = sum(d.get("accuracy_pct", 0) for d in successful) / len(successful) if successful else 0
        avg_deviation = sum(d.get("total_deviation_pct", 0) for d in successful) / len(successful) if successful else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pools Verified", f"{len(successful)}/{len(dex_accuracy)}")
        with col2:
            st.metric("Average Accuracy", f"{avg_accuracy:.1f}%")
        with col3:
            st.metric("Avg. Total Deviation", f"{avg_deviation:.4f}%")

        # Status indicator
        if avg_accuracy >= 90:
            st.success("Data sources are highly accurate")
        elif avg_accuracy >= 70:
            st.warning("Data sources have moderate accuracy - consider additional verification")
        else:
            st.error("Data sources have low accuracy - results may be unreliable")

        st.divider()

        # Detailed results per pool
        for pool in dex_accuracy:
            protocol = pool.get("protocol", "Unknown")
            pool_name = pool.get("pool_name", "Unknown")
            chain = pool.get("chain", "unknown")
            status = pool.get("status", "error")

            status_icon = "✅" if status == "success" else "❌"

            with st.expander(f"{status_icon} {protocol} - {pool_name} ({chain.title()})", expanded=True):
                if status == "error":
                    st.error(f"Error: {pool.get('error', 'Unknown error')}")
                    continue

                col1, col2 = st.columns(2)

                with col1:
                    # Accuracy metrics table
                    st.markdown("##### Verification Results")
                    accuracy_data = [
                        {"Metric": "Data Source", "Value": pool.get("data_source", "N/A")},
                        {"Metric": "Accuracy Score", "Value": f"{pool.get('accuracy_pct', 0):.1f}%"},
                        {"Metric": "Total Liquidity Deviation", "Value": f"{pool.get('total_deviation_pct', 0):.4f}%"},
                        {"Metric": "Positions Matched", "Value": f"{pool.get('positions_matched', 0)}/5"},
                    ]
                    df_accuracy = pd.DataFrame(accuracy_data)
                    st.dataframe(df_accuracy, use_container_width=True, hide_index=True)

                with col2:
                    # Visual indicator
                    accuracy_pct = pool.get("accuracy_pct", 0)

                    if accuracy_pct == 100:
                        status_text = "VERIFIED"
                        color = "#22c55e"
                    elif accuracy_pct >= 50:
                        status_text = "PARTIAL"
                        color = "#eab308"
                    else:
                        status_text = "FAILED"
                        color = "#ef4444"

                    st.markdown(f"""
                    <div style="text-align: center; padding: 20px; background-color: {color}; border-radius: 10px; color: white;">
                        <h2 style="margin: 0;">{status_text}</h2>
                        <h3 style="margin: 5px 0 0 0;">{accuracy_pct:.1f}%</h3>
                    </div>
                    """, unsafe_allow_html=True)

                    # Interpretation
                    st.markdown("**Interpretation:**")
                    if accuracy_pct == 100:
                        st.success("All sampled positions match on-chain data exactly.")
                    elif accuracy_pct >= 80:
                        st.info("Most positions match. Minor deviations may be due to indexing lag.")
                    elif accuracy_pct >= 50:
                        st.warning("Partial match. Data may have indexing delays or errors.")
                    else:
                        st.error("Low accuracy. Data source may be unreliable or outdated.")
    else:
        st.info("Data accuracy verification requires live data fetching. Enable 'Fetch live data' and run analysis.")

    st.divider()

    # =========================================================================
    # METHODOLOGY
    # =========================================================================
    st.subheader("Verification Methodology")

    st.markdown("""
    ### How We Verify Data Accuracy

    **For Uniswap V3 / PancakeSwap V3:**
    1. Fetch total pool liquidity from The Graph subgraph
    2. Compare against on-chain `liquidity()` call on the pool contract
    3. Fetch top N LP positions from subgraph
    4. Verify each position's liquidity and owner against NFT Position Manager contract
    5. Calculate accuracy as % of positions that match within 1% tolerance

    **For Curve Finance:**
    1. Fetch LP token total supply from Blockscout API
    2. Compare against on-chain `totalSupply()` call
    3. Fetch top N LP token holders from Blockscout
    4. Verify each holder's balance against on-chain `balanceOf()` call
    5. Calculate accuracy as % of balances that match within 1% tolerance

    **Accuracy Thresholds:**
    - **100%**: All sampled positions match on-chain data (VERIFIED)
    - **50-99%**: Partial match, likely due to indexing lag (PARTIAL)
    - **< 50%**: Significant discrepancies, data may be unreliable (FAILED)

    **Why This Matters:**
    - Subgraphs and APIs can have indexing delays
    - Stale data can lead to incorrect risk assessments
    - Cross-verification ensures data reliability for risk scoring
    """)


# =============================================================================
# TAB 8: RISK METRICS (index 8)
# =============================================================================

def render_tab_risk_metrics():
    st.header("📈 Risk Metrics")

    config = st.session_state.get("config")
    fetched = st.session_state.get("fetched_data") or {}

    if not config:
        st.info("Load a configuration first.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Proof of Reserves")
        por = fetched.get("proof_of_reserve") or {}

        reserve_ratio = por.get("reserve_ratio", 1.0)
        st.metric("Reserve Ratio", format_percentage(reserve_ratio * 100))

        if reserve_ratio >= 1.0:
            st.success("✅ Fully Backed")
        else:
            st.error("⚠️ Under-collateralized")

        if por.get("reserves"):
            st.metric("Reserves", format_number(por["reserves"], 4))
        if por.get("total_supply"):
            st.metric("Total Supply", format_number(por["total_supply"], 4))

    with col2:
        st.subheader("Price Risk")
        price = fetched.get("price_risk") or {}

        if price.get("volatility"):
            st.metric("Annualized Volatility", format_percentage(price["volatility"]))

        if price.get("var_95"):
            st.markdown("**Value at Risk**")
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("VaR 95%", format_percentage(price.get("var_95", 0)))
                st.metric("CVaR 95%", format_percentage(price.get("cvar_95", 0)))
            with col_b:
                st.metric("VaR 99%", format_percentage(price.get("var_99", 0)))
                st.metric("CVaR 99%", format_percentage(price.get("cvar_99", 0)))

    st.divider()

    # Counterparty Risk
    st.subheader("Counterparty Risk")

    risk_score = st.session_state.get("risk_score") or {}
    if risk_score:
        categories = risk_score.get("categories") or {}
        counterparty = categories.get("counterparty") or {}
        if counterparty:
            grade = counterparty.get("grade", "?")
            score = counterparty.get("score", 0)
            color = get_grade_color(grade)

            st.markdown(f"""
            <span style="background-color: {color}; color: white; padding: 5px 10px; border-radius: 5px;">
                {grade} ({score:.1f})
            </span>
            """, unsafe_allow_html=True)

            breakdown = counterparty.get("breakdown") or {}
            cols = st.columns(4)
            metrics = ["admin_key_control", "custody", "timelock", "blacklist"]
            for i, m in enumerate(metrics):
                if m in breakdown:
                    with cols[i]:
                        st.metric(m.replace("_", " ").title(), f"{breakdown[m].get('score', 0):.0f}")

    st.divider()

    # =========================================================================
    # ORACLE METRICS
    # =========================================================================
    st.subheader("🔮 Oracle Metrics")

    oracle_data = fetched.get("oracle") or {}
    freshness_data = oracle_data.get("freshness", [])
    lag_data = oracle_data.get("lag")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### Oracle Freshness")
        st.caption("Time since last oracle update")

        if freshness_data:
            freshness_table = []
            for feed in freshness_data:
                if feed.get("status") == "success":
                    minutes = feed.get("minutes_since_update", 0)
                    hours = feed.get("hours_since_update", 0)

                    # Determine status
                    if minutes < 60:
                        status = "🟢 Fresh"
                    elif minutes < 180:
                        status = "🟡 Acceptable"
                    else:
                        status = "🔴 Stale"

                    freshness_table.append({
                        "Feed": feed.get("name", "Unknown"),
                        "Chain": feed.get("chain", "").title(),
                        "Price": f"${feed.get('price', 0):,.2f}" if feed.get("price") else "N/A",
                        "Age (min)": f"{minutes:.1f}",
                        "Status": status
                    })
                else:
                    freshness_table.append({
                        "Feed": feed.get("name", "Unknown"),
                        "Chain": feed.get("chain", "").title(),
                        "Price": "N/A",
                        "Age (min)": "N/A",
                        "Status": f"❌ Error: {feed.get('error', 'Unknown')[:20]}..."
                    })

            if freshness_table:
                df_freshness = pd.DataFrame(freshness_table)
                st.dataframe(df_freshness, use_container_width=True, hide_index=True)

                # Summary metrics
                successful = [f for f in freshness_data if f.get("status") == "success"]
                if successful:
                    avg_freshness = sum(f.get("minutes_since_update", 0) for f in successful) / len(successful)
                    max_freshness = max(f.get("minutes_since_update", 0) for f in successful)

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Avg. Freshness", f"{avg_freshness:.1f} min")
                    with col_b:
                        st.metric("Max. Age", f"{max_freshness:.1f} min")

                    if max_freshness < 60:
                        st.success("All oracles are fresh (< 1 hour)")
                    elif max_freshness < 180:
                        st.warning("Some oracles are aging (1-3 hours)")
                    else:
                        st.error("Stale oracle data detected (> 3 hours)")
        else:
            st.info("Oracle freshness data requires live data fetching. Enable 'Fetch live data' and run analysis.")

    with col2:
        st.markdown("##### Cross-Chain Oracle Lag")
        st.caption("Time difference between oracle updates on different chains")

        if lag_data and lag_data.get("status") == "success":
            lag_seconds = lag_data.get("lag_seconds", 0)
            lag_minutes = lag_data.get("lag_minutes", 0)
            ahead_chain = lag_data.get("ahead_chain", "Unknown")
            chain1 = lag_data.get("chain1", "Chain 1")
            chain2 = lag_data.get("chain2", "Chain 2")

            # Lag metrics table
            lag_table = [
                {"Metric": "Chain 1", "Value": chain1},
                {"Metric": "Chain 2", "Value": chain2},
                {"Metric": "Lag", "Value": f"{lag_seconds} seconds ({lag_minutes:.2f} min)"},
                {"Metric": "Ahead Chain", "Value": ahead_chain if ahead_chain != "synchronized" else "Synchronized"},
            ]

            # Add chain-specific data
            chain1_data = lag_data.get("chain1_data") or {}
            chain2_data = lag_data.get("chain2_data") or {}

            if chain1_data.get("price"):
                lag_table.append({"Metric": f"{chain1} Price", "Value": f"${chain1_data['price']:.8f}"})
            if chain2_data.get("price"):
                lag_table.append({"Metric": f"{chain2} Price", "Value": f"${chain2_data['price']:.8f}"})

            df_lag = pd.DataFrame(lag_table)
            st.dataframe(df_lag, use_container_width=True, hide_index=True)

            # Visual indicator
            if lag_minutes < 5:
                st.success(f"Low lag: {lag_minutes:.2f} minutes")
            elif lag_minutes < 30:
                st.warning(f"Moderate lag: {lag_minutes:.2f} minutes")
            else:
                st.error(f"High lag: {lag_minutes:.2f} minutes")

            # Interpretation
            st.markdown("**Interpretation:**")
            if ahead_chain == "synchronized":
                st.info("Both oracles are synchronized - no cross-chain lag detected.")
            else:
                st.info(f"The {ahead_chain} oracle is {lag_minutes:.1f} minutes ahead. "
                       "This lag represents the time difference between oracle updates on different chains.")

        elif lag_data and lag_data.get("status") == "error":
            st.error(f"Error fetching lag data: {lag_data.get('error', 'Unknown error')}")
        else:
            st.info("Cross-chain oracle lag data requires live data fetching and oracle_lag configuration.")


# =============================================================================
# TAB 9: METHODOLOGY (GENERAL) (index 9)
# =============================================================================

def render_tab_methodology_general():
    st.header("📚 Methodology (General)")

    st.markdown("""
    ## Data Sources & Calculation Methods

    ### 1. Supply & Distribution

    **Gini Coefficient:**
    ```
    G = 1 - (2 / n) * Σ(n + 1 - i) * (x_i / Σx)
    ```
    Where x_i is the balance of holder i, sorted ascending.

    **Whale Concentration:**
    ```
    Top N % = Σ(top N balances) / Total Supply * 100
    ```

    ### 2. Lending Metrics

    **RLR (Recursive Lending Ratio):**
    ```
    RLR_supply = Looped Borrow / Total Supply * 100
    RLR_borrow = Looped Borrow / Total Borrow * 100
    ```

    **Per-User Leverage:**
    ```
    Leverage = User Supply / (User Supply - User Borrow)
    ```

    **CLR (Cascade Liquidation Risk):**
    ```
    CLR_count = Positions with HF < 1.1 / Total Positions * 100
    CLR_value = Debt at Risk / Total Debt * 100
    ```

    ### 3. DEX Liquidity

    **HHI (Herfindahl-Hirschman Index):**
    ```
    HHI = Σ(market_share_i)² * 10000
    ```
    - < 1,500: Unconcentrated
    - 1,500 - 2,500: Moderate concentration
    - > 2,500: High concentration

    ### 4. Market Risk

    **Annualized Volatility:**
    ```
    σ_annual = σ_daily * √365
    ```

    **VaR (Value at Risk):**
    ```
    VaR_95 = Percentile(returns, 5)
    VaR_99 = Percentile(returns, 1)
    ```

    ### 5. Data Sources

    | Metric | Source | Method |
    |--------|--------|--------|
    | Token Supply | RPC | totalSupply() call |
    | Holder Distribution | Blockscout API | Token holders endpoint |
    | LP Concentration | The Graph | Position queries |
    | Slippage | DEX Aggregators | Quote comparison |
    | Price Data | CoinGecko | Historical API |
    | Proof of Reserves | Chainlink PoR | latestRoundData() |
    | Lending Data | The Graph + RPC | Hybrid queries |
    """)


# =============================================================================
# MAIN APP
# =============================================================================

def main():
    init_session_state()

    # Sidebar
    with st.sidebar:
        st.title("🛡️ Token Risk Dashboard")

        if not IMPORTS_OK:
            st.error(f"Import Error: {IMPORT_ERROR}")

        if st.session_state.get("config"):
            config = st.session_state.config
            st.markdown(f"**Asset:** {config.get('asset_name', 'N/A')}")

            if st.session_state.get("risk_score"):
                overall = st.session_state.risk_score.get("overall", {})
                if overall:
                    grade = overall.get("grade", "?")
                    score = overall.get("score", 0)
                    color = get_grade_color(grade)
                    st.markdown(f"**Score:** <span style='color:{color}'>{grade} ({score:.1f})</span>", unsafe_allow_html=True)

        st.divider()
        st.caption("v1.0.0")

    # Tabs
    tabs = st.tabs([
        "⚙️ Configuration",
        "📊 Risk Score",
        "📖 Scoring Methodology",
        "🏛️ Protocol Info",
        "💰 Supply & Distribution",
        "🏦 Lending",
        "💱 DEX Liquidity",
        "🔬 Data Accuracy",
        "📈 Risk Metrics",
        "📚 Methodology",
    ])

    with tabs[0]:
        render_tab_configuration()
    with tabs[1]:
        render_tab_risk_score()
    with tabs[2]:
        render_tab_methodology_scoring()
    with tabs[3]:
        render_tab_protocol_info()
    with tabs[4]:
        render_tab_supply()
    with tabs[5]:
        render_tab_lending()
    with tabs[6]:
        render_tab_dex()
    with tabs[7]:
        render_tab_data_accuracy()
    with tabs[8]:
        render_tab_risk_metrics()
    with tabs[9]:
        render_tab_methodology_general()


if __name__ == "__main__":
    main()
