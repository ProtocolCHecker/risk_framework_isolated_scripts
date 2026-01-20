# Risk Framework - Project Documentation

## Overview

This project is a **DeFi Asset Risk Assessment Framework** that analyzes wrapped tokens and liquid staking derivatives (LSDs) across multiple dimensions: price risk, collateral risk, liquidity risk, governance, and oracle health.

The framework consists of:
1. **Quantitative data fetchers** - Scripts that pull on-chain and off-chain data
2. **Scoring engine** - Two-stage scoring system (primary checks + weighted categories)
3. **Streamlit Dashboard** - Interactive UI to visualize risk metrics

---

## Project Structure

```
risk_framework_isolated_scripts/
├── streamlit_app.py          # Main Streamlit dashboard (10 tabs)
├── asset_score.py            # Scoring logic for all risk categories
├── thresholds.py             # Threshold definitions and weights
├── config_schema.py          # JSON config validation schema
├── data_adapter.py           # Adapter layer for data fetching
│
├── example_cbbtc_config.json # Sample config for Coinbase Wrapped BTC
├── example_wsteth_config.json# Sample config for Lido wstETH
│
├── Scripts (Quantitative):
│   ├── aave_check.py         # Aave V3 lending metrics (TVL, utilization, RLR, CLR)
│   ├── compound_check.py     # Compound V3 lending metrics
│   ├── uniswap_check.py      # Uniswap V3 pool data verification
│   ├── pancakeswap_check.py  # PancakeSwap pool data verification
│   ├── curve_check.py        # Curve pool data verification
│   ├── slippage_check.py     # DEX slippage simulation (100k, 500k swaps)
│   ├── oracle_lag.py         # Cross-chain oracle lag analysis
│   ├── price_risk.py         # Price volatility, VaR, CVaR calculations
│   └── proof_of_reserve.py   # Reserve verification (wrapped assets)
│
└── PROJECT_DOCUMENTATION.md  # This file
```

---

## Config JSON Schema

Each asset requires a JSON config file. Key sections:

### Basic Info
```json
{
  "asset_name": "Lido Wrapped Staked ETH",
  "asset_symbol": "wstETH",
  "asset_type": "liquid_staking",  // or "wrapped_btc"
  "underlying": "ETH",
  "token_decimals": 18
}
```

### Token Addresses (multi-chain)
```json
"token_addresses": [
  {"chain": "ethereum", "address": "0x..."},
  {"chain": "arbitrum", "address": "0x..."},
  {"chain": "base", "address": "0x..."}
]
```

### Lending Configs
```json
"lending_configs": [
  {
    "protocol": "aave",
    "chain": "ethereum",
    "token_address": "0x...",
    "pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
    "data_provider": "0x7B4EB56E7CD4b454BA8ff71E4518426369a138a3"
  },
  {
    "protocol": "compound",
    "chain": "ethereum",
    "token_address": "0x...",
    "comet_address": "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
    "market_name": "USDC",
    "subgraph_id": "AwoxEZbiWLvv6e3QdvdMZw4WDURdGbvPfHmZRc8Dpfz9"
  }
]
```

### DEX Pools
```json
"dex_pools": [
  {
    "protocol": "uniswap",
    "chain": "ethereum",
    "pool_address": "0x...",
    "pool_name": "wstETH/WETH 0.01%",
    "subgraph_id": "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
  },
  {
    "protocol": "curve",
    "chain": "ethereum",
    "pool_address": "0x...",
    "pool_name": "stETH/ETH",
    "gauge_address": "0x...",
    "n_coins": 2
  }
]
```

### Proof of Reserve
For wrapped assets (cbBTC):
```json
"proof_of_reserve": {
  "evm_chains": [
    {"name": "ethereum", "por": "0x...", "token": "0x..."}
  ]
}
```

