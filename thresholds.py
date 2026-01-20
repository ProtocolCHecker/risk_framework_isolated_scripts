"""
Risk Scoring Thresholds and Justifications.

All thresholds are based on industry standards from:
- Gauntlet Network (VaR methodology, simulation-based risk)
- Chaos Labs (Aave risk parameters)
- Aave Risk Framework (A+ to D- scale, LTV/liquidation thresholds)
- DeFi Score by ConsenSys (smart contract, financial, centralization weights)
- L2Beat (stage framework, exit windows)
- S&P/Moody's (stablecoin stability assessments)

Each threshold includes:
- value: The numeric threshold
- score: The score assigned when metric meets this threshold
- justification: Why this threshold was chosen (with source)
"""

# =============================================================================
# GRADE SCALE
# =============================================================================

GRADE_SCALE = {
    "A": {
        "min": 85,
        "max": 100,
        "label": "Excellent",
        "risk_level": "Minimal Risk",
        "description": "Asset exhibits strong fundamentals across all risk dimensions. "
                      "Comparable to investment-grade ratings in traditional finance.",
    },
    "B": {
        "min": 70,
        "max": 84,
        "label": "Good",
        "risk_level": "Low Risk",
        "description": "Asset shows solid risk profile with minor concerns in some areas. "
                      "Suitable for most risk-tolerant portfolios.",
    },
    "C": {
        "min": 55,
        "max": 69,
        "label": "Adequate",
        "risk_level": "Moderate Risk",
        "description": "Asset has notable risk factors that require monitoring. "
                      "Position sizing and hedging recommended.",
    },
    "D": {
        "min": 40,
        "max": 54,
        "label": "Below Average",
        "risk_level": "Elevated Risk",
        "description": "Asset exhibits significant risk factors. "
                      "Only suitable for high-risk tolerance with active management.",
    },
    "F": {
        "min": 0,
        "max": 39,
        "label": "Poor",
        "risk_level": "High Risk",
        "description": "Asset has critical risk factors that could result in substantial loss. "
                      "Extreme caution advised.",
    },
}

# =============================================================================
# CATEGORY WEIGHTS
# =============================================================================

CATEGORY_WEIGHTS = {
    "smart_contract": {
        "weight": 0.10,
        "justification": "Weight depends on code complexity and maturity. For battle-tested "
                        "code (OpenZeppelin-based, simple ERC20), lower weight is justified. "
                        "Industry standard: DeFi Score allocates 45% to smart contract risk "
                        "for novel protocols, reduced for proven codebases."
    },
    "counterparty": {
        "weight": 0.25,
        "justification": "Critical for assets with centralized custody or issuance. "
                        "Custodian failure means asset loses value. Aligned with DeFi Score's "
                        "centralization risk (25%) and Aave's counterparty risk pillar. "
                        "S&P SSA framework emphasizes issuer/custodian risk."
    },
    "market": {
        "weight": 0.15,
        "justification": "Peg deviation and volatility matter for wrapped/synthetic assets. "
                        "Asset should track underlying closely. Weight based on Aave's "
                        "market risk category."
    },
    "liquidity": {
        "weight": 0.15,
        "justification": "Essential for redemption capability and DeFi utility. Aligns with "
                        "DeFi Score's financial risk component (30% split). Gauntlet emphasizes "
                        "slippage analysis for liquidation efficiency."
    },
    "collateral": {
        "weight": 0.10,
        "justification": "Secondary risk - depends on DeFi protocol usage. Important for "
                        "lending market integrations but not core to asset value proposition. "
                        "Based on Chaos Labs' cascade liquidation risk framework."
    },
    "reserve_oracle": {
        "weight": 0.25,
        "justification": "Fundamental to wrapped/backed asset integrity. 1:1 backing with "
                        "underlying is the core value proposition. Aligned with S&P SSA's "
                        "reserve quality focus (primary factor) and Moody's proposed "
                        "stablecoin methodology emphasizing reserve assessment."
    },
}

# =============================================================================
# SMART CONTRACT RISK THRESHOLDS
# =============================================================================

