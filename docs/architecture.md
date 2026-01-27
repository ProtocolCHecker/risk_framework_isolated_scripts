# Architecture Documentation

> Generated: 2026-01-22 | DeFi Risk Assessment Framework

## Executive Summary

This project is a **DeFi Asset Risk Assessment Framework** that provides quantitative risk scoring for wrapped tokens, liquid staking derivatives (LSDs), and other DeFi assets. It combines on-chain data fetching, off-chain API integration, and a weighted scoring methodology to produce letter grades (A-F) for asset risk profiles.

**Architecture Style:** Modular Monolith with Layered Data Pipeline

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│                                                                              │
│  ┌─────────────────────────────────────┐  ┌─────────────────────────────┐   │
│  │     Streamlit Dashboard (Web)       │  │    CLI Runner (Terminal)    │   │
│  │         streamlit_app.py            │  │     risk_framework.py       │   │
│  │  • 10 interactive tabs              │  │  • Interactive prompts      │   │
│  │  • JSON config upload               │  │  • Module selection         │   │
│  │  • Real-time data fetching          │  │  • Batch analysis           │   │
│  └─────────────────────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SCORING ENGINE                                    │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  primary_checks  │  │   asset_score    │  │      thresholds          │   │
│  │                  │  │                  │  │                          │   │
│  │ • 3 binary gates │  │ • 6 categories   │  │ • Industry benchmarks    │   │
│  │ • Pass/Fail      │  │ • Weighted avg   │  │ • Justifications         │   │
│  │ • Disqualify     │  │ • Circuit break  │  │ • Grade scale            │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA FETCHING LAYER                                 │
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐    │
│  │   Lending   │ │     DEX     │ │    Risk     │ │    Verification     │    │
│  │  Protocols  │ │  Protocols  │ │   Analysis  │ │      Scripts        │    │
│  ├─────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────────────┤    │
│  │ aave_data   │ │ uniswap     │ │ price_risk  │ │ uniswap_check       │    │
│  │ compound    │ │ curve       │ │ oracle_lag  │ │ curve_check         │    │
│  │ fluid       │ │ pancakeswap │ │ proof_of_   │ │ pancakeswap_check   │    │
│  │             │ │ cowswap     │ │   reserve   │ │                     │    │
│  │             │ │             │ │ slippage    │ │                     │    │
│  │             │ │             │ │ token_dist  │ │                     │    │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL DATA SOURCES                                │
│                                                                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐  │
│  │ Chainlink │ │ The Graph │ │ CoinGecko │ │   1inch   │ │  Blockscout   │  │
│  │           │ │           │ │           │ │           │ │               │  │
│  │ • PoR     │ │ • Uniswap │ │ • Prices  │ │ • Quotes  │ │ • Holders     │  │
│  │ • Oracles │ │ • Compound│ │ • History │ │ • Routes  │ │ • Balances    │  │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────────┘  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      On-Chain RPC (via dRPC)                         │    │
│  │   Ethereum │ Base │ Arbitrum │ Optimism │ Polygon │ Avalanche       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Presentation** | Streamlit | 1.53.0 | Interactive web dashboard |
| **Data Processing** | pandas | 2.3.3 | DataFrame operations |
| **Numerics** | numpy | 2.4.1 | Statistical calculations |
| **Visualization** | Plotly | 6.5.2 | Interactive charts |
| **Blockchain** | web3.py | 7.14.0 | Smart contract calls |
| **HTTP** | requests | 2.32.5 | REST API calls |
| **Async** | aiohttp | 3.13.3 | Parallel data fetching |
| **Validation** | pydantic | 2.12.5 | Config validation |
| **Runtime** | Python | 3.13.1 | Language runtime |

## Data Architecture

### Input: Configuration Schema

Assets are defined via JSON configuration files with the following structure:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Asset Configuration JSON                      │
├─────────────────────────────────────────────────────────────────┤
│ asset_metadata                                                   │
│   ├── asset_name, asset_symbol, asset_type                      │
│   ├── underlying, token_decimals                                │
│   └── token_addresses[] (multi-chain)                           │
├─────────────────────────────────────────────────────────────────┤
│ protocol_configs                                                 │
│   ├── lending_configs[] (Aave, Compound, Fluid)                 │
│   └── dex_pools[] (Uniswap, Curve, PancakeSwap)                │
├─────────────────────────────────────────────────────────────────┤
│ verification_configs                                             │
│   ├── proof_of_reserve (PoR addresses or LST verification)     │
│   ├── oracle_lag (Chainlink price feeds)                        │
│   └── oracle_freshness (freshness monitoring)                   │
├─────────────────────────────────────────────────────────────────┤
│ risk_configs                                                     │
│   └── price_risk (CoinGecko IDs for token and underlying)      │
├─────────────────────────────────────────────────────────────────┤
│ governance_configs                                               │
│   ├── multisig_configs[] (roles, thresholds, addresses)        │
│   ├── has_timelock, timelock_hours                              │
│   ├── custody_model                                              │
│   └── has_blacklist, blacklist_control                          │
├─────────────────────────────────────────────────────────────────┤
│ security_configs                                                 │
│   ├── audit_data (auditors, issues, dates)                      │
│   ├── deployment_date                                            │
│   └── incidents[] (historical security events)                  │
├─────────────────────────────────────────────────────────────────┤
│ infrastructure                                                   │
│   ├── rpc_urls (per-chain RPC endpoints)                        │
│   └── blockscout_apis (per-chain block explorers)               │
└─────────────────────────────────────────────────────────────────┘
```

### Output: Risk Score Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                      Risk Assessment Output                      │
├─────────────────────────────────────────────────────────────────┤
│ primary_checks                                                   │
│   ├── qualified: boolean                                         │
│   ├── checks[]: {id, name, status, reason}                      │
│   └── summary: string                                            │
├─────────────────────────────────────────────────────────────────┤
│ category_scores (if qualified)                                   │
│   ├── smart_contract: {score, weight: 10%, details}             │
│   ├── counterparty: {score, weight: 25%, details}               │
│   ├── market: {score, weight: 15%, details}                     │
│   ├── liquidity: {score, weight: 15%, details}                  │
│   ├── collateral: {score, weight: 10%, details}                 │
│   └── reserve_oracle: {score, weight: 25%, details}             │
├─────────────────────────────────────────────────────────────────┤
│ final_score                                                      │
│   ├── weighted_score: 0-100                                      │
│   ├── grade: A/B/C/D/F                                          │
│   ├── circuit_breakers_triggered[]                              │
│   └── risk_level: string                                         │
└─────────────────────────────────────────────────────────────────┘
```

