"""
Unit tests for primary_checks module.

Primary checks are binary pass/fail gates that must ALL pass
before an asset can be scored. These tests verify:
1. Has Security Audit check
2. No Critical Audit Issues check
3. No Active Security Incident check
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from primary_checks import (
    run_primary_checks,
    check_has_security_audit,
    check_no_critical_audit_issues,
    check_no_active_incident,
    CheckStatus,
    PRIMARY_CHECKS,
)


class TestHasSecurityAudit:
    """Tests for the 'has security audit' primary check."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_passes_with_audit_data(self, passing_primary_checks_metrics):
        """Asset with audit data should pass."""
        result = check_has_security_audit(passing_primary_checks_metrics)
        assert result.status == CheckStatus.PASS
        assert "Audit exists" in result.reason

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_fails_without_audit_data(self, failing_audit_metrics):
        """Asset without audit data should fail."""
        result = check_has_security_audit(failing_audit_metrics)
        assert result.status == CheckStatus.FAIL
        assert "unaudited" in result.reason.lower()

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_fails_with_empty_audit_data(self):
        """Asset with empty audit_data dict should fail."""
        metrics = {"audit_data": {}}
        result = check_has_security_audit(metrics)
        assert result.status == CheckStatus.FAIL

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_handles_complex_audit_format(self, sample_wsteth_config):
        """Should handle complex audit format with multiple auditors."""
        result = check_has_security_audit(sample_wsteth_config)
        assert result.status == CheckStatus.PASS
        # Should show auditor count
        assert "auditors" in result.actual_value.lower()


class TestNoCriticalAuditIssues:
    """Tests for the 'no critical audit issues' primary check."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_passes_with_no_critical_issues(self, passing_primary_checks_metrics):
        """Asset with 0 unresolved critical issues should pass."""
        result = check_no_critical_audit_issues(passing_primary_checks_metrics)
        assert result.status == CheckStatus.PASS
        assert "0 critical issues" in result.actual_value

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_fails_with_unresolved_critical_issues(self, failing_critical_issues_metrics):
        """Asset with unresolved critical issues should fail."""
        result = check_no_critical_audit_issues(failing_critical_issues_metrics)
        assert result.status == CheckStatus.FAIL

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_handles_nested_audit_arrays(self):
        """Should check critical issues in nested audit arrays."""
        metrics = {
            "audit_data": {
                "key_audits": [
                    {"issues": {"critical": 0}},
                    {"issues": {"critical": 1}},  # This should cause failure
                ]
            }
        }
        result = check_no_critical_audit_issues(metrics)
        assert result.status == CheckStatus.FAIL

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_prefers_unresolved_over_issues(self):
        """Should use 'unresolved.critical' if present, not 'issues.critical'."""
        metrics = {
            "audit_data": {
                "latest_protocol_audit": {
                    "issues": {"critical": 5},  # Found 5 critical
                    "unresolved": {"critical": 0}  # But all resolved
                }
            }
        }
        result = check_no_critical_audit_issues(metrics)
        assert result.status == CheckStatus.PASS


class TestNoActiveIncident:
    """Tests for the 'no active security incident' primary check."""

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_passes_with_no_incidents(self):
        """Asset with no incidents should pass."""
        metrics = {"incidents": []}
        result = check_no_active_incident(metrics)
        assert result.status == CheckStatus.PASS

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_passes_with_old_incident(self):
        """Asset with incident > 30 days ago should pass."""
        metrics = {
            "incidents": [
                {"days_ago": 60, "funds_lost": 1000000}
            ]
        }
        result = check_no_active_incident(metrics)
        assert result.status == CheckStatus.PASS

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_fails_with_recent_incident_with_fund_loss(self):
        """Asset with recent incident AND fund loss should fail."""
        metrics = {
            "incidents": [
                {"days_ago": 15, "funds_lost": 500000}
            ]
        }
        result = check_no_active_incident(metrics)
        assert result.status == CheckStatus.FAIL

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_passes_with_recent_incident_no_fund_loss(self):
        """Asset with recent incident but NO fund loss should pass."""
        metrics = {
            "incidents": [
                {"days_ago": 5, "funds_lost": 0}  # Bug found but no loss
            ]
        }
        result = check_no_active_incident(metrics)
        assert result.status == CheckStatus.PASS


class TestRunPrimaryChecks:
    """Tests for the main run_primary_checks function."""

    @pytest.mark.unit
    @pytest.mark.scoring
    @pytest.mark.smoke
    def test_all_checks_pass(self, passing_primary_checks_metrics):
        """When all checks pass, asset should be qualified."""
        result = run_primary_checks(passing_primary_checks_metrics)
        assert result["qualified"] is True
        assert result["passed_count"] == 3
        assert result["total_count"] == 3
        assert len(result["failed_checks"]) == 0

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_single_check_fails(self, failing_audit_metrics):
        """When any check fails, asset should be disqualified."""
        result = run_primary_checks(failing_audit_metrics)
        assert result["qualified"] is False
        assert "has_security_audit" in result["failed_checks"]

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_returns_all_check_results(self, passing_primary_checks_metrics):
        """Should return CheckResult objects for all 3 checks."""
        result = run_primary_checks(passing_primary_checks_metrics)
        assert len(result["checks"]) == 3

        check_ids = [c.check_id for c in result["checks"]]
        assert "has_security_audit" in check_ids
        assert "no_critical_audit_issues" in check_ids
        assert "no_active_incident" in check_ids

    @pytest.mark.unit
    @pytest.mark.scoring
    def test_summary_reflects_status(self, passing_primary_checks_metrics, failing_audit_metrics):
        """Summary message should reflect qualification status."""
        passing_result = run_primary_checks(passing_primary_checks_metrics)
        assert "qualifies for scoring" in passing_result["summary"].lower()

        failing_result = run_primary_checks(failing_audit_metrics)
        assert "disqualified" in failing_result["summary"].lower()