SMART_CONTRACT_THRESHOLDS = {
    "audit_score": {
        "weight": 0.40,
        "thresholds": [
            {
                "condition": "Multiple audits from top-tier firms, no critical/high issues",
                "score": 100,
                "justification": "DeFiSafety awards maximum points for comprehensive audit coverage. "
                                "Top-tier auditors (OpenZeppelin, Trail of Bits, Consensys Diligence) "
                                "provide highest assurance. Zero critical issues is baseline for A grade."
            },
            {
                "condition": "Single audit from reputable firm, no critical issues",
                "score": 80,
                "justification": "DeFiSafety considers single audit sufficient for 70%+ score. "
                                "Most protocols launch with one audit. Score reflects adequate "
                                "but not exceptional security review."
            },
            {
                "condition": "Audit exists but older than 12 months or minor issues found",
                "score": 60,
                "justification": "DeFi Score penalizes audits older than 6-12 months. Code may have "
                                "changed since audit. Industry standard is re-audit after major changes."
            },
            {
                "condition": "No formal audit or critical issues found",
                "score": 20,
                "justification": "Unaudited code represents highest smart contract risk. "
                                "DeFiSafety assigns 0% to protocols without any audit coverage."
            },
        ],
        "scoring_formula": """
        audit_score = base_score
        if critical_issues > 0: audit_score *= 0.3
        if high_issues > 0: audit_score *= 0.7
        if months_since_audit > 12: audit_score *= 0.8
        if months_since_audit > 24: audit_score *= 0.6
        """,
    },
    "code_maturity": {
        "weight": 0.30,
        "thresholds": [
            {"days": 730, "score": 100, "justification": "2+ years deployment = battle-tested. Aave considers time on mainnet as key maturity indicator."},
            {"days": 365, "score": 85, "justification": "1+ year shows resilience through market cycles. DeFi Score uses 1 year as maturity benchmark."},
            {"days": 180, "score": 70, "justification": "6 months provides reasonable confidence. Most exploits occur in first months."},
            {"days": 90, "score": 50, "justification": "3 months is minimum for initial confidence. Still in high-risk early period."},
            {"days": 30, "score": 30, "justification": "1 month - very new code, highest exploit risk window."},
            {"days": 0, "score": 10, "justification": "Brand new deployment - extreme caution required."},
        ],
        "scoring_formula": "Linear interpolation between thresholds based on days_deployed.",
    },
    "incident_history": {
        "weight": 0.30,
        "thresholds": [
            {"incidents": 0, "score": 100, "justification": "No security incidents is the baseline expectation for A grade."},
            {"incidents": 1, "minor": True, "score": 70, "justification": "Minor incident (no funds lost) shows vulnerability but quick response."},
            {"incidents": 1, "minor": False, "score": 40, "justification": "Major incident with fund loss significantly impacts trust. Recovery matters."},
            {"incidents": 2, "score": 20, "justification": "Multiple incidents indicate systemic security issues."},
        ],
        "scoring_formula": """
        base = 100
        for incident in incidents:
            if incident.funds_lost > 0:
                base -= 30 + min(30, incident.funds_lost_pct)
            else:
                base -= 15
        return max(0, base)
        """,
    },
}

# =============================================================================
# COUNTERPARTY RISK THRESHOLDS
# =============================================================================

