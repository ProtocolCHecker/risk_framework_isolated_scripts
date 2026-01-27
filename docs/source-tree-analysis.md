# Source Tree Analysis

> Generated: 2026-01-22 | Scan Level: Deep

## Project Structure

```
risk_framework_isolated_scripts/
│
├── 📊 PRESENTATION LAYER
│   └── streamlit_app.py          # Main Streamlit dashboard (10 tabs, ~4500 LOC)
│
├── 🧮 SCORING ENGINE
│   ├── asset_score.py            # Risk scoring implementation (~1200 LOC)
│   ├── thresholds.py             # Threshold definitions & weights (~900 LOC)
│   └── primary_checks.py         # Binary pass/fail qualification (~230 LOC)
│
├── 📡 DATA FETCHING LAYER
│   │
│   ├── [Lending Protocols]
│   │   ├── aave_data.py          # Aave V3 metrics (TVL, utilization, RLR, CLR)
│   │   ├── compound.py           # Compound V3 metrics
│   │   └── fluid.py              # Fluid DEX integration
│   │
│   ├── [DEX Protocols]
│   │   ├── uniswap.py            # Uniswap V3 pool analysis
│   │   ├── curve.py              # Curve pool analysis
│   │   ├── pancakeswap.py        # PancakeSwap V3 analysis
│   │   └── cowswap.py            # CowSwap slippage quotes
│   │
│   ├── [Verification Scripts]
│   │   ├── uniswap_check.py      # Uniswap data accuracy verification
│   │   ├── pancakeswap_check.py  # PancakeSwap data accuracy verification
│   │   └── curve_check.py        # Curve data accuracy verification
│   │
│   ├── [Risk Analysis]
│   │   ├── price_risk.py         # Volatility, VaR, CVaR, peg deviation
│   │   ├── oracle_lag.py         # Oracle freshness & cross-chain lag
│   │   ├── proof_of_reserve.py   # Reserve backing verification
│   │   ├── slippage_check.py     # DEX slippage simulation (100k/500k)
│   │   └── token_distribution.py # Holder concentration (HHI)
│   │
│   └── [Specialized]
│       ├── ankr_token_distribution.py  # Ankr API token distribution
│       └── rlp_reserve_scrapper.py     # RLP reserve scraping
│
├── 🖥️ CLI RUNNER
│   └── risk_framework.py         # Interactive CLI for running analyses
│
├── ⚙️ CONFIGURATION
│   ├── example_wsteth_config.json    # Lido wstETH config template
│   ├── example_cbbtc_config.json     # Coinbase cbBTC config template
│   ├── example_wbtc_config.json      # Wrapped BTC config template
│   ├── example_rlp_config.json       # RLP config template
│   └── test_config.json              # Test configuration
│
├── 📚 DOCUMENTATION
│   ├── PROJECT_DOCUMENTATION.md  # Comprehensive project docs (~730 lines)
│   └── docs/                     # Generated documentation (this folder)
│
├── 🔧 ENVIRONMENT
│   ├── venv/                     # Python virtual environment
│   ├── __pycache__/              # Python bytecode cache
│   └── .gitignore                # Git ignore rules
│
└── 🔒 VERSION CONTROL
    └── .git/                     # Git repository
```

## File Categories

### Entry Points

| File | Type | Description |
|------|------|-------------|
| `streamlit_app.py` | Web UI | Main dashboard entry point (`streamlit run streamlit_app.py`) |
| `risk_framework.py` | CLI | Interactive command-line interface |

### Core Scoring Modules

| File | LOC | Purpose |
|------|-----|---------|
| `asset_score.py` | ~1200 | Calculates weighted risk scores across 6 categories |
| `thresholds.py` | ~900 | Defines scoring thresholds with industry justifications |
| `primary_checks.py` | ~230 | 3 binary pass/fail checks (audit, critical issues, incidents) |

### Data Fetching Modules

| File | Data Source | Key Metrics |
|------|-------------|-------------|
| `aave_data.py` | Aave V3 on-chain | TVL, utilization, RLR, CLR, holder concentration |
| `compound.py` | Compound V3 | Collateral metrics, utilization |
| `uniswap.py` | The Graph | Pool TVL, volume, fee tier, LP positions |
| `curve.py` | Blockscout | Pool balances, gauges, LP holders |
| `pancakeswap.py` | On-chain | Pool metrics for Base chain |
| `fluid.py` | Fluid DEX | DEX liquidity analysis |
| `proof_of_reserve.py` | Chainlink PoR | Reserve/supply ratio verification |
| `oracle_lag.py` | Chainlink | Price feed freshness, cross-chain lag |
| `price_risk.py` | CoinGecko | 365-day volatility, VaR 95%, peg deviation |
| `slippage_check.py` | 1inch/CowSwap | Simulated price impact at $100k/$500k |
| `token_distribution.py` | Blockscout | Top holder %, HHI concentration |

### Verification Modules

| File | Purpose |
|------|---------|
| `uniswap_check.py` | Cross-verify Uniswap subgraph vs on-chain |
| `pancakeswap_check.py` | Cross-verify PancakeSwap data |
| `curve_check.py` | Cross-verify Curve LP data |

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INPUT                                       │
│                    (JSON Config File)                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      streamlit_app.py                                    │
│                    (Parse & Orchestrate)                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│  primary_checks   │   │   Data Fetchers   │   │   asset_score     │
│  (Qualification)  │   │  (14 modules)     │   │   (6 categories)  │
└───────────────────┘   └───────────────────┘   └───────────────────┘
            │                       │                       │
            ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCES                                 │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────┤
│  Chainlink  │  The Graph  │  CoinGecko  │   1inch     │  On-chain RPC   │
│    PoR      │  Subgraphs  │     API     │   Quotes    │  (Ethereum,     │
│  Oracles    │             │             │             │   Base, Arb)    │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘
```

## Critical Files for Development

When modifying the project, these files are most impactful:

1. **`thresholds.py`** - Change scoring weights or thresholds
2. **`asset_score.py`** - Modify scoring logic or add categories
3. **`streamlit_app.py`** - Update UI, add tabs, change visualizations
4. **`example_*.json`** - Add new asset configurations

## Module Dependencies

```
streamlit_app.py
    ├── thresholds.py
    ├── primary_checks.py
    ├── asset_score.py
    │       └── thresholds.py
    │       └── primary_checks.py
    ├── aave_data.py
    ├── compound.py
    ├── uniswap.py
    ├── curve.py
    ├── fluid.py
    ├── proof_of_reserve.py
    ├── price_risk.py
    ├── oracle_lag.py
    ├── token_distribution.py
    ├── slippage_check.py
    └── *_check.py (verification modules)
```
