"""
Asset Risk Scoring Implementation.

This module calculates risk scores for any asset based on the defined thresholds
and provides detailed justifications for each score.

Supports wrapped assets, stablecoins, LSTs, and other DeFi tokens.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

try:
    from .thresholds import (
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
    from .primary_checks import run_primary_checks, CheckStatus
except ImportError:
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
    from primary_checks import run_primary_checks, CheckStatus


# =============================================================================
# CUSTODY MODEL DEFINITIONS (Configurable per asset)
# =============================================================================

CUSTODY_MODELS = {
    "decentralized": {
        "score": 100,
        "justification": "Smart contract custody - no counterparty risk"
    },
    "regulated_insured": {
        "score": 85,
        "justification": "Regulated custodian with insurance coverage"
    },
    "regulated": {
        "score": 70,
        "justification": "Regulated custodian without full insurance"
    },
    "unregulated": {
        "score": 45,
        "justification": "Unregulated custodian - reputation-based trust only"
    },
    "unknown": {
        "score": 20,
        "justification": "Unknown custody arrangement - highest risk"
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def score_to_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    for grade, config in GRADE_SCALE.items():
        if config["min"] <= score <= config["max"]:
            return grade
    return "F"


def get_grade_info(grade: str) -> dict:
    """Get detailed information about a grade."""
    return GRADE_SCALE.get(grade, GRADE_SCALE["F"])


def interpolate_score(value: float, thresholds: list, value_key: str, ascending: bool = True) -> Tuple[float, str]:
    """
    Interpolate score between thresholds.

    Args:
        value: The metric value
        thresholds: List of threshold dicts with value_key and 'score'
        value_key: Key name for the threshold value (e.g., 'deviation_pct', 'hhi')
        ascending: If True, higher values = lower scores (e.g., volatility)
                  If False, higher values = higher scores

    Returns:
        Tuple of (score, justification)
    """
    sorted_thresholds = sorted(thresholds, key=lambda x: x[value_key])

    # Handle edge cases
    if value <= sorted_thresholds[0][value_key]:
        t = sorted_thresholds[0]
        return (t["score"], t.get("justification", ""))

    if value >= sorted_thresholds[-1][value_key]:
        t = sorted_thresholds[-1]
        return (t["score"], t.get("justification", ""))

    # Find bracketing thresholds and interpolate
    for i in range(len(sorted_thresholds) - 1):
        lower = sorted_thresholds[i]
        upper = sorted_thresholds[i + 1]

        if lower[value_key] <= value <= upper[value_key]:
            # Linear interpolation
            range_val = upper[value_key] - lower[value_key]
            range_score = upper["score"] - lower["score"]

            if range_val == 0:
                score = lower["score"]
            else:
                ratio = (value - lower[value_key]) / range_val
                score = lower["score"] + (ratio * range_score)

            justification = f"Value {value:.2f} between thresholds {lower[value_key]} (score {lower['score']}) and {upper[value_key]} (score {upper['score']})"
            return (score, justification)

    return (50, "Unable to interpolate - using default")


# =============================================================================
# CATEGORY SCORING FUNCTIONS
# =============================================================================

def calculate_smart_contract_score(
    audit_data: dict,
    deployment_date: datetime,
    incidents: list = None
) -> Dict[str, Any]:
    """
    Calculate Smart Contract Risk score.

    Args:
        audit_data: Dict with auditor, date, issues (critical, high, medium, low)
        deployment_date: Contract deployment date
        incidents: List of security incidents

    Returns:
        Dict with score, breakdown, and justifications
    """
    incidents = incidents or []
    breakdown = {}
    justifications = []

    # 1. Audit Score (40%)
    audit_score = 80  # Base for having an audit
    audit_justification = []

    if audit_data:
        # Handle both simple and complex audit formats
        critical = 0
        high = 0
        latest_date = None
        auditors_list = []

        # Simple format: direct issues and auditor fields
        if "issues" in audit_data:
            critical = audit_data["issues"].get("critical", 0) or 0
            high = audit_data["issues"].get("high", 0) or 0

        if "auditor" in audit_data:
            auditors_list = [audit_data["auditor"]]

        if "date" in audit_data and isinstance(audit_data["date"], str):
            latest_date = audit_data["date"]

        # Complex format: nested audit arrays
        if "auditors" in audit_data and isinstance(audit_data["auditors"], list):
            auditors_list = audit_data["auditors"]

        # Check nested audit arrays for issues and dates
        audit_arrays = [
            audit_data.get("key_audits", []),
            audit_data.get("wsteth_specific_audits", []),
            audit_data.get("wbtc_specific_audits", []),
        ]
        for audit_array in audit_arrays:
            if isinstance(audit_array, list):
                for audit in audit_array:
                    if isinstance(audit, dict):
                        if "issues" in audit:
                            critical += audit["issues"].get("critical", 0) or 0
                            high += audit["issues"].get("high", 0) or 0
                        if "date" in audit:
                            audit_date_str = audit["date"]
                            if latest_date is None or audit_date_str > latest_date:
                                latest_date = audit_date_str

        # Check latest_protocol_audit
        latest_audit = audit_data.get("latest_protocol_audit", {})
        if isinstance(latest_audit, dict):
            if "issues" in latest_audit:
                critical += latest_audit["issues"].get("critical", 0) or 0
                high += latest_audit["issues"].get("high", 0) or 0
            if "date" in latest_audit:
                audit_date_str = latest_audit["date"]
                if latest_date is None or audit_date_str > latest_date:
                    latest_date = audit_date_str

        # Adjust for issues
        if critical > 0:
            audit_score *= 0.3
            audit_justification.append(f"{critical} critical issues found - severe penalty")
        elif high > 0:
            audit_score *= 0.7
            audit_justification.append(f"{high} high issues found - moderate penalty")
        else:
            audit_score = 90
            audit_justification.append("No critical or high issues - strong audit")

        # Adjust for recency
        if latest_date:
            try:
                audit_date = datetime.strptime(latest_date, "%Y-%m")
                months_ago = (datetime.now() - audit_date).days / 30

                if months_ago > 24:
                    audit_score *= 0.6
                    audit_justification.append(f"Audit is {months_ago:.0f} months old - needs refresh")
                elif months_ago > 12:
                    audit_score *= 0.8
                    audit_justification.append(f"Audit is {months_ago:.0f} months old - aging")
                else:
                    audit_justification.append(f"Audit is {months_ago:.0f} months old - recent")
            except:
                pass

        # Bonus for top-tier auditor
        top_auditors = ["OpenZeppelin", "Trail of Bits", "Consensys Diligence", "Spearbit", "ChainSecurity",
                       "Quantstamp", "Sigma Prime", "MixBytes", "Certora", "Hexens"]
        top_tier_found = [a for a in auditors_list if a in top_auditors]
        if top_tier_found:
            audit_score = min(100, audit_score * 1.1)
            audit_justification.append(f"Top-tier auditor(s) ({', '.join(top_tier_found[:3])}) - bonus applied")

        # Bonus for multiple auditors
        if len(auditors_list) >= 3:
            audit_score = min(100, audit_score * 1.05)
            audit_justification.append(f"{len(auditors_list)} auditors - diversity bonus")
    else:
        audit_score = 20
        audit_justification.append("No audit found - maximum smart contract risk")

    breakdown["audit"] = {
        "score": round(audit_score, 1),
        "weight": SMART_CONTRACT_THRESHOLDS["audit_score"]["weight"],
        "justification": " | ".join(audit_justification),
    }

    # 2. Code Maturity (30%)
    if deployment_date:
        days_deployed = (datetime.now(timezone.utc) - deployment_date.replace(tzinfo=timezone.utc)).days
    else:
        days_deployed = 0  # Unknown deployment = treat as brand new

    maturity_thresholds = SMART_CONTRACT_THRESHOLDS["code_maturity"]["thresholds"]
    maturity_score, maturity_just = interpolate_score(days_deployed, maturity_thresholds, "days")

    breakdown["maturity"] = {
        "score": round(maturity_score, 1),
        "weight": SMART_CONTRACT_THRESHOLDS["code_maturity"]["weight"],
        "justification": f"Contract deployed {days_deployed} days ago. {maturity_just}",
        "value": days_deployed,
    }

    # 3. Incident History (30%)
    incident_score = 100
    incident_justification = []

    if not incidents:
        incident_justification.append("No security incidents on record")
    else:
        for incident in incidents:
            if incident.get("funds_lost", 0) > 0:
                incident_score -= 30 + min(30, incident.get("funds_lost_pct", 0))
                incident_justification.append(f"Incident with fund loss: -{30 + min(30, incident.get('funds_lost_pct', 0))} points")
            else:
                incident_score -= 15
                incident_justification.append(f"Minor incident (no funds lost): -15 points")

    incident_score = max(0, incident_score)

    breakdown["incidents"] = {
        "score": round(incident_score, 1),
        "weight": SMART_CONTRACT_THRESHOLDS["incident_history"]["weight"],
        "justification": " | ".join(incident_justification) if incident_justification else "Clean security record",
        "count": len(incidents),
    }

    # Calculate weighted total
    total_score = (
        breakdown["audit"]["score"] * breakdown["audit"]["weight"] +
        breakdown["maturity"]["score"] * breakdown["maturity"]["weight"] +
        breakdown["incidents"]["score"] * breakdown["incidents"]["weight"]
    )

    return {
        "category": "Smart Contract Risk",
        "score": round(total_score, 1),
        "grade": score_to_grade(total_score),
        "weight": CATEGORY_WEIGHTS["smart_contract"]["weight"],
        "weight_justification": CATEGORY_WEIGHTS["smart_contract"]["justification"],
        "breakdown": breakdown,
    }


def calculate_counterparty_score(
    multisig_configs: dict,
    has_timelock: bool,
    timelock_hours: float = 0,
    custody_model: str = "unknown",
    has_blacklist: bool = False,
    blacklist_control: str = "none",
    critical_roles: list = None,
    role_weights: dict = None
) -> Dict[str, Any]:
    """
    Calculate Counterparty Risk score.

    Args:
        multisig_configs: Dict of role -> {is_multisig, threshold, total_signers, is_eoa}
        has_timelock: Whether protocol has timelock
        timelock_hours: Timelock delay in hours
        custody_model: Type of custody (decentralized, regulated_insured, regulated, unregulated, unknown)
        has_blacklist: Whether token has blacklist capability
        blacklist_control: Who controls blacklist (none, governance, multisig, eoa)
        critical_roles: List of critical admin roles to check (default: ["owner", "admin"])
        role_weights: Dict of role -> weight for scoring (default weights provided)
    """
    breakdown = {}

    # Default critical roles and weights if not provided
    if critical_roles is None:
        critical_roles = ["owner", "admin"]
    if role_weights is None:
        role_weights = {role: 5 for role in critical_roles}  # Default weight of 5 for all

    # 1. Admin Key Control (40%)
    akc_score = 100
    akc_justifications = []

    all_multisig = True
    any_eoa = False

    for role, config in multisig_configs.items():
        if role == "timelock":
            continue

        weight = role_weights.get(role, 3)

        if config.get("is_eoa"):
            any_eoa = True
            all_multisig = False
            penalty = weight * 15
            akc_score -= penalty
            akc_justifications.append(f"{role}: EOA (single key) - penalty {penalty} points")
        elif config.get("is_multisig"):
            threshold = config.get("threshold", 1)
            total = config.get("owners_count", config.get("total_signers", 1))
            ratio = threshold / total if total > 0 else 0

            # Higher ratio = more decentralized = less penalty
            penalty = weight * (1 - ratio) * 10
            akc_score -= penalty
            akc_justifications.append(f"{role}: {threshold}/{total} multisig (ratio {ratio:.2f}) - penalty {penalty:.1f} points")
        else:
            # Unknown contract
            penalty = weight * 7
            akc_score -= penalty
            akc_justifications.append(f"{role}: Unknown contract type - penalty {penalty} points")

    if not has_timelock:
        akc_score *= 0.85
        akc_justifications.append("No timelock - 15% penalty applied")
    else:
        akc_justifications.append(f"Timelock present ({timelock_hours}h delay) - no penalty")

    akc_score = max(0, akc_score)

    breakdown["admin_key_control"] = {
        "score": round(akc_score, 1),
        "weight": COUNTERPARTY_THRESHOLDS["admin_key_control"]["weight"],
        "justification": " | ".join(akc_justifications),
        "all_multisig": all_multisig,
        "any_eoa": any_eoa,
    }

    # 2. Custody Model (30%)
    custody_info = CUSTODY_MODELS.get(custody_model, CUSTODY_MODELS["unknown"])
    custody_score = custody_info["score"]
    custody_justification = custody_info["justification"]

    breakdown["custody"] = {
        "score": custody_score,
        "weight": COUNTERPARTY_THRESHOLDS["custody_model"]["weight"],
        "justification": custody_justification,
        "model": custody_model,
    }

    # 3. Timelock Presence (15%)
    timelock_thresholds = COUNTERPARTY_THRESHOLDS["timelock_presence"]["thresholds"]
    if has_timelock:
        timelock_score, timelock_just = interpolate_score(timelock_hours, timelock_thresholds, "delay_hours")
    else:
        timelock_score = 30
        timelock_just = "No timelock - actions are immediate"

    breakdown["timelock"] = {
        "score": round(timelock_score, 1),
        "weight": COUNTERPARTY_THRESHOLDS["timelock_presence"]["weight"],
        "justification": timelock_just,
        "delay_hours": timelock_hours if has_timelock else 0,
    }

    # 4. Blacklist Capability (15%)
    if not has_blacklist:
        blacklist_score = 100
        blacklist_just = "No blacklist function - censorship resistant"
    elif blacklist_control == "governance":
        blacklist_score = 75
        blacklist_just = "Blacklist requires governance approval"
    elif blacklist_control == "multisig":
        blacklist_score = 55
        blacklist_just = "Blacklist controlled by multisig - compliance trade-off"
    else:
        blacklist_score = 30
        blacklist_just = "Blacklist controlled by single entity - censorship risk"

    breakdown["blacklist"] = {
        "score": blacklist_score,
        "weight": COUNTERPARTY_THRESHOLDS["blacklist_capability"]["weight"],
        "justification": blacklist_just,
        "has_blacklist": has_blacklist,
        "control": blacklist_control,
    }

    # Calculate weighted total
    total_score = sum(
        breakdown[k]["score"] * breakdown[k]["weight"]
        for k in breakdown
    )

    return {
        "category": "Counterparty Risk",
        "score": round(total_score, 1),
        "grade": score_to_grade(total_score),
        "weight": CATEGORY_WEIGHTS["counterparty"]["weight"],
        "weight_justification": CATEGORY_WEIGHTS["counterparty"]["justification"],
        "breakdown": breakdown,
    }


def calculate_market_score(
    peg_deviation_pct: float,
    volatility_annualized_pct: float,
    var_95_pct: float
) -> Dict[str, Any]:
    """
    Calculate Market Risk score.

    Args:
        peg_deviation_pct: Price deviation from underlying (wrapped asset vs underlying)
        volatility_annualized_pct: Annualized volatility as percentage
        var_95_pct: 95% VaR as percentage
    """
    breakdown = {}

    # 1. Peg Deviation (40%)
    peg_thresholds = MARKET_THRESHOLDS["peg_deviation"]["thresholds"]
    peg_score, peg_just = interpolate_score(abs(peg_deviation_pct), peg_thresholds, "deviation_pct")

    breakdown["peg_deviation"] = {
        "score": round(peg_score, 1),
        "weight": MARKET_THRESHOLDS["peg_deviation"]["weight"],
        "justification": f"Peg deviation: {peg_deviation_pct:+.4f}%. {peg_just}",
        "value": peg_deviation_pct,
    }

    # 2. Volatility (30%)
    vol_thresholds = MARKET_THRESHOLDS["volatility_annualized"]["thresholds"]
    vol_score, vol_just = interpolate_score(volatility_annualized_pct, vol_thresholds, "volatility_pct")

    breakdown["volatility"] = {
        "score": round(vol_score, 1),
        "weight": MARKET_THRESHOLDS["volatility_annualized"]["weight"],
        "justification": f"Annualized volatility: {volatility_annualized_pct:.1f}%. {vol_just}",
        "value": volatility_annualized_pct,
    }

    # 3. VaR 95% (30%)
    var_thresholds = MARKET_THRESHOLDS["var_95"]["thresholds"]
    var_score, var_just = interpolate_score(var_95_pct, var_thresholds, "var_pct")

    breakdown["var_95"] = {
        "score": round(var_score, 1),
        "weight": MARKET_THRESHOLDS["var_95"]["weight"],
        "justification": f"95% VaR: {var_95_pct:.2f}% daily. {var_just}",
        "value": var_95_pct,
    }

    total_score = sum(
        breakdown[k]["score"] * breakdown[k]["weight"]
        for k in breakdown
    )

    return {
        "category": "Market Risk",
        "score": round(total_score, 1),
        "grade": score_to_grade(total_score),
        "weight": CATEGORY_WEIGHTS["market"]["weight"],
        "weight_justification": CATEGORY_WEIGHTS["market"]["justification"],
        "breakdown": breakdown,
    }


def calculate_liquidity_score(
    slippage_100k_pct: float,
    slippage_500k_pct: float,
    hhi: float
) -> Dict[str, Any]:
    """
    Calculate Liquidity Risk score.

    Args:
        slippage_100k_pct: Slippage for $100K trade
        slippage_500k_pct: Slippage for $500K trade
        hhi: Herfindahl-Hirschman Index (0-10000)
    """
    breakdown = {}

    # 1. Slippage at $100K (40%)
    slip_100k_thresholds = LIQUIDITY_THRESHOLDS["slippage_100k"]["thresholds"]
    slip_100k_score, slip_100k_just = interpolate_score(slippage_100k_pct, slip_100k_thresholds, "slippage_pct")

    breakdown["slippage_100k"] = {
        "score": round(slip_100k_score, 1),
        "weight": LIQUIDITY_THRESHOLDS["slippage_100k"]["weight"],
        "justification": f"$100K trade slippage: {slippage_100k_pct:.2f}%. {slip_100k_just}",
        "value": slippage_100k_pct,
    }

    # 2. Slippage at $500K (30%)
    slip_500k_thresholds = LIQUIDITY_THRESHOLDS["slippage_500k"]["thresholds"]
    slip_500k_score, slip_500k_just = interpolate_score(slippage_500k_pct, slip_500k_thresholds, "slippage_pct")

    breakdown["slippage_500k"] = {
        "score": round(slip_500k_score, 1),
        "weight": LIQUIDITY_THRESHOLDS["slippage_500k"]["weight"],
        "justification": f"$500K trade slippage: {slippage_500k_pct:.2f}%. {slip_500k_just}",
        "value": slippage_500k_pct,
    }

    # 3. HHI Concentration (30%)
    hhi_thresholds = LIQUIDITY_THRESHOLDS["hhi_concentration"]["thresholds"]
    hhi_score, hhi_just = interpolate_score(hhi, hhi_thresholds, "hhi")

    breakdown["hhi"] = {
        "score": round(hhi_score, 1),
        "weight": LIQUIDITY_THRESHOLDS["hhi_concentration"]["weight"],
        "justification": f"HHI: {hhi:.0f}. {hhi_just}",
        "value": hhi,
    }

    total_score = sum(
        breakdown[k]["score"] * breakdown[k]["weight"]
        for k in breakdown
    )

    return {
        "category": "Liquidity Risk",
        "score": round(total_score, 1),
        "grade": score_to_grade(total_score),
        "weight": CATEGORY_WEIGHTS["liquidity"]["weight"],
        "weight_justification": CATEGORY_WEIGHTS["liquidity"]["justification"],
        "breakdown": breakdown,
    }


def calculate_collateral_score(
    clr_pct: float,
    rlr_pct: float,
    utilization_pct: float
) -> Dict[str, Any]:
    """
    Calculate Collateral Risk score (lending market metrics).

    Args:
        clr_pct: Cascade Liquidation Risk percentage
        rlr_pct: Recursive Lending Ratio percentage
        utilization_pct: Pool utilization percentage
    """
    breakdown = {}

    # 1. CLR (40%)
    clr_thresholds = COLLATERAL_THRESHOLDS["cascade_liquidation_risk"]["thresholds"]
    clr_score, clr_just = interpolate_score(clr_pct, clr_thresholds, "clr_pct")

    breakdown["clr"] = {
        "score": round(clr_score, 1),
        "weight": COLLATERAL_THRESHOLDS["cascade_liquidation_risk"]["weight"],
        "justification": f"CLR: {clr_pct:.2f}% of positions at risk. {clr_just}",
        "value": clr_pct,
    }

    # 2. RLR (35%)
    rlr_thresholds = COLLATERAL_THRESHOLDS["recursive_lending_ratio"]["thresholds"]
    rlr_score, rlr_just = interpolate_score(rlr_pct, rlr_thresholds, "rlr_pct")

    breakdown["rlr"] = {
        "score": round(rlr_score, 1),
        "weight": COLLATERAL_THRESHOLDS["recursive_lending_ratio"]["weight"],
        "justification": f"RLR: {rlr_pct:.2f}% looped positions. {rlr_just}",
        "value": rlr_pct,
    }

    # 3. Utilization (25%)
    util_thresholds = COLLATERAL_THRESHOLDS["utilization_rate"]["thresholds"]
    util_score, util_just = interpolate_score(utilization_pct, util_thresholds, "util_pct")

    breakdown["utilization"] = {
        "score": round(util_score, 1),
        "weight": COLLATERAL_THRESHOLDS["utilization_rate"]["weight"],
        "justification": f"Utilization: {utilization_pct:.2f}%. {util_just}",
        "value": utilization_pct,
    }

    total_score = sum(
        breakdown[k]["score"] * breakdown[k]["weight"]
        for k in breakdown
    )

    return {
        "category": "Collateral Risk",
        "score": round(total_score, 1),
        "grade": score_to_grade(total_score),
        "weight": CATEGORY_WEIGHTS["collateral"]["weight"],
        "weight_justification": CATEGORY_WEIGHTS["collateral"]["justification"],
        "breakdown": breakdown,
    }


def calculate_reserve_oracle_score(
    reserve_ratio: float,
    oracle_freshness_minutes: float,
    cross_chain_lag_minutes: float
) -> Dict[str, Any]:
    """
    Calculate Reserve & Oracle Risk score.

    Args:
        reserve_ratio: Proof of Reserves ratio (1.0 = 100%)
        oracle_freshness_minutes: Minutes since last oracle update
        cross_chain_lag_minutes: Maximum lag between chains
    """
    breakdown = {}

    # 1. Proof of Reserves (50%)
    por_thresholds = RESERVE_ORACLE_THRESHOLDS["proof_of_reserves_ratio"]["thresholds"]

    if reserve_ratio >= 1.0:
        por_score = 95 + min(5, (reserve_ratio - 1.0) * 100)
        por_just = f"Reserve ratio: {reserve_ratio*100:.2f}% - fully backed"
    else:
        por_score = max(0, 95 - (1.0 - reserve_ratio) * 500)
        por_just = f"Reserve ratio: {reserve_ratio*100:.2f}% - UNDERCOLLATERALIZED"

    breakdown["reserves"] = {
        "score": round(por_score, 1),
        "weight": RESERVE_ORACLE_THRESHOLDS["proof_of_reserves_ratio"]["weight"],
        "justification": por_just,
        "value": reserve_ratio,
        "is_fully_backed": reserve_ratio >= 1.0,
    }

    # 2. Oracle Freshness (25%)
    fresh_thresholds = RESERVE_ORACLE_THRESHOLDS["oracle_freshness"]["thresholds"]
    fresh_score, fresh_just = interpolate_score(oracle_freshness_minutes, fresh_thresholds, "minutes")

    breakdown["oracle_freshness"] = {
        "score": round(fresh_score, 1),
        "weight": RESERVE_ORACLE_THRESHOLDS["oracle_freshness"]["weight"],
        "justification": f"Last update: {oracle_freshness_minutes:.0f} minutes ago. {fresh_just}",
        "value": oracle_freshness_minutes,
    }

    # 3. Cross-chain Lag (25%)
    lag_thresholds = RESERVE_ORACLE_THRESHOLDS["cross_chain_oracle_lag"]["thresholds"]
    lag_score, lag_just = interpolate_score(cross_chain_lag_minutes, lag_thresholds, "minutes")

    breakdown["cross_chain_lag"] = {
        "score": round(lag_score, 1),
        "weight": RESERVE_ORACLE_THRESHOLDS["cross_chain_oracle_lag"]["weight"],
        "justification": f"Cross-chain lag: {cross_chain_lag_minutes:.0f} minutes. {lag_just}",
        "value": cross_chain_lag_minutes,
    }

    total_score = sum(
        breakdown[k]["score"] * breakdown[k]["weight"]
        for k in breakdown
    )

    return {
        "category": "Reserve & Oracle Risk",
        "score": round(total_score, 1),
        "grade": score_to_grade(total_score),
        "weight": CATEGORY_WEIGHTS["reserve_oracle"]["weight"],
        "weight_justification": CATEGORY_WEIGHTS["reserve_oracle"]["justification"],
        "breakdown": breakdown,
    }


# =============================================================================
# OVERALL SCORE CALCULATION
# =============================================================================

def calculate_category_scores(metrics: dict) -> Dict[str, Any]:
    """
    Calculate all category scores from raw metrics.

    Args:
        metrics: Dict containing all required metrics

    Returns:
        Dict with all category scores and breakdowns
    """
    categories = {}

    # Smart Contract
    categories["smart_contract"] = calculate_smart_contract_score(
        audit_data=metrics.get("audit_data", {}),
        deployment_date=metrics.get("deployment_date"),
        incidents=metrics.get("incidents", []),
    )

    # Counterparty
    categories["counterparty"] = calculate_counterparty_score(
        multisig_configs=metrics.get("multisig_configs", {}),
        has_timelock=metrics.get("has_timelock", False),
        timelock_hours=metrics.get("timelock_hours", 0),
        custody_model=metrics.get("custody_model", "unknown"),
        has_blacklist=metrics.get("has_blacklist", False),
        blacklist_control=metrics.get("blacklist_control", "none"),
        critical_roles=metrics.get("critical_roles"),
        role_weights=metrics.get("role_weights"),
    )

    # Market
    categories["market"] = calculate_market_score(
        peg_deviation_pct=metrics.get("peg_deviation_pct", 0),
        volatility_annualized_pct=metrics.get("volatility_annualized_pct", 50),
        var_95_pct=metrics.get("var_95_pct", 5),
    )

    # Liquidity
    categories["liquidity"] = calculate_liquidity_score(
        slippage_100k_pct=metrics.get("slippage_100k_pct", 0.5),
        slippage_500k_pct=metrics.get("slippage_500k_pct", 1.0),
        hhi=metrics.get("hhi", 2000),
    )

    # Collateral
    categories["collateral"] = calculate_collateral_score(
        clr_pct=metrics.get("clr_pct", 5),
        rlr_pct=metrics.get("rlr_pct", 10),
        utilization_pct=metrics.get("utilization_pct", 50),
    )

    # Reserve & Oracle
    categories["reserve_oracle"] = calculate_reserve_oracle_score(
        reserve_ratio=metrics.get("reserve_ratio", 1.0),
        oracle_freshness_minutes=metrics.get("oracle_freshness_minutes", 30),
        cross_chain_lag_minutes=metrics.get("cross_chain_lag_minutes", 15),
    )

    return categories


def apply_circuit_breakers(
    base_score: float,
    category_scores: dict,
    metrics: dict
) -> Tuple[float, List[dict]]:
    """
    Apply circuit breakers to cap or modify the final score.

    Returns:
        Tuple of (adjusted_score, list of triggered breakers)
    """
    triggered = []
    score = base_score

    # Check reserve undercollateralization
    if metrics.get("reserve_ratio", 1.0) < 1.0:
        breaker = CIRCUIT_BREAKERS["reserve_undercollateralized"]
        score = min(score, breaker["max_score"])
        triggered.append({
            "name": "Reserve Undercollateralized",
            "effect": f"Score capped at {breaker['max_score']} (Grade {breaker['max_grade']})",
            "justification": breaker["justification"],
        })

    # Check if critical admin roles are EOA
    counterparty_breakdown = category_scores.get("counterparty", {}).get("breakdown", {})
    akc = counterparty_breakdown.get("admin_key_control", {})
    if akc.get("any_eoa") and not akc.get("all_multisig"):
        # Check if critical roles are EOA
        multisig_configs = metrics.get("multisig_configs", {})
        critical_roles = metrics.get("critical_roles", ["owner", "admin"])
        critical_eoa = any(
            multisig_configs.get(role, {}).get("is_eoa", False)
            for role in critical_roles
        )
        if critical_eoa:
            breaker = CIRCUIT_BREAKERS["all_admin_eoa"]
            score = min(score, breaker["max_score"])
            triggered.append({
                "name": "Critical Admin EOA",
                "effect": f"Score capped at {breaker['max_score']} (Grade {breaker['max_grade']})",
                "justification": breaker["justification"],
            })

    # Check for active security incident
    incidents = metrics.get("incidents", [])
    recent_incident = any(
        i.get("days_ago", 999) < 30 and i.get("funds_lost", 0) > 0
        for i in incidents
    )
    if recent_incident:
        breaker = CIRCUIT_BREAKERS["active_security_incident"]
        score = min(score, breaker["max_score"])
        triggered.append({
            "name": "Active Security Incident",
            "effect": f"Score capped at {breaker['max_score']} (Grade {breaker['max_grade']})",
            "justification": breaker["justification"],
        })

    # Check for critical category failure (any score < 25)
    multiplier = 1.0
    for cat_name, cat_data in category_scores.items():
        cat_score = cat_data.get("score", 50)
        if cat_score < 25:
            multiplier = min(multiplier, CIRCUIT_BREAKERS["critical_category_failure"]["multiplier"])
            triggered.append({
                "name": f"Critical Failure: {cat_data.get('category', cat_name)}",
                "effect": f"Multiplier: {CIRCUIT_BREAKERS['critical_category_failure']['multiplier']}",
                "justification": f"{cat_data.get('category', cat_name)} score is {cat_score} (< 25). {CIRCUIT_BREAKERS['critical_category_failure']['justification']}",
            })
        elif cat_score < 40:
            multiplier = min(multiplier, CIRCUIT_BREAKERS["severe_category_weakness"]["multiplier"])
            triggered.append({
                "name": f"Severe Weakness: {cat_data.get('category', cat_name)}",
                "effect": f"Multiplier: {CIRCUIT_BREAKERS['severe_category_weakness']['multiplier']}",
                "justification": f"{cat_data.get('category', cat_name)} score is {cat_score} (< 40). {CIRCUIT_BREAKERS['severe_category_weakness']['justification']}",
            })

    score *= multiplier

    # Check for no audit
    audit_data = metrics.get("audit_data")
    if not audit_data:
        breaker = CIRCUIT_BREAKERS["no_audit"]
        score = min(score, breaker["max_score"])
        triggered.append({
            "name": "No Audit",
            "effect": f"Score capped at {breaker['max_score']} (Grade {breaker['max_grade']})",
            "justification": breaker["justification"],
        })

    return score, triggered


def calculate_asset_risk_score(metrics: dict) -> Dict[str, Any]:
    """
    Calculate comprehensive asset risk score using two-stage evaluation.

    Stage 1: Primary Checks (3 binary pass/fail)
        - If any check fails, asset is DISQUALIFIED
        - No score is calculated

    Stage 2: Secondary Scoring (weighted categories)
        - Only runs if all primary checks pass
        - Calculates detailed score with circuit breakers

    Args:
        metrics: Dict containing all required metrics including:
            - asset_name: Name of the asset (e.g., "cbBTC", "WBTC")
            - asset_symbol: Symbol (e.g., "cbBTC")
            - asset_type: Type (e.g., "wrapped_btc", "stablecoin", "lst")
            - underlying: Underlying asset if applicable (e.g., "BTC", "ETH")
            - ... all other scoring metrics

    Returns:
        Complete risk assessment with qualification status, scores, grades, and justifications
    """
    # Extract asset metadata
    asset_info = {
        "name": metrics.get("asset_name", "Unknown Asset"),
        "symbol": metrics.get("asset_symbol", "???"),
        "type": metrics.get("asset_type", "token"),
        "underlying": metrics.get("underlying"),
    }

    # ==========================================================================
    # STAGE 1: PRIMARY CHECKS (Binary Pass/Fail)
    # ==========================================================================
    primary_results = run_primary_checks(metrics)

    # If any primary check fails, return DISQUALIFIED status
    if not primary_results["qualified"]:
        return {
            "asset": asset_info,
            "qualified": False,
            "status": "DISQUALIFIED",
            "primary_checks": {
                "passed": primary_results["passed_count"],
                "total": primary_results["total_count"],
                "failed_checks": primary_results["failed_checks"],
                "checks": [
                    {
                        "id": check.check_id,
                        "name": check.name,
                        "status": check.status.value,
                        "condition": check.condition,
                        "actual_value": check.actual_value,
                        "reason": check.reason,
                    }
                    for check in primary_results["checks"]
                ],
                "summary": primary_results["summary"],
            },
            "overall": None,
            "categories": None,
            "circuit_breakers": None,
            "methodology": {
                "approach": "Two-stage: Primary checks (binary) + Secondary scoring (weighted)",
                "scale": "0-100 numeric with A-F letter grades",
                "primary_checks": "3 binary pass/fail qualification criteria",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ==========================================================================
    # STAGE 2: SECONDARY SCORING (Weighted Categories)
    # ==========================================================================

    # Calculate all category scores
    category_scores = calculate_category_scores(metrics)

    # Calculate base score (weighted average)
    base_score = sum(
        cat_data["score"] * cat_data["weight"]
        for cat_data in category_scores.values()
    )

    # Apply circuit breakers
    final_score, triggered_breakers = apply_circuit_breakers(
        base_score, category_scores, metrics
    )

    final_score = round(final_score, 1)
    final_grade = score_to_grade(final_score)
    grade_info = get_grade_info(final_grade)

    return {
        "asset": asset_info,
        "qualified": True,
        "status": "QUALIFIED",
        "primary_checks": {
            "passed": primary_results["passed_count"],
            "total": primary_results["total_count"],
            "failed_checks": [],
            "checks": [
                {
                    "id": check.check_id,
                    "name": check.name,
                    "status": check.status.value,
                    "condition": check.condition,
                    "actual_value": check.actual_value,
                    "reason": check.reason,
                }
                for check in primary_results["checks"]
            ],
            "summary": primary_results["summary"],
        },
        "overall": {
            "score": final_score,
            "grade": final_grade,
            "label": grade_info["label"],
            "risk_level": grade_info["risk_level"],
            "description": grade_info["description"],
            "base_score": round(base_score, 1),
            "base_grade": score_to_grade(base_score),
        },
        "categories": category_scores,
        "circuit_breakers": {
            "triggered": triggered_breakers,
            "score_adjusted": final_score != base_score,
        },
        "methodology": {
            "approach": "Two-stage: Primary checks (binary) + Secondary scoring (weighted)",
            "scale": "0-100 numeric with A-F letter grades",
            "primary_checks": "3 binary pass/fail qualification criteria",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_score_justifications(risk_score: dict) -> List[dict]:
    """
    Extract all justifications from a risk score for display.

    Args:
        risk_score: Output from calculate_asset_risk_score

    Returns:
        List of justification entries
    """
    justifications = []

    # Overall score justification
    overall = risk_score.get("overall", {})
    if overall:
        justifications.append({
            "category": "Overall Score",
            "score": overall.get("score"),
            "grade": overall.get("grade"),
            "justification": f"Base score: {overall.get('base_score')} | Final: {overall.get('score')} | {overall.get('description')}",
        })

    # Category justifications
    for cat_key, cat_data in risk_score.get("categories", {}).items():
        justifications.append({
            "category": cat_data.get("category", cat_key),
            "score": cat_data.get("score"),
            "grade": cat_data.get("grade"),
            "weight": f"{cat_data.get('weight', 0) * 100:.0f}%",
            "justification": cat_data.get("weight_justification", ""),
        })

        # Sub-metric justifications
        for metric_key, metric_data in cat_data.get("breakdown", {}).items():
            justifications.append({
                "category": f"  └─ {metric_key}",
                "score": metric_data.get("score"),
                "weight": f"{metric_data.get('weight', 0) * 100:.0f}%",
                "justification": metric_data.get("justification", ""),
            })

    # Circuit breaker justifications
    for breaker in risk_score.get("circuit_breakers", {}).get("triggered", []):
        justifications.append({
            "category": f"Circuit Breaker: {breaker.get('name')}",
            "effect": breaker.get("effect"),
            "justification": breaker.get("justification"),
        })

    return justifications
