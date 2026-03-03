from __future__ import annotations

import json
from io import StringIO
import subprocess
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.intercompany_pools.master_data_sync_readiness_gates import (
    READINESS_GATE_SCHEMA_VERSION,
    build_readiness_gate_report,
    run_nominal_load_model,
    validate_readiness_gate_report_shape,
)


def _passing_measured_values() -> dict[str, dict[str, float]]:
    return {
        "load": {
            "reconcile_window_p95_seconds": 110.0,
            "reconcile_window_p99_seconds": 140.0,
            "coverage_ratio": 0.999,
            "partial_outcome_rate": 0.01,
        },
        "replay_consistency": {
            "lost_events_total": 0.0,
            "duplicate_apply_total": 0.0,
            "deterministic_replay_match_ratio": 1.0,
        },
        "failover_restart": {
            "checkpoint_monotonicity_violations": 0.0,
            "ack_before_commit_violations": 0.0,
            "worker_recovery_to_steady_state_seconds": 12.5,
        },
        "security": {
            "secrets_exposed_in_diagnostics": 0.0,
            "secrets_exposed_in_last_error": 0.0,
            "redaction_test_failures": 0.0,
        },
    }


def test_run_nominal_load_model_emits_expected_metrics() -> None:
    payload = run_nominal_load_model(
        windows=5,
        scopes_per_window=720,
        random_seed=42,
    )
    assert payload["model_windows"] == 5.0
    assert payload["model_scopes_per_window"] == 720.0
    assert payload["reconcile_window_p95_seconds"] > 0
    assert payload["reconcile_window_p99_seconds"] >= payload["reconcile_window_p95_seconds"]
    assert 0.0 <= payload["coverage_ratio"] <= 1.0
    assert 0.0 <= payload["partial_outcome_rate"] <= 1.0


def test_build_report_requires_orr_signoff_for_overall_pass() -> None:
    report = build_readiness_gate_report(
        measured_values_by_gate=_passing_measured_values(),
        evidence_refs_by_gate={},
        signoff_by_role={},
    )
    assert report["schema_version"] == READINESS_GATE_SCHEMA_VERSION
    assert report["overall_status"] == "fail"
    assert sorted(report["orr_signoff"]["missing_roles"]) == ["operations", "platform", "security"]
    assert validate_readiness_gate_report_shape(report) == []


@pytest.mark.django_db
def test_management_command_generates_passing_report_in_strict_mode(tmp_path) -> None:
    report_path = tmp_path / "readiness-report.json"
    out = StringIO()

    success_result = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=0,
        stdout="3 passed\n",
        stderr="",
    )

    with patch(
        "apps.intercompany_pools.management.commands.run_pool_master_data_sync_readiness_gates.subprocess.run",
        side_effect=[success_result, success_result, success_result],
    ):
        call_command(
            "run_pool_master_data_sync_readiness_gates",
            "--report-path",
            str(report_path),
            "--strict",
            "--signoff-platform",
            "platform-oncall",
            "--signoff-security",
            "security-oncall",
            "--signoff-operations",
            "operations-oncall",
            stdout=out,
        )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "pass"
    assert payload["gates"]["load"]["status"] == "pass"
    assert payload["gates"]["replay_consistency"]["status"] == "pass"
    assert payload["gates"]["failover_restart"]["status"] == "pass"
    assert payload["gates"]["security"]["status"] == "pass"
    assert payload["orr_signoff"]["status"] == "complete"


@pytest.mark.django_db
def test_management_command_strict_fails_when_any_gate_failed(tmp_path) -> None:
    report_path = tmp_path / "readiness-report-failed.json"

    success_result = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=0,
        stdout="3 passed\n",
        stderr="",
    )
    fail_result = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=1,
        stdout="1 failed\n",
        stderr="assertion failed",
    )

    with (
        patch(
            "apps.intercompany_pools.management.commands.run_pool_master_data_sync_readiness_gates.subprocess.run",
            side_effect=[success_result, fail_result, success_result],
        ),
        pytest.raises(CommandError),
    ):
        call_command(
            "run_pool_master_data_sync_readiness_gates",
            "--report-path",
            str(report_path),
            "--strict",
            "--signoff-platform",
            "platform-oncall",
            "--signoff-security",
            "security-oncall",
            "--signoff-operations",
            "operations-oncall",
        )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "fail"
    assert payload["gates"]["failover_restart"]["status"] == "fail"
