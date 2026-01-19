"""
Data Adapter Layer for Risk Framework.

This module provides the bridge between:
1. JSON Configuration → Script function calls (input mapping)
2. Script outputs → Scoring metrics (output mapping)

Single entry point for the Streamlit app to fetch all required data
and transform it into the format expected by the scoring module.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import traceback

# Import configuration schema
try:
    from .config_schema import (
        AssetRiskConfig,
        validate_config,
        SUPPORTED_CHAINS,
    )
    from .aave_data import analyze_aave_market, CHAINS as AAVE_CHAINS
    from .compound import analyze_compound_market, MARKETS as COMPOUND_MARKETS
    from .uniswap import UniswapV3Analyzer
    from .curve import CurveFinanceAnalyzer
    from .proof_of_reserve import analyze_proof_of_reserve
    from .price_risk import get_coingecko_data, calculate_peg_deviation, calculate_metrics
    from .oracle_lag import (
        analyze_oracle_lag,
        get_oracle_freshness,
        get_cross_chain_oracle_freshness,
    )
except ImportError:
    from config_schema import (
        AssetRiskConfig,
        validate_config,
        SUPPORTED_CHAINS,
    )
    from aave_data import analyze_aave_market, CHAINS as AAVE_CHAINS
    from compound import analyze_compound_market, MARKETS as COMPOUND_MARKETS
    from uniswap import UniswapV3Analyzer
    from curve import CurveFinanceAnalyzer
    from proof_of_reserve import analyze_proof_of_reserve
    from price_risk import get_coingecko_data, calculate_peg_deviation, calculate_metrics
    from oracle_lag import (
        analyze_oracle_lag,
        get_oracle_freshness,
        get_cross_chain_oracle_freshness,
    )


# =============================================================================
# CONSTANTS
# =============================================================================

# The Graph API key (should be moved to env variable in production)
GRAPH_API_KEY = "db5921ae7c7116289958d028661c86b3"


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def fetch_lending_data(config: AssetRiskConfig) -> Dict[str, Any]:
    """
    Fetch lending market data (AAVE + Compound) based on configuration.

    Returns aggregated RLR, CLR, and utilization metrics across all configured markets.
    """
    results = {
        "aave_markets": [],
        "compound_markets": [],
        "aggregated": {
            "rlr_pct": None,
            "clr_pct": None,
            "utilization_pct": None,
        },
        "errors": [],
    }

    all_rlr = []
    all_clr = []
    all_utilization = []

    for lending_cfg in config.lending_configs:
        try:
            if lending_cfg.protocol == "aave":
                # Get chain config
                chain_name = lending_cfg.chain.capitalize()
                if chain_name == "Ethereum":
                    chain_name = "Ethereum"
                elif chain_name == "Base":
                    chain_name = "Base"
                elif chain_name == "Arbitrum":
                    chain_name = "Arbitrum"

                if chain_name not in AAVE_CHAINS:
                    results["errors"].append(f"AAVE: Chain {chain_name} not supported")
                    continue

                chain_config = AAVE_CHAINS[chain_name]
                market_result = analyze_aave_market(
                    lending_cfg.token_address,
                    chain_name,
                    chain_config
                )

                results["aave_markets"].append(market_result)

                # Extract metrics if successful
                if market_result.get("status") == "success":
                    rlr = market_result.get("rlr", {})
                    if rlr and "rlr_supply_based" in rlr:
                        all_rlr.append(rlr["rlr_supply_based"])

                    clr = market_result.get("clr", {})
                    if clr and "clr_by_value" in clr:
                        all_clr.append(clr["clr_by_value"])

                    market_overview = market_result.get("market_overview", {})
                    if market_overview and "utilization_rate" in market_overview:
                        all_utilization.append(market_overview["utilization_rate"])

            elif lending_cfg.protocol == "compound":
                chain_name = lending_cfg.chain.capitalize()
                if chain_name not in COMPOUND_MARKETS:
                    results["errors"].append(f"Compound: Chain {chain_name} not supported")
                    continue

                chain_config = COMPOUND_MARKETS[chain_name]
                market_result = analyze_compound_market(
                    lending_cfg.token_address,
                    chain_name,
                    chain_config
                )

                results["compound_markets"].append(market_result)

                # Extract metrics from each supported market
                if market_result.get("status") == "success":
                    for market in market_result.get("markets", []):
                        if market.get("supported"):
                            clr = market.get("clr", {})
                            if clr and "clr_by_value" in clr:
                                all_clr.append(clr["clr_by_value"])

                            market_overview = market.get("market_overview", {})
                            if market_overview and "utilization" in market_overview:
                                all_utilization.append(market_overview["utilization"])

        except Exception as e:
            results["errors"].append(f"Error fetching {lending_cfg.protocol} on {lending_cfg.chain}: {str(e)}")
            traceback.print_exc()

    # Aggregate metrics (use worst case / average as appropriate)
    if all_rlr:
        results["aggregated"]["rlr_pct"] = max(all_rlr)  # Worst case
    if all_clr:
        results["aggregated"]["clr_pct"] = max(all_clr)  # Worst case
    if all_utilization:
        results["aggregated"]["utilization_pct"] = sum(all_utilization) / len(all_utilization)  # Average

    return results


def fetch_dex_data(config: AssetRiskConfig) -> Dict[str, Any]:
    """
    Fetch DEX pool data (Uniswap, Curve) based on configuration.

    Returns aggregated HHI and concentration metrics.
    """
    results = {
        "uniswap_pools": [],
        "curve_pools": [],
        "aggregated": {
            "hhi": None,
            "tvl_usd": 0,
        },
        "errors": [],
    }

    all_hhi = []
    total_tvl = 0

    for pool_cfg in config.dex_pools:
        try:
            if pool_cfg.protocol == "uniswap":
                analyzer = UniswapV3Analyzer(pool_cfg.chain, GRAPH_API_KEY)
                pool_result = analyzer.analyze_pool(pool_cfg.pool_address)

                results["uniswap_pools"].append(pool_result)

                if pool_result.get("status") == "success":
                    concentration = pool_result.get("concentration_metrics", {})
                    if concentration and "hhi" in concentration:
                        hhi = concentration["hhi"]
                        tvl = pool_result.get("tvl_usd", 0)
                        all_hhi.append((hhi, tvl))
                        total_tvl += tvl

            elif pool_cfg.protocol == "curve":
                analyzer = CurveFinanceAnalyzer(pool_cfg.chain)
                pool_result = analyzer.analyze_pool(pool_cfg.pool_address)

                results["curve_pools"].append(pool_result)

                if pool_result.get("status") == "success":
                    concentration = pool_result.get("concentration_metrics", {})
                    if concentration and "hhi" in concentration:
                        hhi = concentration["hhi"]
                        tvl = pool_result.get("tvl_usd", 0)
                        all_hhi.append((hhi, tvl))
                        total_tvl += tvl

        except Exception as e:
            results["errors"].append(f"Error fetching {pool_cfg.protocol} pool on {pool_cfg.chain}: {str(e)}")
            traceback.print_exc()

    # Aggregate HHI (weighted by TVL)
    if all_hhi and total_tvl > 0:
        weighted_hhi = sum(hhi * tvl for hhi, tvl in all_hhi) / total_tvl
        results["aggregated"]["hhi"] = weighted_hhi
        results["aggregated"]["tvl_usd"] = total_tvl

    return results


def fetch_proof_of_reserve_data(config: AssetRiskConfig) -> Dict[str, Any]:
    """
    Fetch Proof of Reserve data based on configuration.

    Returns reserve ratio and backing status.
    """
    results = {
        "data": None,
        "reserve_ratio": None,
        "is_fully_backed": None,
        "errors": [],
    }

    if not config.proof_of_reserve:
        results["errors"].append("No proof_of_reserve configuration provided")
        return results

    try:
        por_result = analyze_proof_of_reserve(
            evm_chains=config.proof_of_reserve.evm_chains,
            solana_token=config.proof_of_reserve.solana_token
        )

        results["data"] = por_result

        if por_result.get("status") == "success":
            metrics = por_result.get("metrics", {})
            results["reserve_ratio"] = metrics.get("reserve_ratio", 1.0)
            results["is_fully_backed"] = metrics.get("is_fully_backed", True)

    except Exception as e:
        results["errors"].append(f"Error fetching Proof of Reserve: {str(e)}")
        traceback.print_exc()

    return results


def fetch_price_risk_data(config: AssetRiskConfig) -> Dict[str, Any]:
    """
    Fetch price risk data from CoinGecko based on configuration.

    Returns peg deviation, volatility, and VaR metrics.
    """
    results = {
        "peg_metrics": None,
        "risk_metrics": None,
        "aggregated": {
            "peg_deviation_pct": None,
            "volatility_annualized_pct": None,
            "var_95_pct": None,
        },
        "errors": [],
    }

    if not config.price_risk:
        results["errors"].append("No price_risk configuration provided")
        return results

    try:
        # Fetch price data
        print(f"Fetching price data for {config.price_risk.token_coingecko_id}...")
        token_timestamps, token_prices = get_coingecko_data(config.price_risk.token_coingecko_id)

        print(f"Fetching price data for {config.price_risk.underlying_coingecko_id}...")
        underlying_timestamps, underlying_prices = get_coingecko_data(config.price_risk.underlying_coingecko_id)

        # Ensure same length
        min_len = min(len(token_prices), len(underlying_prices))
        token_prices = token_prices[:min_len]
        underlying_prices = underlying_prices[:min_len]

        # Calculate peg deviation
        peg_metrics = calculate_peg_deviation(token_prices, underlying_prices)
        results["peg_metrics"] = peg_metrics

        # Calculate risk metrics (volatility, VaR)
        risk_metrics = calculate_metrics(token_prices)
        results["risk_metrics"] = risk_metrics

        # Parse metrics for scoring
        # Peg deviation - extract numeric value
        current_dev = peg_metrics.get("Current Deviation", "0%")
        results["aggregated"]["peg_deviation_pct"] = float(current_dev.replace("%", ""))

        # Volatility - extract numeric value
        vol = risk_metrics.get("Annualized Volatility", "0%")
        results["aggregated"]["volatility_annualized_pct"] = float(vol.replace("%", "")) * 100

        # VaR 95% - extract numeric value (negative, convert to positive)
        var = risk_metrics.get("VaR 95%", "0%")
        results["aggregated"]["var_95_pct"] = abs(float(var.replace("%", ""))) * 100

    except Exception as e:
        results["errors"].append(f"Error fetching price risk data: {str(e)}")
        traceback.print_exc()

    return results


def fetch_oracle_data(config: AssetRiskConfig) -> Dict[str, Any]:
    """
    Fetch oracle lag and freshness data based on configuration.

    Returns oracle freshness and cross-chain lag metrics.
    """
    results = {
        "lag_data": None,
        "freshness_data": None,
        "aggregated": {
            "oracle_freshness_minutes": None,
            "cross_chain_lag_minutes": None,
        },
        "errors": [],
    }

    # Fetch oracle lag (PoR feeds)
    if config.oracle_lag:
        try:
            lag_result = analyze_oracle_lag(
                chain1_name=config.oracle_lag.por_feed_1.chain,
                oracle1_address=config.oracle_lag.por_feed_1.address,
                chain2_name=config.oracle_lag.por_feed_2.chain,
                oracle2_address=config.oracle_lag.por_feed_2.address,
            )

            results["lag_data"] = lag_result

            if lag_result.get("status") == "success":
                results["aggregated"]["cross_chain_lag_minutes"] = lag_result.get("lag_minutes", 0)

        except Exception as e:
            results["errors"].append(f"Error fetching oracle lag: {str(e)}")
            traceback.print_exc()

    # Fetch oracle freshness (Price feeds)
    if config.oracle_freshness and config.oracle_freshness.price_feeds:
        try:
            # Build chain_oracles list for cross-chain freshness
            chain_oracles = [
                {
                    "chain": pf.chain,
                    "oracle_address": pf.address
                }
                for pf in config.oracle_freshness.price_feeds
            ]

            freshness_result = get_cross_chain_oracle_freshness(chain_oracles)
            results["freshness_data"] = freshness_result

            if freshness_result.get("status") == "success":
                # Get average freshness across all price feeds
                chains = freshness_result.get("chains", [])
                freshness_values = [
                    c.get("minutes_since_update", 0)
                    for c in chains
                    if "minutes_since_update" in c
                ]
                if freshness_values:
                    results["aggregated"]["oracle_freshness_minutes"] = max(freshness_values)  # Worst case

        except Exception as e:
            results["errors"].append(f"Error fetching oracle freshness: {str(e)}")
            traceback.print_exc()

    return results


def calculate_chain_distribution(config: AssetRiskConfig, lending_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate supply distribution across chains.

    Returns dict of chain -> percentage of total supply.
    """
    chain_supply = {}
    total_supply = 0

    # Extract supply from AAVE markets
    for market in lending_data.get("aave_markets", []):
        if market.get("status") == "success":
            chain = market.get("chain", "unknown")
            market_overview = market.get("market_overview", {})
            supply = market_overview.get("total_supply", 0)
            chain_supply[chain] = chain_supply.get(chain, 0) + supply
            total_supply += supply

    # Calculate percentages
    if total_supply > 0:
        return {chain: (supply / total_supply) * 100 for chain, supply in chain_supply.items()}

    return {}


