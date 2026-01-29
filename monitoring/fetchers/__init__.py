"""
Metric fetchers - wrappers around existing scripts.

Each fetcher module provides:
- fetch_X_metrics(asset_config) - Fetch metrics without storing
- fetch_and_store_X_metrics(asset_config) - Fetch and store to database

Available fetchers:
- oracle: Oracle freshness and cross-chain lag
- liquidity: DEX slippage and pool TVL
- lending: AAVE/Compound CLR, RLR, utilization
- reserve: Proof of Reserve / backing ratio
- distribution: HHI, Gini, supply concentration
- market: Volatility, VaR, peg deviation
"""

from .oracle import (
    fetch_oracle_freshness,
    fetch_cross_chain_oracle_lag,
    fetch_and_store_oracle_metrics
)

from .liquidity import (
    fetch_slippage_metrics,
    fetch_pool_tvl,
    fetch_and_store_liquidity_metrics
)

from .lending import (
    fetch_aave_metrics,
    fetch_compound_metrics,
    fetch_all_lending_metrics,
    fetch_and_store_lending_metrics
)

from .reserve import (
    fetch_por_metrics,
    fetch_and_store_reserve_metrics
)

from .distribution import (
    fetch_distribution_metrics,
    fetch_single_chain_distribution,
    fetch_and_store_distribution_metrics,
    calculate_hhi
)

from .market import (
    fetch_price_risk_metrics,
    fetch_peg_deviation,
    fetch_all_market_metrics,
    fetch_and_store_market_metrics
)

__all__ = [
    # Oracle
    "fetch_oracle_freshness",
    "fetch_cross_chain_oracle_lag",
    "fetch_and_store_oracle_metrics",
    # Liquidity
    "fetch_slippage_metrics",
    "fetch_pool_tvl",
    "fetch_and_store_liquidity_metrics",
    # Lending
    "fetch_aave_metrics",
    "fetch_compound_metrics",
    "fetch_all_lending_metrics",
    "fetch_and_store_lending_metrics",
    # Reserve
    "fetch_por_metrics",
    "fetch_and_store_reserve_metrics",
    # Distribution
    "fetch_distribution_metrics",
    "fetch_single_chain_distribution",
    "fetch_and_store_distribution_metrics",
    "calculate_hhi",
    # Market
    "fetch_price_risk_metrics",
    "fetch_peg_deviation",
    "fetch_all_market_metrics",
    "fetch_and_store_market_metrics",
]