## Scoring Methodology

### Two-Stage Evaluation

```
┌─────────────────────────────────────────────────────────────────┐
│                    STAGE 1: Primary Checks                       │
│                      (Binary Pass/Fail)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐   ┌─────────────────┐   ┌────────────────┐ │
│  │ Has Security    │   │ No Critical     │   │ No Active      │ │
│  │ Audit?          │──▶│ Audit Issues?   │──▶│ Incident?      │ │
│  └─────────────────┘   └─────────────────┘   └────────────────┘ │
│          │                     │                     │          │
│          ▼                     ▼                     ▼          │
│     ┌─────────┐           ┌─────────┐           ┌─────────┐    │
│     │  FAIL   │           │  FAIL   │           │  FAIL   │    │
│     │ ───────▶│ DISQUALIFIED ◀──────│           │◀────────│    │
│     └─────────┘           └─────────┘           └─────────┘    │
│                                                                  │
│                    ALL PASS ──▶ Proceed to Stage 2              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   STAGE 2: Weighted Scoring                      │
│                    (6 Risk Categories)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Smart Contract (10%)  ──┐                                       │
│  Counterparty (25%)    ──┼──▶  Weighted Average  ──▶  Grade     │
│  Market (15%)          ──┤         0-100              A-F       │
│  Liquidity (15%)       ──┤                                       │
│  Collateral (10%)      ──┤     Circuit Breakers                 │
│  Reserve/Oracle (25%)  ──┘     may cap score                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Category Weights Justification

| Category | Weight | Source | Rationale |
|----------|--------|--------|-----------|
| Smart Contract | 10% | DeFi Score | Lower for battle-tested code |
| Counterparty | 25% | DeFi Score, Aave | Critical for centralized custody |
| Market | 15% | Aave | Peg deviation matters for wrapped assets |
| Liquidity | 15% | Gauntlet | Essential for redemption |
| Collateral | 10% | Chaos Labs | Secondary risk for lending usage |
| Reserve/Oracle | 25% | S&P SSA, Moody's | Fundamental to asset integrity |

## Module Architecture

### Data Fetcher Pattern

Each data fetcher follows a consistent pattern:

```python
def analyze_[protocol]_market(config: dict) -> dict:
    """
    Fetch and analyze data from [Protocol].

    Args:
        config: Asset configuration dictionary

    Returns:
        Dictionary with standardized metrics:
        {
            "tvl": float,
            "utilization": float,
            "metrics": {...},
            "raw_data": {...}
        }
    """
    # 1. Extract config parameters
    # 2. Initialize Web3/HTTP clients
    # 3. Fetch on-chain or API data
    # 4. Calculate derived metrics
    # 5. Return standardized output
```

### Supported Chains

| Chain | RPC Provider | Block Explorer |
|-------|--------------|----------------|
| Ethereum | dRPC | Blockscout |
| Base | dRPC | Blockscout |
| Arbitrum | dRPC | Blockscout |
| Optimism | dRPC | Blockscout |
| Polygon | dRPC | Blockscout |

## Security Considerations

### API Key Management

- RPC endpoints use dRPC (embedded in source)
- The Graph uses public subgraph IDs
- CoinGecko uses free tier (no key)
- No secrets management system

### Data Integrity

- Verification scripts cross-check subgraph vs on-chain data
- Oracle freshness is monitored for stale prices
- Proof of Reserve verifies reserve/supply ratios

### Known Limitations

1. **Rate Limiting:** Public APIs may throttle requests
2. **Data Latency:** Subgraph data may lag behind on-chain
3. **Single Point of Failure:** No redundant data sources
4. **No Caching:** Every request fetches fresh data

## Future Architecture Considerations

### Potential Improvements

1. **Caching Layer:** Redis/memcached for API responses
2. **Background Workers:** Celery for async data fetching
3. **Database:** PostgreSQL for historical score tracking
4. **API Layer:** FastAPI for programmatic access
5. **Alerting:** Webhook notifications for score changes

### Scalability Path

```
Current:  Streamlit → Direct API calls → External sources
          (Single user, synchronous)

Future:   Load Balancer → API Gateway → Worker Pool → Cache → DB
          (Multi-user, async, persistent)
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | Streamlit | Rapid prototyping, built-in widgets |
| Data fetching | Synchronous | Simplicity over performance |
| Configuration | JSON files | Human-readable, version-controllable |
| Scoring | Weighted average | Industry-standard methodology |
| Thresholds | Hardcoded | Transparency, auditability |
| Multi-chain | Per-asset config | Flexibility for different deployments |
