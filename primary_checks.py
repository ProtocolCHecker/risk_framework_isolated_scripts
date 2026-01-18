"""
Primary Checks Module - Binary Pass/Fail Qualification Criteria.

These 3 checks must ALL pass before an asset can be scored.
If any check fails, the asset is DISQUALIFIED and no score is calculated.

Primary checks are binary (yes/no) and represent fundamental requirements
that cannot be compensated by good scores in other areas.
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum


class CheckStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass
class CheckResult:
    """Result of a single primary check."""
    check_id: str
    name: str
    status: CheckStatus
    condition: str
    actual_value: Any
    reason: str


# =============================================================================
# PRIMARY CHECK DEFINITIONS
# =============================================================================

PRIMARY_CHECKS = {
    "has_security_audit": {
        "name": "Has Security Audit",
        "category": "Smart Contract",
        "condition": "At least 1 security audit exists",
        "disqualify_reason": "No security audit found - unaudited code is unacceptable",
    },
    "no_critical_audit_issues": {
        "name": "No Critical Audit Issues",
        "category": "Smart Contract",
        "condition": "0 unresolved critical issues from audits",
        "disqualify_reason": "Critical audit issues remain unresolved - immediate exploit risk",
    },
    "no_active_incident": {
        "name": "No Active Security Incident",
        "category": "Smart Contract",
        "condition": "No security incident with fund loss in last 30 days",
        "disqualify_reason": "Active or recent security incident - avoid until resolved",
    },
}


# =============================================================================
# CHECK FUNCTIONS
# =============================================================================

def check_has_security_audit(metrics: dict) -> CheckResult:
    """Check if at least one security audit exists."""
    check_def = PRIMARY_CHECKS["has_security_audit"]

    audit_data = metrics.get("audit_data")
    has_audit = audit_data is not None and bool(audit_data)

    return CheckResult(
        check_id="has_security_audit",
        name=check_def["name"],
        status=CheckStatus.PASS if has_audit else CheckStatus.FAIL,
        condition=check_def["condition"],
        actual_value=audit_data.get("auditor", "None") if audit_data else "No audit",
        reason="Audit exists" if has_audit else check_def["disqualify_reason"],
    )


def check_no_critical_audit_issues(metrics: dict) -> CheckResult:
    """Check if there are no unresolved critical audit issues."""
    check_def = PRIMARY_CHECKS["no_critical_audit_issues"]

    audit_data = metrics.get("audit_data", {})
    issues = audit_data.get("issues", {}) if audit_data else {}
    critical_issues = issues.get("critical", 0) or 0

    passes = critical_issues == 0

    return CheckResult(
        check_id="no_critical_audit_issues",
        name=check_def["name"],
        status=CheckStatus.PASS if passes else CheckStatus.FAIL,
        condition=check_def["condition"],
        actual_value=f"{critical_issues} critical issues",
        reason="No critical issues" if passes else check_def["disqualify_reason"],
    )


def check_no_active_incident(metrics: dict) -> CheckResult:
    """Check if there are no active/recent security incidents."""
    check_def = PRIMARY_CHECKS["no_active_incident"]

    incidents = metrics.get("incidents", [])

    # Check for recent incidents with fund loss
    recent_with_loss = [
        i for i in incidents
        if i.get("days_ago", 999) < 30 and i.get("funds_lost", 0) > 0
    ]

    passes = len(recent_with_loss) == 0

    return CheckResult(
        check_id="no_active_incident",
        name=check_def["name"],
        status=CheckStatus.PASS if passes else CheckStatus.FAIL,
        condition=check_def["condition"],
        actual_value=f"{len(recent_with_loss)} recent incidents" if recent_with_loss else "No recent incidents",
        reason="No active incidents" if passes else check_def["disqualify_reason"],
    )


# =============================================================================
# MAIN EVALUATION FUNCTION
# =============================================================================

def run_primary_checks(metrics: dict) -> Dict[str, Any]:
    """
    Run all 3 primary checks on the provided metrics.

    Args:
        metrics: Dictionary containing all required metrics

    Returns:
        Dictionary with:
        - qualified: bool - True if all checks pass
        - checks: List of CheckResult objects
        - failed_checks: List of failed check IDs
        - summary: Human-readable summary
    """
    check_functions = [
        check_has_security_audit,
        check_no_critical_audit_issues,
        check_no_active_incident,
    ]

    results: List[CheckResult] = []
    failed_checks: List[str] = []

    for check_fn in check_functions:
        result = check_fn(metrics)
        results.append(result)

        if result.status == CheckStatus.FAIL:
            failed_checks.append(result.check_id)

    qualified = len(failed_checks) == 0

    # Build summary
    if qualified:
        summary = "All 3 primary checks passed. Asset qualifies for scoring."
    else:
        summary = f"DISQUALIFIED: {len(failed_checks)} of 3 checks failed."

    return {
        "qualified": qualified,
        "checks": results,
        "failed_checks": failed_checks,
        "passed_count": len(results) - len(failed_checks),
        "total_count": len(results),
        "summary": summary,
    }


def get_check_by_category(results: List[CheckResult]) -> Dict[str, List[CheckResult]]:
    """Group check results by category."""
    by_category = {}

    for result in results:
        check_def = PRIMARY_CHECKS.get(result.check_id, {})
        category = check_def.get("category", "Other")

        if category not in by_category:
            by_category[category] = []
        by_category[category].append(result)

    return by_category