For liquid staking (wstETH):
```json
"proof_of_reserve": {
  "type": "liquid_staking",
  "steth_token": {"chain": "ethereum", "address": "0x..."},
  "verification_method": "Compare stETH totalSupply with validator balances"
}
```

### Oracle Config
```json
"oracle_lag": {
  "price_feed_1": {"chain": "ethereum", "address": "0x...", "name": "stETH/ETH"},
  "price_feed_2": {"chain": "ethereum", "address": "0x...", "name": "wstETH/USD"}
},
"oracle_freshness": {
  "price_feeds": [
    {"chain": "ethereum", "address": "0x...", "name": "wstETH/USD"}
  ]
}
```

### Price Risk
```json
"price_risk": {
  "token_coingecko_id": "wrapped-steth",
  "underlying_coingecko_id": "ethereum"
}
```

### Governance & Security
```json
"multisig_configs": [
  {
    "role_name": "owner",
    "is_multisig": true,
    "address": "0x...",
    "threshold": 3,
    "owners_count": 5
  }
],
"has_timelock": true,
"timelock_hours": 72,
"custody_model": "non_custodial",  // or "regulated_insured"
"has_blacklist": false
```

---

## Scoring System

### Two-Stage Approach

The scoring system uses a two-stage evaluation:

**Stage 1: Primary Checks (Binary Pass/Fail)**
If any check fails, the asset is **DISQUALIFIED** and no score is calculated.

| Check | Condition | Disqualify Reason |
|-------|-----------|-------------------|
| Has Security Audit | At least 1 security audit exists | Unaudited code is unacceptable |
| No Critical Audit Issues | 0 unresolved critical issues | Immediate exploit risk |
| No Active Security Incident | No fund loss incident in last 30 days | Avoid until resolved |

**Stage 2: Secondary Scoring (Weighted Categories)**
Only runs if all primary checks pass. Calculates detailed score with circuit breakers.

---

## Detailed Scoring Methodology

### Grade Scale

| Grade | Score Range | Label | Risk Level |
|-------|-------------|-------|------------|
| A | 85-100 | Excellent | Minimal Risk |
| B | 70-84 | Good | Low Risk |
| C | 55-69 | Adequate | Moderate Risk |
| D | 40-54 | Below Average | Elevated Risk |
| F | 0-39 | Poor | High Risk |

### Category Weights

| Category | Weight | Justification |
|----------|--------|---------------|
| Smart Contract | 10% | Lower weight for battle-tested code. DeFi Score allocates 45% for novel protocols, reduced for proven codebases. |
| Counterparty | 25% | Critical for centralized custody/issuance. Aligned with DeFi Score's centralization risk and Aave's counterparty pillar. |
| Market | 15% | Peg deviation and volatility matter for wrapped/synthetic assets. Based on Aave's market risk category. |
| Liquidity | 15% | Essential for redemption and DeFi utility. Gauntlet emphasizes slippage for liquidation efficiency. |
| Collateral | 10% | Secondary risk - depends on DeFi protocol usage. Based on Chaos Labs' cascade liquidation framework. |
| Reserve & Oracle | 25% | Fundamental to wrapped asset integrity. S&P SSA and Moody's emphasize reserve quality as primary factor. |

---

## Category 1: Smart Contract Risk (10% weight)

### 1.1 Audit Score (40% of category)

**Data Source:** Config JSON `audit_data` field (manual research)

**Formula:**
```
audit_score = base_score (80 if audit exists, 20 if not)
if critical_issues > 0: audit_score *= 0.3
if high_issues > 0: audit_score *= 0.7
if months_since_audit > 12: audit_score *= 0.8
if months_since_audit > 24: audit_score *= 0.6
if auditor in top_tier: audit_score *= 1.1 (capped at 100)
```

**Top-tier Auditors:** OpenZeppelin, Trail of Bits, Consensys Diligence, Spearbit, ChainSecurity