COUNTERPARTY_THRESHOLDS = {
    "admin_key_control": {
        "weight": 0.40,
        "description": "Measures centralization of admin privileges",
        "thresholds": [
            {
                "config": "All roles: 4+ of 7+ multisig with timelock",
                "score": 100,
                "justification": "Highest decentralization standard. Aave governance uses similar thresholds. "
                                "4/7 requires majority consensus, timelock allows community response."
            },
            {
                "config": "All roles: 3+ of 5+ multisig with timelock",
                "score": 90,
                "justification": "Strong decentralization. 3/5 is common secure configuration (e.g., Gnosis Safe default)."
            },
            {
                "config": "All roles: 2+ of 3+ multisig with timelock",
                "score": 75,
                "justification": "Adequate decentralization. 2/3 prevents single-party action but low redundancy."
            },
            {
                "config": "Mixed: some multisig, some EOA, timelock present",
                "score": 55,
                "justification": "Partial decentralization. EOA roles represent single points of failure."
            },
            {
                "config": "All roles: multisig but no timelock",
                "score": 45,
                "justification": "Immediate execution risk. Multisig helps but no time for community to react."
            },
            {
                "config": "Any critical role is EOA",
                "score": 25,
                "justification": "Single key controls critical functions. Highest centralization risk."
            },
        ],
        "scoring_formula": """
        akc_score = 100
        for role in admin_roles:
            if role.is_eoa:
                akc_score -= role.risk_weight * 15
            elif role.is_multisig:
                threshold_ratio = role.threshold / role.total_signers
                # Higher ratio = more decentralized = less penalty
                penalty = role.risk_weight * (1 - threshold_ratio) * 10
                akc_score -= penalty
        if not has_timelock:
            akc_score *= 0.85
        return max(0, akc_score)
        """,
    },
    "custody_model": {
        "weight": 0.30,
        "thresholds": [
            {
                "model": "Decentralized/trustless (smart contract custody)",
                "score": 100,
                "justification": "No counterparty risk for custody. Assets held by immutable contracts."
            },
            {
                "model": "Regulated custodian (SEC/OCC licensed) with insurance",
                "score": 85,
                "justification": "Regulatory oversight provides recourse. Insurance covers operational "
                                "failures. S&P rates regulated custodians higher."
            },
            {
                "model": "Regulated custodian without full insurance",
                "score": 70,
                "justification": "Regulatory compliance but limited loss protection."
            },
            {
                "model": "Unregulated but reputable custodian",
                "score": 45,
                "justification": "Reputation-based trust only. No regulatory recourse."
            },
            {
                "model": "Unknown or offshore custodian",
                "score": 20,
                "justification": "Highest custodian risk. No oversight or accountability."
            },
        ],
    },
    "timelock_presence": {
        "weight": 0.15,
        "thresholds": [
            {"delay_hours": 168, "score": 100, "justification": "7+ day timelock allows full community review. Compound standard."},
            {"delay_hours": 48, "score": 85, "justification": "48 hours is reasonable minimum for complex proposals."},
            {"delay_hours": 24, "score": 70, "justification": "24 hours allows basic review but limits response time."},
            {"delay_hours": 6, "score": 50, "justification": "6 hours is minimal - only prevents immediate rug."},
            {"delay_hours": 0, "score": 30, "justification": "No timelock - actions are immediate. High risk."},
        ],
    },
    "blacklist_capability": {
        "weight": 0.15,
        "thresholds": [
            {
                "capability": "No blacklist function",
                "score": 100,
                "justification": "Censorship-resistant. Funds cannot be frozen by issuer."
            },
            {
                "capability": "Blacklist with governance approval only",
                "score": 75,
                "justification": "Blacklist exists but requires decentralized approval."
            },
            {
                "capability": "Blacklist controlled by multisig",
                "score": 55,
                "justification": "Issuer can freeze addresses. Required for compliance but "
                                "introduces censorship risk. Penalty reflects trade-off."
            },
            {
                "capability": "Blacklist controlled by single entity/EOA",
                "score": 30,
                "justification": "Single party can freeze any user's funds. Highest censorship risk."
            },
        ],
    },
}

# =============================================================================
# DAO VOTING THRESHOLDS
# =============================================================================

DAO_VOTING_THRESHOLDS = {
    "base_score": 50,
    "max_score": 80,
    "description": "DAO voting is less secure than high-threshold multisig due to 51% attack risk, "
                   "low participation rates, and potential token concentration. Safeguards can improve score.",
    "safeguard_bonuses": {
        "has_veto_power": {
            "bonus": 15,
            "justification": "Guardian/council veto power can block malicious proposals, "
                            "providing critical safety mechanism against governance attacks."
        },
        "has_dual_governance": {
            "bonus": 10,
            "justification": "Dual governance allows token holders to oppose harmful changes, "
                            "adding an extra layer of protection (e.g., Lido LIP-28)."
        },
        "high_quorum": {
            "threshold_pct": 10,
            "bonus": 5,
            "justification": "Quorum >= 10% reduces risk of low-participation attacks. "
                            "Many DAOs have quorums as low as 1%, which is risky."
        },
    },
    "justification": "DAO voting carries inherent risks: proven 51% attacks (Aragon 2023), "
                    "typical participation <10%, and potential token concentration. "
                    "Max score of 80 reflects that DAO voting never equals high-threshold multisig security."
}