# =============================================================================
# MAIN ADAPTER FUNCTION
# =============================================================================

def fetch_all_data(config: AssetRiskConfig, skip_sections: List[str] = None) -> Dict[str, Any]:
    """
    Fetch all quantitative data based on configuration.

    Args:
        config: AssetRiskConfig with all required parameters
        skip_sections: Optional list of sections to skip (e.g., ["lending", "dex"])

    Returns:
        Dict with all fetched data organized by category
    """
    skip_sections = skip_sections or []
    results = {
        "config_validation": None,
        "lending": None,
        "dex": None,
        "proof_of_reserve": None,
        "price_risk": None,
        "oracle": None,
        "chain_distribution": None,
        "errors": [],
    }

    # Validate configuration
    results["config_validation"] = validate_config(config)
    if not results["config_validation"]["is_valid"]:
        results["errors"].extend(results["config_validation"]["errors"])
        return results

    # Fetch data from each source
    if "lending" not in skip_sections:
        print("\n" + "=" * 70)
        print("FETCHING LENDING DATA")
        print("=" * 70)
        results["lending"] = fetch_lending_data(config)

    if "dex" not in skip_sections:
        print("\n" + "=" * 70)
        print("FETCHING DEX DATA")
        print("=" * 70)
        results["dex"] = fetch_dex_data(config)

    if "proof_of_reserve" not in skip_sections:
        print("\n" + "=" * 70)
        print("FETCHING PROOF OF RESERVE DATA")
        print("=" * 70)
        results["proof_of_reserve"] = fetch_proof_of_reserve_data(config)

    if "price_risk" not in skip_sections:
        print("\n" + "=" * 70)
        print("FETCHING PRICE RISK DATA")
        print("=" * 70)
        results["price_risk"] = fetch_price_risk_data(config)

    if "oracle" not in skip_sections:
        print("\n" + "=" * 70)
        print("FETCHING ORACLE DATA")
        print("=" * 70)
        results["oracle"] = fetch_oracle_data(config)

    # Calculate chain distribution
    if results["lending"]:
        results["chain_distribution"] = calculate_chain_distribution(config, results["lending"])

    # Collect all errors
    for key, data in results.items():
        if isinstance(data, dict) and "errors" in data:
            results["errors"].extend(data["errors"])

    return results