**Thresholds:**
| Condition | Score | Justification |
|-----------|-------|---------------|
| Multiple top-tier audits, no issues | 100 | DeFiSafety maximum for comprehensive coverage |
| Single reputable audit, no issues | 80 | Most protocols launch with one audit |
| Audit >12 months or minor issues | 60 | DeFi Score penalizes old audits |
| No audit or critical issues | 20 | Unaudited = highest risk |

### 1.2 Code Maturity (30% of category)

**Data Source:** Config JSON `deployment_date` field

**Formula:** Linear interpolation between thresholds based on `days_deployed`

**Thresholds:**
| Days Deployed | Score | Justification |
|---------------|-------|---------------|
| 730+ (2 years) | 100 | Battle-tested through market cycles |
| 365 (1 year) | 85 | DeFi Score maturity benchmark |
| 180 (6 months) | 70 | Most exploits occur in first months |
| 90 (3 months) | 50 | Minimum for initial confidence |
| 30 (1 month) | 30 | High-risk early period |
| 0 | 10 | Brand new - extreme caution |

### 1.3 Incident History (30% of category)

**Data Source:** Config JSON `incidents` array

**Formula:**
```
base = 100
for incident in incidents:
    if incident.funds_lost > 0:
        base -= 30 + min(30, incident.funds_lost_pct)
    else:
        base -= 15
return max(0, base)
```

---

## Category 2: Counterparty Risk (25% weight)

### 2.1 Admin Key Control (40% of category)

**Data Source:** Config JSON `multisig_configs`, `has_timelock`, `critical_roles`, `role_weights`

**Formula:**
```
akc_score = 100
for role in admin_roles:
    weight = role_weights.get(role, 3)
    if role.is_eoa:
        akc_score -= weight * 15
    elif role.is_multisig:
        threshold_ratio = role.threshold / role.total_signers
        penalty = weight * (1 - threshold_ratio) * 10
        akc_score -= penalty
    elif role.is_dao_voting:
        dao_score = calculate_dao_score(role.dao_safeguards)  # See below
        penalty = weight * (100 - dao_score) / 100 * 10
        akc_score -= penalty
    else:
        akc_score -= weight * 7  # Unknown contract
if not has_timelock:
    akc_score *= 0.85
return max(0, akc_score)
```

**Thresholds:**
| Configuration | Score | Justification |
|---------------|-------|---------------|
| All 4+/7+ multisig with timelock | 100 | Aave governance standard |
| All 3+/5+ multisig with timelock | 90 | Gnosis Safe default |
| All 2+/3+ multisig with timelock | 75 | Low redundancy |
| Mixed multisig/EOA with timelock | 55 | Partial decentralization |
| Multisig but no timelock | 45 | No community response time |
| Any critical role is EOA | 25 | Single key = highest risk |

#### DAO Voting Scoring

DAO voting is evaluated separately due to inherent risks (51% attacks, low participation, token concentration).

**Base Score:** 50 (moderate risk)
**Max Score:** 80 (never equals high-threshold multisig)

**Safeguard Bonuses:**
| Safeguard | Bonus | Justification |
|-----------|-------|---------------|
| `has_veto_power` | +15 | Guardian/council can block malicious proposals |
| `has_dual_governance` | +10 | Opposition mechanism for token holders (e.g., Lido LIP-28) |
| `quorum_pct >= 10%` | +5 | Higher quorum reduces low-participation attack risk |

**Config Example:**
```json
{
  "role_name": "dao_governance",
  "is_dao_voting": true,
  "dao_safeguards": {
    "has_veto_power": true,
    "has_dual_governance": true,
    "quorum_pct": 5
  }
}
```

**Why DAO voting is capped at 80:**
- Proven 51% attacks (Aragon 2023)
- Typical participation <10%
- Token concentration enables governance capture

### 2.2 Custody Model (30% of category)

**Data Source:** Config JSON `custody_model` field