# =============================================================================
# MARKET RISK THRESHOLDS
# =============================================================================

MARKET_THRESHOLDS = {
    "peg_deviation": {
        "weight": 0.40,
        "description": "Measures price deviation from underlying asset",
        "thresholds": [
            {"deviation_pct": 0.1, "score": 100, "justification": "< 0.1% deviation is excellent peg maintenance. Within normal arbitrage bounds."},
            {"deviation_pct": 0.5, "score": 90, "justification": "< 0.5% is strong. S&P SSA considers this range stable."},
            {"deviation_pct": 1.0, "score": 75, "justification": "< 1% is acceptable for wrapped assets. Minor arbitrage opportunity."},
            {"deviation_pct": 2.0, "score": 55, "justification": "1-2% deviation indicates liquidity stress or confidence issues."},
            {"deviation_pct": 5.0, "score": 30, "justification": "2-5% is significant depeg. Warning level."},
            {"deviation_pct": 10.0, "score": 10, "justification": "> 5% indicates serious peg failure."},
        ],
        "scoring_formula": "Linear interpolation. Score = 100 - (deviation_pct * 20), capped at bounds.",
    },
    "volatility_annualized": {
        "weight": 0.30,
        "description": "Annualized price volatility (standard deviation of returns)",
        "thresholds": [
            {"volatility_pct": 20, "score": 100, "justification": "< 20% annualized is low for crypto. Comparable to gold."},
            {"volatility_pct": 40, "score": 80, "justification": "20-40% is moderate. Typical for large-cap crypto in calm markets."},
            {"volatility_pct": 60, "score": 60, "justification": "40-60% is elevated. BTC historical average ~50-60%."},
            {"volatility_pct": 80, "score": 40, "justification": "60-80% is high. Stress period volatility."},
            {"volatility_pct": 100, "score": 20, "justification": "> 80% is extreme. Crisis-level volatility."},
        ],
        "scoring_formula": "Score = max(0, 100 - (volatility_pct - 20) * 1.25)",
    },
    "var_95": {
        "weight": 0.30,
        "description": "95% Value at Risk - maximum expected daily loss at 95% confidence",
        "thresholds": [
            {"var_pct": 3, "score": 100, "justification": "< 3% daily VaR is conservative. Low tail risk."},
            {"var_pct": 5, "score": 85, "justification": "3-5% is moderate. Gauntlet uses 5% as baseline threshold."},
            {"var_pct": 8, "score": 65, "justification": "5-8% is elevated. Typical crypto during volatility."},
            {"var_pct": 12, "score": 45, "justification": "8-12% is high. Significant daily drawdown risk."},
            {"var_pct": 15, "score": 25, "justification": "> 12% is extreme. Flash crash territory."},
        ],
        "scoring_formula": "Score = max(0, 100 - (var_pct * 5))",
    },
}

# =============================================================================
# LIQUIDITY RISK THRESHOLDS
# =============================================================================

