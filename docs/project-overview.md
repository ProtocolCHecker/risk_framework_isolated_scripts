# Project Overview

> DeFi Risk Assessment Framework

## What is this project?

A **quantitative risk scoring system** for DeFi assets that analyzes wrapped tokens, liquid staking derivatives (LSDs), and other crypto assets across multiple risk dimensions to produce letter grades (A-F).

## Key Features

- **Two-stage scoring:** Primary checks (pass/fail) + weighted category scoring
- **Multi-chain support:** Ethereum, Base, Arbitrum, Optimism, Polygon
- **Live data fetching:** On-chain RPC, The Graph, CoinGecko, Chainlink
- **Interactive dashboard:** 10-tab Streamlit UI for exploration
- **Configurable assets:** JSON-based asset definitions

## Quick Start

```bash
# Activate environment
source venv/bin/activate

# Run dashboard
streamlit run streamlit_app.py
```

Then upload a config JSON (e.g., `example_wsteth_config.json`) to analyze an asset.

## Risk Categories (Weighted)

| Category | Weight | What it measures |
|----------|--------|------------------|
| Smart Contract | 10% | Audit status, code maturity, incidents |
| Counterparty | 25% | Admin keys, custody model, timelock |
| Market | 15% | Peg deviation, volatility, VaR |
| Liquidity | 15% | Slippage at $100k/$500k, LP concentration |
| Collateral | 10% | Lending utilization, cascade risk |
| Reserve/Oracle | 25% | Proof of reserves, oracle freshness |

## Grade Scale

| Grade | Score | Risk Level |
|-------|-------|------------|
| A | 85-100 | Minimal Risk |
| B | 70-84 | Low Risk |
| C | 55-69 | Moderate Risk |
| D | 40-54 | Elevated Risk |
| F | 0-39 | High Risk |

## Configured Assets

| Asset | Type | Config File |
|-------|------|-------------|
| wstETH | Liquid Staking | `example_wsteth_config.json` |
| cbBTC | Wrapped BTC | `example_cbbtc_config.json` |
| WBTC | Wrapped BTC | `example_wbtc_config.json` |
| RLP | Reserve LP | `example_rlp_config.json` |

## Technology

- **Python 3.13** with Streamlit, web3.py, pandas
- **Data Sources:** Chainlink, The Graph, CoinGecko, Blockscout
- **Architecture:** Modular monolith with layered data pipeline

## Documentation

- [Architecture](./architecture.md) - System design and data flow
- [Development Guide](./development-guide.md) - Setup and contribution
- [Source Tree](./source-tree-analysis.md) - File structure and modules
- [Scoring Methodology](../PROJECT_DOCUMENTATION.md) - Detailed thresholds