**Thresholds:**
| Model | Score | Justification |
|-------|-------|---------------|
| decentralized | 100 | No counterparty risk - smart contract custody |
| regulated_insured | 85 | Regulatory oversight + insurance |
| regulated | 70 | Compliance but limited loss protection |
| unregulated | 45 | Reputation-based trust only |
| unknown | 20 | Highest custodian risk |

### 2.3 Timelock Presence (15% of category)

**Data Source:** Config JSON `has_timelock`, `timelock_hours`

**Thresholds:**
| Delay (hours) | Score | Justification |
|---------------|-------|---------------|
| 168+ (7 days) | 100 | Compound standard for full review |
| 48 | 85 | Reasonable minimum |
| 24 | 70 | Basic review time |
| 6 | 50 | Only prevents immediate rug |
| 0 | 30 | Actions are immediate |

### 2.4 Blacklist Capability (15% of category)

**Data Source:** Config JSON `has_blacklist`, `blacklist_control`

**Thresholds:**
| Capability | Score | Justification |
|------------|-------|---------------|
| No blacklist | 100 | Censorship-resistant |
| Governance-controlled | 75 | Requires decentralized approval |
| Multisig-controlled | 55 | Compliance trade-off |
| Single entity/EOA | 30 | Highest censorship risk |

---

## Category 3: Market Risk (15% weight)

### 3.1 Peg Deviation (40% of category)

**Data Source:** CoinGecko API via `price_risk.py`
- Fetches prices for `token_coingecko_id` and `underlying_coingecko_id`
- Calculates deviation: `(token_price / underlying_price - 1) * 100`

**Thresholds:**
| Deviation % | Score | Justification |
|-------------|-------|---------------|
| < 0.1% | 100 | Within normal arbitrage bounds |
| < 0.5% | 90 | S&P SSA considers stable |
| < 1.0% | 75 | Acceptable for wrapped assets |
| < 2.0% | 55 | Liquidity stress indicator |
| < 5.0% | 30 | Significant depeg warning |
| > 5.0% | 10 | Serious peg failure |

### 3.2 Volatility Annualized (30% of category)

**Data Source:** CoinGecko API via `price_risk.py`
- Fetches 365 days of historical prices
- Calculates: `std(daily_returns) * sqrt(365) * 100`

**Formula:** `score = max(0, 100 - (volatility_pct - 20) * 1.25)`

**Thresholds:**
| Volatility % | Score | Justification |
|--------------|-------|---------------|
| < 20% | 100 | Low for crypto, comparable to gold |
| 20-40% | 80 | Moderate, large-cap in calm markets |
| 40-60% | 60 | BTC historical average |
| 60-80% | 40 | Stress period volatility |
| > 80% | 20 | Crisis-level |

### 3.3 VaR 95% (30% of category)

**Data Source:** CoinGecko API via `price_risk.py`
- Calculates: `percentile(daily_returns, 5)` (5th percentile)

**Thresholds:**
| VaR % | Score | Justification |
|-------|-------|---------------|
| < 3% | 100 | Conservative, low tail risk |
| 3-5% | 85 | Gauntlet baseline threshold |
| 5-8% | 65 | Typical crypto volatility |
| 8-12% | 45 | Significant drawdown risk |
| > 12% | 25 | Flash crash territory |

---

## Category 4: Liquidity Risk (15% weight)

### 4.1 Slippage at $100K (40% of category)

**Data Source:** `slippage_check.py`
- Uses 1inch API / DEX aggregators
- Simulates $100K swap and calculates price impact

**Thresholds:**
| Slippage % | Score | Justification |
|------------|-------|---------------|
| < 0.1% | 100 | Excellent depth |
| < 0.3% | 90 | Institutional-grade |
| < 0.5% | 80 | Good for most traders |
| 0.5-1.0% | 65 | CowSwap acceptable range |
| 1.0-2.0% | 45 | Significant execution cost |
| > 2.0% | 20 | Liquidation efficiency at risk |