LIQUIDITY_THRESHOLDS = {
    "slippage_100k": {
        "weight": 0.40,
        "description": "Price impact for $100K trade",
        "thresholds": [
            {"slippage_pct": 0.1, "score": 100, "justification": "< 0.1% slippage at $100K is excellent depth."},
            {"slippage_pct": 0.3, "score": 90, "justification": "< 0.3% is very good. Institutional-grade liquidity."},
            {"slippage_pct": 0.5, "score": 80, "justification": "< 0.5% is good. Acceptable for most traders."},
            {"slippage_pct": 1.0, "score": 65, "justification": "0.5-1% is moderate. CowSwap considers this acceptable."},
            {"slippage_pct": 2.0, "score": 45, "justification": "1-2% is poor. Significant execution cost."},
            {"slippage_pct": 5.0, "score": 20, "justification": "> 2% is very poor. Liquidation efficiency at risk."},
        ],
    },
    "slippage_500k": {
        "weight": 0.30,
        "description": "Price impact for $500K trade",
        "thresholds": [
            {"slippage_pct": 0.5, "score": 100, "justification": "< 0.5% at $500K indicates deep institutional liquidity."},
            {"slippage_pct": 1.0, "score": 85, "justification": "< 1% is strong. Most large trades can execute cleanly."},
            {"slippage_pct": 2.0, "score": 65, "justification": "1-2% is acceptable for large trades."},
            {"slippage_pct": 5.0, "score": 40, "justification": "2-5% is concerning. May need to split orders."},
            {"slippage_pct": 10.0, "score": 15, "justification": "> 5% indicates thin liquidity for institutional size."},
        ],
    },
    "hhi_concentration": {
        "weight": 0.30,
        "description": "Herfindahl-Hirschman Index for LP concentration (0-10000)",
        "thresholds": [
            {"hhi": 1000, "score": 100, "justification": "HHI < 1000 is unconcentrated market. DOJ/FTC standard."},
            {"hhi": 1500, "score": 85, "justification": "1000-1500 is low concentration. Healthy LP diversity."},
            {"hhi": 2500, "score": 65, "justification": "1500-2500 is moderate concentration. DOJ review threshold."},
            {"hhi": 4000, "score": 45, "justification": "2500-4000 is high concentration. Whale LP risk."},
            {"hhi": 6000, "score": 25, "justification": "4000-6000 is very high. Single LP could destabilize pool."},
            {"hhi": 10000, "score": 5, "justification": "HHI approaching 10000 is monopoly. Single LP controls pool."},
        ],
        "scoring_formula": "Score = max(0, 100 - (HHI / 100))",
    },
}

# =============================================================================
# COLLATERAL RISK THRESHOLDS (LENDING MARKETS)
# =============================================================================

COLLATERAL_THRESHOLDS = {
    "cascade_liquidation_risk": {
        "weight": 0.40,
        "description": "Percentage of positions at risk of liquidation (HF < 1.1)",
        "thresholds": [
            {"clr_pct": 2, "score": 100, "justification": "< 2% at-risk is healthy. Minimal cascade potential."},
            {"clr_pct": 5, "score": 85, "justification": "2-5% is low risk. Gauntlet considers this acceptable."},
            {"clr_pct": 10, "score": 65, "justification": "5-10% is moderate. Elevated cascade risk in downturn."},
            {"clr_pct": 20, "score": 40, "justification": "10-20% is high. Significant liquidation wave possible."},
            {"clr_pct": 30, "score": 20, "justification": "> 20% is critical. Cascade liquidation likely in stress."},
        ],
        "scoring_formula": "Score = max(0, 100 - (CLR_pct * 3))",
    },
    "recursive_lending_ratio": {
        "weight": 0.35,
        "description": "Percentage of supply in looped/leveraged positions",
        "thresholds": [
            {"rlr_pct": 5, "score": 100, "justification": "< 5% looping is minimal leverage risk."},
            {"rlr_pct": 10, "score": 80, "justification": "5-10% is low. Some yield farming activity."},
            {"rlr_pct": 20, "score": 60, "justification": "10-20% is moderate. Notable leverage in system."},
            {"rlr_pct": 35, "score": 40, "justification": "20-35% is high. Significant deleverage risk."},
            {"rlr_pct": 50, "score": 20, "justification": "> 35% is critical. System heavily leveraged."},
        ],
        "scoring_formula": "Score = max(0, 100 - (RLR_pct * 2))",
    },
    "utilization_rate": {
        "weight": 0.25,
        "description": "Lending pool utilization (borrowed / supplied)",
        "thresholds": [
            {"util_pct": 50, "score": 100, "justification": "< 50% utilization is healthy buffer."},
            {"util_pct": 70, "score": 85, "justification": "50-70% is optimal range per Aave interest rate model."},
            {"util_pct": 85, "score": 65, "justification": "70-85% is elevated. Approaching kink in rate curve."},
            {"util_pct": 95, "score": 40, "justification": "85-95% is high. Withdrawal liquidity constrained."},
            {"util_pct": 100, "score": 15, "justification": "> 95% is critical. Suppliers may not be able to withdraw."},
        ],
    },
}

# =============================================================================
# RESERVE & ORACLE RISK THRESHOLDS
# =============================================================================