def build_scoring_metrics(config: AssetRiskConfig, fetched_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform fetched data and configuration into scoring metrics.

    This is the output mapping: script outputs → scoring inputs.

    Args:
        config: Original configuration
        fetched_data: Output from fetch_all_data()

    Returns:
        Dict in the format expected by calculate_asset_risk_score()
    """
    metrics = {}

    # ==========================================================================
    # Asset Metadata
    # ==========================================================================
    metrics["asset_name"] = config.asset_name
    metrics["asset_symbol"] = config.asset_symbol
    metrics["asset_type"] = config.asset_type
    metrics["underlying"] = config.underlying

    # ==========================================================================
    # Smart Contract Risk (from config - qualitative)
    # ==========================================================================
    if config.audit_data:
        metrics["audit_data"] = {
            "auditor": config.audit_data.auditor,
            "date": config.audit_data.date,
            "issues": config.audit_data.issues,
        }
    else:
        metrics["audit_data"] = None

    if config.deployment_date:
        metrics["deployment_date"] = datetime.fromisoformat(config.deployment_date).replace(tzinfo=timezone.utc)
    else:
        metrics["deployment_date"] = None

    metrics["incidents"] = [
        {
            "description": inc.description,
            "days_ago": inc.days_ago,
            "funds_lost": inc.funds_lost,
            "funds_lost_pct": inc.funds_lost_pct,
        }
        for inc in config.incidents
    ]

    # ==========================================================================
    # Counterparty Risk (from config - qualitative)
    # ==========================================================================
    metrics["multisig_configs"] = {
        cfg.role_name: {
            "is_multisig": cfg.is_multisig,
            "is_eoa": cfg.is_eoa,
            "threshold": cfg.threshold,
            "owners_count": cfg.owners_count,
        }
        for cfg in config.multisig_configs
    }

    metrics["has_timelock"] = config.has_timelock
    metrics["timelock_hours"] = config.timelock_hours
    metrics["custody_model"] = config.custody_model
    metrics["has_blacklist"] = config.has_blacklist
    metrics["blacklist_control"] = config.blacklist_control
    metrics["critical_roles"] = config.critical_roles
    metrics["role_weights"] = config.role_weights if config.role_weights else None

    # ==========================================================================
    # Market Risk (from price_risk data)
    # ==========================================================================
    price_risk = fetched_data.get("price_risk", {}) or {}
    aggregated_price = price_risk.get("aggregated", {}) or {}

    metrics["peg_deviation_pct"] = aggregated_price.get("peg_deviation_pct", 0)
    metrics["volatility_annualized_pct"] = aggregated_price.get("volatility_annualized_pct", 50)
    metrics["var_95_pct"] = aggregated_price.get("var_95_pct", 5)

    # ==========================================================================
    # Liquidity Risk (from DEX data)
    # ==========================================================================
    dex_data = fetched_data.get("dex", {}) or {}
    aggregated_dex = dex_data.get("aggregated", {}) or {}

    metrics["hhi"] = aggregated_dex.get("hhi", 2000)

    # Slippage - would need additional DEX simulation
    # For now, use default values (can be enhanced with CowSwap API, etc.)
    metrics["slippage_100k_pct"] = 0.5  # Default
    metrics["slippage_500k_pct"] = 1.0  # Default

    # Chain distribution
    metrics["chain_distribution"] = fetched_data.get("chain_distribution", {})

    # ==========================================================================
    # Collateral Risk (from lending data)
    # ==========================================================================
    lending_data = fetched_data.get("lending", {}) or {}
    aggregated_lending = lending_data.get("aggregated", {}) or {}

    metrics["clr_pct"] = aggregated_lending.get("clr_pct", 5)
    metrics["rlr_pct"] = aggregated_lending.get("rlr_pct", 10)
    metrics["utilization_pct"] = aggregated_lending.get("utilization_pct", 50)

    # ==========================================================================
    # Reserve & Oracle Risk (from PoR and oracle data)
    # ==========================================================================
    por_data = fetched_data.get("proof_of_reserve", {}) or {}
    metrics["reserve_ratio"] = por_data.get("reserve_ratio", 1.0)

    oracle_data = fetched_data.get("oracle", {}) or {}
    aggregated_oracle = oracle_data.get("aggregated", {}) or {}

    metrics["oracle_freshness_minutes"] = aggregated_oracle.get("oracle_freshness_minutes", 30)
    metrics["cross_chain_lag_minutes"] = aggregated_oracle.get("cross_chain_lag_minutes", 15)

    return metrics


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def run_complete_analysis(
    config: AssetRiskConfig,
    skip_sections: List[str] = None
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Run complete risk analysis pipeline.

    Args:
        config: AssetRiskConfig with all parameters
        skip_sections: Optional list of sections to skip

    Returns:
        Tuple of (fetched_data, scoring_metrics, risk_score)
    """
    try:
        from .asset_score import calculate_asset_risk_score
    except ImportError:
        from asset_score import calculate_asset_risk_score

    # Step 1: Fetch all data
    fetched_data = fetch_all_data(config, skip_sections)

    # Step 2: Build scoring metrics
    scoring_metrics = build_scoring_metrics(config, fetched_data)

    # Step 3: Calculate risk score
    risk_score = calculate_asset_risk_score(scoring_metrics)

    return fetched_data, scoring_metrics, risk_score


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    import json
    from .config_schema import get_example_config

    # Get example configuration
    config = get_example_config()

    print("=" * 70)
    print("RUNNING COMPLETE ANALYSIS")
    print("=" * 70)
    print(f"Asset: {config.asset_name} ({config.asset_symbol})")
    print("=" * 70)

    # Run analysis (skip some sections for demo speed)
    fetched_data, scoring_metrics, risk_score = run_complete_analysis(
        config,
        skip_sections=["lending", "dex", "proof_of_reserve"]  # Skip slow fetches for demo
    )

    print("\n" + "=" * 70)
    print("SCORING METRICS")
    print("=" * 70)
    print(json.dumps(scoring_metrics, indent=2, default=str))

    print("\n" + "=" * 70)
    print("RISK SCORE RESULT")
    print("=" * 70)
    print(json.dumps(risk_score, indent=2, default=str))