### 4.2 Slippage at $500K (30% of category)

**Data Source:** `slippage_check.py` (same method, larger amount)

**Thresholds:**
| Slippage % | Score | Justification |
|------------|-------|---------------|
| < 0.5% | 100 | Deep institutional liquidity |
| < 1.0% | 85 | Large trades execute cleanly |
| 1.0-2.0% | 65 | Acceptable for large trades |
| 2.0-5.0% | 40 | May need to split orders |
| > 5.0% | 15 | Thin liquidity |

### 4.3 HHI Concentration (30% of category)

**Data Source:** Blockscout API via `curve_check.py` / `uniswap_check.py`
- Fetches top LP holders
- Calculates: `HHI = sum(market_share_i^2) * 10000`

**Thresholds:**
| HHI | Score | Justification |
|-----|-------|---------------|
| < 1000 | 100 | Unconcentrated (DOJ/FTC standard) |
| 1000-1500 | 85 | Healthy LP diversity |
| 1500-2500 | 65 | DOJ review threshold |
| 2500-4000 | 45 | Whale LP risk |
| 4000-6000 | 25 | Single LP could destabilize |
| > 6000 | 5 | Approaching monopoly |

---

## Category 5: Collateral Risk (10% weight)

*Metrics are TVL-weighted averages across all lending markets*

### 5.1 Cascade Liquidation Risk (40% of category)

**Data Source:** `aave_check.py`, `compound_check.py`
- Queries on-chain positions with health factor < 1.1
- CLR = (value_at_risk / total_supplied) * 100

**Thresholds:**
| CLR % | Score | Justification |
|-------|-------|---------------|
| < 2% | 100 | Minimal cascade potential |
| 2-5% | 85 | Gauntlet acceptable range |
| 5-10% | 65 | Elevated cascade risk |
| 10-20% | 40 | Significant liquidation wave possible |
| > 20% | 20 | Cascade liquidation likely |

### 5.2 Recursive Lending Ratio (35% of category)

**Data Source:** `aave_check.py`, `compound_check.py`
- Detects looped positions (borrow → deposit cycles)
- RLR = (looped_value / total_supplied) * 100

**Thresholds:**
| RLR % | Score | Justification |
|-------|-------|---------------|
| < 5% | 100 | Minimal leverage risk |
| 5-10% | 80 | Some yield farming |
| 10-20% | 60 | Notable leverage |
| 20-35% | 40 | Significant deleverage risk |
| > 35% | 20 | System heavily leveraged |

### 5.3 Utilization Rate (25% of category)

**Data Source:** `aave_check.py`, `compound_check.py`
- On-chain query: utilization = (borrowed / supplied) * 100

**Thresholds:**
| Utilization % | Score | Justification |
|---------------|-------|---------------|
| < 50% | 100 | Healthy buffer |
| 50-70% | 85 | Aave optimal range |
| 70-85% | 65 | Approaching rate curve kink |
| 85-95% | 40 | Withdrawal constrained |
| > 95% | 15 | Suppliers may not withdraw |

---

## Category 6: Reserve & Oracle Risk (25% weight)

### 6.1 Proof of Reserves (50% of category)

**Data Source:** `proof_of_reserve.py`
- For Chainlink PoR: Queries `evm_chains[].por` aggregator contracts
- Compares: (reserves / total_supply)

**Formula:**
```
if ratio >= 1.0:
    score = 95 + min(5, (ratio - 1.0) * 100)
else:
    score = max(0, 95 - (1.0 - ratio) * 500)
```

**Thresholds:**
| Ratio | Score | Justification |
|-------|-------|---------------|
| > 102% | 100 | Overcollateralized buffer |
| 100% | 95 | Minimum for A grade |
| 99% | 70 | Minor shortfall (timing/rounding) |
| 98% | 50 | 2% unbacked is material |
| 95% | 25 | Significant shortfall |
| < 95% | 10 | Solvency concern |