RESERVE_ORACLE_THRESHOLDS = {
    "proof_of_reserves_ratio": {
        "weight": 0.50,
        "description": "On-chain verified reserves / total supply",
        "thresholds": [
            {"ratio": 1.02, "score": 100, "justification": "> 102% reserves provides buffer. Overcollateralized."},
            {"ratio": 1.00, "score": 95, "justification": "100% exactly backed. Minimum acceptable for A grade."},
            {"ratio": 0.99, "score": 70, "justification": "99% is minor shortfall. May be timing/rounding."},
            {"ratio": 0.98, "score": 50, "justification": "98% is concerning. 2% unbacked is material."},
            {"ratio": 0.95, "score": 25, "justification": "95% is significant shortfall. Redemption risk."},
            {"ratio": 0.90, "score": 10, "justification": "< 95% is critical. Solvency concern."},
        ],
        "scoring_formula": """
        if ratio >= 1.0:
            score = 95 + min(5, (ratio - 1.0) * 100)
        else:
            score = max(0, 95 - (1.0 - ratio) * 500)
        """,
    },
    "oracle_freshness": {
        "weight": 0.25,
        "description": "Time since last oracle update",
        "thresholds": [
            {"minutes": 5, "score": 100, "justification": "< 5 min is real-time. Chainlink heartbeat standard."},
            {"minutes": 30, "score": 90, "justification": "< 30 min is fresh. Within normal update cycle."},
            {"minutes": 60, "score": 75, "justification": "30-60 min is acceptable. Chainlink 1hr heartbeat."},
            {"minutes": 180, "score": 50, "justification": "1-3 hours is stale. Price may have moved significantly."},
            {"minutes": 360, "score": 25, "justification": "3-6 hours is very stale. Arbitrage risk."},
            {"minutes": 720, "score": 10, "justification": "> 6 hours is critical. Oracle effectively offline."},
        ],
    },
    "cross_chain_oracle_lag": {
        "weight": 0.25,
        "description": "Maximum lag between chain oracle updates",
        "thresholds": [
            {"minutes": 5, "score": 100, "justification": "< 5 min cross-chain sync is excellent."},
            {"minutes": 15, "score": 85, "justification": "< 15 min is good. Minor arbitrage window."},
            {"minutes": 30, "score": 70, "justification": "15-30 min is acceptable for most use cases."},
            {"minutes": 60, "score": 50, "justification": "30-60 min creates meaningful arbitrage opportunity."},
            {"minutes": 120, "score": 30, "justification": "1-2 hour lag is problematic for cross-chain operations."},
        ],
    },
}

# =============================================================================
# CIRCUIT BREAKERS
# =============================================================================

CIRCUIT_BREAKERS = {
    "reserve_undercollateralized": {
        "condition": "Proof of Reserves ratio < 100%",
        "max_grade": "C",
        "max_score": 69,
        "justification": "Fundamental backing issue. Asset is not fully redeemable. "
                        "S&P SSA and Moody's frameworks both emphasize full reserve backing "
                        "as baseline requirement. Cannot achieve A or B grade without it."
    },
    "all_admin_eoa": {
        "condition": "All critical admin roles controlled by EOA (single key)",
        "max_grade": "D",
        "max_score": 54,
        "justification": "Maximum centralization risk. Single compromised key can drain funds "
                        "or freeze protocol. DeFi Score heavily penalizes EOA admin. "
                        "Aave requires multisig for all protocol changes."
    },
    "active_security_incident": {
        "condition": "Ongoing or recent (< 30 days) security incident with fund loss",
        "max_grade": "F",
        "max_score": 39,
        "justification": "Active risk to user funds. DeFiSafety immediately downgrades protocols "
                        "with active incidents. Users should not deposit until resolved."
    },
    "critical_category_failure": {
        "condition": "Any category score < 25",
        "multiplier": 0.5,
        "justification": "Critical weakness in one area represents systemic risk. "
                        "Exponential framework multiplies (not averages) risks to capture this."
    },
    "severe_category_weakness": {
        "condition": "Any category score < 40",
        "multiplier": 0.7,
        "justification": "Severe weakness significantly impacts overall risk profile. "
                        "Cannot offset with strong scores in other areas."
    },
    "no_audit": {
        "condition": "Smart contract has never been audited",
        "max_grade": "D",
        "max_score": 54,
        "justification": "DeFiSafety requires audit for 70%+ score. Unaudited code is "
                        "highest smart contract risk regardless of other factors."
    },
}