### 6.2 Oracle Freshness (25% of category)

**Data Source:** `oracle_lag.py`
- On-chain query to Chainlink aggregators
- Reads `latestRoundData().updatedAt`
- Calculates: `(now - updatedAt) / 60` (minutes)

**Thresholds:**
| Minutes | Score | Justification |
|---------|-------|---------------|
| < 5 | 100 | Real-time (Chainlink heartbeat) |
| < 30 | 90 | Within normal update cycle |
| 30-60 | 75 | Chainlink 1hr heartbeat |
| 60-180 | 50 | Price may have moved |
| 180-360 | 25 | Arbitrage risk |
| > 360 | 10 | Oracle effectively offline |

### 6.3 Cross-Chain Oracle Lag (25% of category)

**Data Source:** `oracle_lag.py`
- Queries same oracle on multiple chains
- Calculates: max(|timestamp_chain_a - timestamp_chain_b|)

**Thresholds:**
| Minutes | Score | Justification |
|---------|-------|---------------|
| < 5 | 100 | Excellent cross-chain sync |
| < 15 | 85 | Minor arbitrage window |
| 15-30 | 70 | Acceptable for most use cases |
| 30-60 | 50 | Meaningful arbitrage opportunity |
| 60-120 | 30 | Problematic for cross-chain ops |

---

## Circuit Breakers

Circuit breakers cap or modify the final score regardless of category scores:

| Breaker | Condition | Effect | Justification |
|---------|-----------|--------|---------------|
| Reserve Undercollateralized | PoR ratio < 100% | Max grade C (score ≤ 69) | S&P/Moody's require full backing |
| Critical Admin EOA | Critical role controlled by single key | Max grade D (score ≤ 54) | Single key = maximum centralization |
| Active Security Incident | Fund loss < 30 days ago | Max grade F (score ≤ 39) | DeFiSafety immediately downgrades |
| Critical Category Failure | Any category < 25 | Score × 0.5 | Exponential risk framework |
| Severe Category Weakness | Any category < 40 | Score × 0.7 | Cannot offset with other areas |
| No Audit | Never audited | Max grade D (score ≤ 54) | DeFiSafety requires audit for 70%+ |

---

## Data Sources Summary

| Data Type | Source | Script |
|-----------|--------|--------|
| Price data (365 days) | CoinGecko API | `price_risk.py` |
| Proof of Reserves | Chainlink PoR contracts | `proof_of_reserve.py` |
| Oracle timestamps | Chainlink aggregators | `oracle_lag.py` |
| Lending metrics (Aave) | Aave V3 Pool + DataProvider | `aave_check.py` |
| Lending metrics (Compound) | Compound V3 Comet contracts | `compound_check.py` |
| DEX liquidity (Uniswap) | The Graph subgraphs | `uniswap_check.py` |
| DEX liquidity (Curve) | Blockscout API | `curve_check.py` |
| LP holder concentration | Blockscout API | `curve_check.py`, `uniswap_check.py` |
| Slippage simulation | 1inch API / Aggregators | `slippage_check.py` |
| Audit/Governance data | Manual research | Config JSON |

---

## Key Metrics Explained

- **RLR (Recursive Lending Ratio)**: % of supply in looped positions
- **CLR (Cascade Liquidation Risk)**: % of debt with health factor < 1.1
- **HHI (Herfindahl-Hirschman Index)**: Liquidity concentration across pools (0-10000)
- **Slippage**: Price impact for 100k/500k USD swaps
- **TVL-weighted averaging**: Lending metrics are aggregated weighted by TVL
- **VaR 95%**: Maximum expected daily loss at 95% confidence

---

## Streamlit App Tabs

1. **Protocol Info** - Basic asset info, addresses, security features
2. **Lending Analysis** - Aave/Compound metrics per market
3. **DEX Liquidity** - Pool TVL, volume, slippage data
4. **Data Accuracy** - Subgraph vs on-chain data comparison
5. **Risk Metrics** - Price risk, collateral risk, liquidity risk scores
6. **Oracle Health** - Freshness and cross-chain lag
7. **Proof of Reserve** - Reserve backing verification
8. **Governance** - Multisig analysis, timelock status
9. **Audit History** - Audit reports and incidents
10. **Final Score** - Aggregated risk score with breakdown

---

## Key Contract Addresses Reference

### Aave V3 Pools
| Chain | Pool | Data Provider |
|-------|------|---------------|
| Ethereum | 0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2 | 0x7B4EB56E7CD4b454BA8ff71E4518426369a138a3 |
| Arbitrum | 0x794a61358D6845594F94dc1DB02A252b5b4814aD | 0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654 |
| Base | 0xA238Dd80C259a72e81d7e4664a9801593F98d1c5 | 0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A |

### Compound V3 Comets (Ethereum)
| Market | Comet Address |
|--------|---------------|
| USDC | 0xc3d688B66703497DAA19211EEdff47f25384cdc3 |
| WETH | 0xA17581A9E3356d9A858b789D68B4d866e593aE94 |
| USDT | 0x3Afdc9BCA9213A35503b077a6072F3D0d5AB0840 |

### Subgraph IDs
| Protocol | Chain | Subgraph ID |
|----------|-------|-------------|
| Uniswap V3 | Ethereum | 5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV |
| Uniswap V3 | Arbitrum | FQ6JYszEKApsBpAmiHesRsd9Ygc6mzmpNRANeVQFYoVX |
| Uniswap V3 | Base | 43Hwfi3dJSoGpyas9VwNoDAv55yjgGrPpNSmbQZArzMG |
| Compound V3 | Ethereum | AwoxEZbiWLvv6e3QdvdMZw4WDURdGbvPfHmZRc8Dpfz9 |

---

## Recent Changes Log

### Latest Session (Jan 2026)
- Added wstETH config with full research
- Fixed Aave Base data provider: `0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A`
- Added Compound V3 USDC/USDT markets for wstETH
- Added PancakeSwap Base pool: `0xBd59a718E60bd868123C6E949c9fd97185EFbDB7`
- Added Uniswap V3 Arbitrum pool for wstETH

### Previous Session
- Implemented TVL-weighted averaging for lending metrics (RLR, CLR, Utilization)
- Removed "distribution" metric from Liquidity Risk scoring
- Updated Liquidity Risk weights: slippage_100k (40%), slippage_500k (30%), HHI (30%)
- Fixed price risk calculation (removed *100 multiplication, changed to 365 days)
- Added Oracle Lag and Freshness to Risk Metrics tab
- Added Data Accuracy tab

---

## How to Run

```bash
# Install dependencies
pip install streamlit pandas web3 requests

# Run the dashboard
streamlit run streamlit_app.py
```

Load a config JSON file in the app to analyze an asset.

---

## Assets Currently Configured

1. **cbBTC** (Coinbase Wrapped BTC) - `example_cbbtc_config.json`
   - Type: wrapped_btc
   - Chains: Ethereum, Base, Arbitrum, Solana
   - Has Proof of Reserve via Chainlink

2. **wstETH** (Lido Wrapped Staked ETH) - `example_wsteth_config.json`
   - Type: liquid_staking
   - Chains: Ethereum, Arbitrum, Base, Optimism, Polygon
   - Reserve verified via stETH total supply

---

## Notes for Future Development

1. **Optimism support**: Architecture exists but not yet implemented for lending/DEX
2. **Balancer pools**: Currently no subgraph integration (direct on-chain only)
3. **Proof of Reserve for LSDs**: Different verification method than wrapped assets
4. **The Graph API keys**: Required for subgraph queries in production
