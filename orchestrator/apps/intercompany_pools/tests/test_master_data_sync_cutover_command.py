from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.runtime_settings.models import RuntimeSetting


SYNC_ENABLED_KEY = "pools.master_data.sync.enabled"


def _write_gate_report(path, *, overall_status: str = "pass", orr_complete: bool = True) -> None:
    missing_roles = [] if orr_complete else ["operations"]
    signed_off_by = {
        "platform": "platform.lead",
        "security": "security.lead",
        "operations": "operations.lead" if orr_complete else "",
    }
    gate_payload = {
        "status": "pass",
        "measured_values": {},
        "thresholds": {},
        "checks": [],
        "evidence_refs": [],
    }
    payload = {
        "schema_version": "pool_master_data_sync_readiness_gate_report.v1",
        "generated_at_utc": "2026-03-03T00:00:00Z",
        "overall_status": overall_status,
        "gates": {
            "load": dict(gate_payload),
            "replay_consistency": dict(gate_payload),
            "failover_restart": dict(gate_payload),
            "security": dict(gate_payload),
        },
        "orr_signoff": {
            "required_roles": ["platform", "security", "operations"],
            "signed_off_by": signed_off_by,
            "missing_roles": missing_roles,
            "status": "complete" if orr_complete else "missing",
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.django_db
def test_cutover_command_dry_run_does_not_mutate_runtime_setting(tmp_path) -> None:
    RuntimeSetting.objects.update_or_create(key=SYNC_ENABLED_KEY, defaults={"value": False})
    report_path = tmp_path / "cutover-dry-run.json"
    gate_report_path = tmp_path / "gate-report.json"
    _write_gate_report(gate_report_path, overall_status="pass")

    call_command(
        "run_pool_master_data_sync_cutover",
        "--report-path",
        str(report_path),
        "--gate-report-path",
        str(gate_report_path),
        "--strict",
    )

    RuntimeSetting.objects.get(key=SYNC_ENABLED_KEY)
    assert RuntimeSetting.objects.get(key=SYNC_ENABLED_KEY).value is False

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["execution_mode"] == "dry_run"
    assert payload["overall_status"] == "pass"
    assert payload["stages"]["freeze"]["applied"] is False
    assert payload["stages"]["enable"]["applied"] is False


@pytest.mark.django_db
def test_cutover_command_apply_mode_enables_sync_runtime_setting(tmp_path) -> None:
    RuntimeSetting.objects.update_or_create(key=SYNC_ENABLED_KEY, defaults={"value": False})
    report_path = tmp_path / "cutover-apply.json"
    gate_report_path = tmp_path / "gate-report-pass.json"
    _write_gate_report(gate_report_path, overall_status="pass")

    call_command(
        "run_pool_master_data_sync_cutover",
        "--report-path",
        str(report_path),
        "--gate-report-path",
        str(gate_report_path),
        "--execute-enable",
        "--strict",
    )

    assert RuntimeSetting.objects.get(key=SYNC_ENABLED_KEY).value is True

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["execution_mode"] == "apply"
    assert payload["overall_status"] == "pass"
    assert payload["stages"]["freeze"]["applied"] is True
    assert payload["stages"]["enable"]["applied"] is True
    assert payload["stages"]["enable"]["enabled_value_after"] is True


@pytest.mark.django_db
def test_cutover_command_strict_fails_when_gate_report_not_pass(tmp_path) -> None:
    RuntimeSetting.objects.update_or_create(key=SYNC_ENABLED_KEY, defaults={"value": False})
    report_path = tmp_path / "cutover-failed.json"
    gate_report_path = tmp_path / "gate-report-failed.json"
    _write_gate_report(gate_report_path, overall_status="fail")

    with pytest.raises(CommandError):
        call_command(
            "run_pool_master_data_sync_cutover",
            "--report-path",
            str(report_path),
            "--gate-report-path",
            str(gate_report_path),
            "--strict",
        )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "fail"
    assert payload["stages"]["gate_report"]["overall_status"] == "fail"


@pytest.mark.django_db
def test_cutover_command_execute_enable_does_not_enable_runtime_when_gate_report_failed(tmp_path) -> None:
    RuntimeSetting.objects.update_or_create(key=SYNC_ENABLED_KEY, defaults={"value": False})
    report_path = tmp_path / "cutover-failed-apply.json"
    gate_report_path = tmp_path / "gate-report-failed.json"
    _write_gate_report(gate_report_path, overall_status="fail")

    with pytest.raises(CommandError):
        call_command(
            "run_pool_master_data_sync_cutover",
            "--report-path",
            str(report_path),
            "--gate-report-path",
            str(gate_report_path),
            "--execute-enable",
            "--strict",
        )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "fail"
    assert payload["stages"]["gate_report"]["overall_status"] == "fail"
    assert payload["stages"]["enable"]["applied"] is False
    assert payload["stages"]["enable"]["enabled_value_after"] is False
    assert RuntimeSetting.objects.get(key=SYNC_ENABLED_KEY).value is False


@pytest.mark.django_db
def test_cutover_command_execute_enable_requires_complete_orr_signoff(tmp_path) -> None:
    RuntimeSetting.objects.update_or_create(key=SYNC_ENABLED_KEY, defaults={"value": False})
    report_path = tmp_path / "cutover-missing-orr.json"
    gate_report_path = tmp_path / "gate-report-missing-orr.json"
    _write_gate_report(gate_report_path, overall_status="pass", orr_complete=False)

    with pytest.raises(CommandError):
        call_command(
            "run_pool_master_data_sync_cutover",
            "--report-path",
            str(report_path),
            "--gate-report-path",
            str(gate_report_path),
            "--execute-enable",
            "--strict",
        )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "fail"
    assert payload["stages"]["gate_report"]["orr_status"] == "missing"
    assert payload["stages"]["enable"]["applied"] is False
    assert payload["stages"]["enable"]["enabled_value_after"] is False
    assert RuntimeSetting.objects.get(key=SYNC_ENABLED_KEY).value is False


@pytest.mark.django_db
def test_cutover_command_strict_fails_on_malformed_gate_report_json(tmp_path) -> None:
    RuntimeSetting.objects.update_or_create(key=SYNC_ENABLED_KEY, defaults={"value": False})
    report_path = tmp_path / "cutover-invalid-json.json"
    gate_report_path = tmp_path / "gate-report-invalid.json"
    gate_report_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(CommandError):
        call_command(
            "run_pool_master_data_sync_cutover",
            "--report-path",
            str(report_path),
            "--gate-report-path",
            str(gate_report_path),
            "--execute-enable",
            "--strict",
        )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "fail"
    assert payload["stages"]["gate_report"]["overall_status"] == "invalid"
    assert "GATE_REPORT_INVALID_JSON" in payload["stages"]["gate_report"]["blocking_reasons"]
    assert payload["stages"]["enable"]["applied"] is False
    assert payload["stages"]["enable"]["enabled_value_after"] is False
    assert RuntimeSetting.objects.get(key=SYNC_ENABLED_KEY).value is False


@pytest.mark.django_db
def test_cutover_command_strict_fails_on_partial_gate_report_shape(tmp_path) -> None:
    RuntimeSetting.objects.update_or_create(key=SYNC_ENABLED_KEY, defaults={"value": False})
    report_path = tmp_path / "cutover-partial-shape.json"
    gate_report_path = tmp_path / "gate-report-partial.json"
    partial_payload = {
        "schema_version": "pool_master_data_sync_readiness_gate_report.v1",
        "generated_at_utc": "2026-03-03T00:00:00Z",
        "overall_status": "pass",
        "gates": {
            "load": {
                "status": "pass",
                "measured_values": {},
            }
        },
    }
    gate_report_path.write_text(json.dumps(partial_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(CommandError):
        call_command(
            "run_pool_master_data_sync_cutover",
            "--report-path",
            str(report_path),
            "--gate-report-path",
            str(gate_report_path),
            "--execute-enable",
            "--strict",
        )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    gate_stage = payload["stages"]["gate_report"]
    assert payload["overall_status"] == "fail"
    assert gate_stage["overall_status"] == "pass"
    assert gate_stage["schema_valid"] is False
    assert "GATE_REPORT_SCHEMA_INVALID" in gate_stage["blocking_reasons"]
    assert "GATE_REPORT_ORR_INCOMPLETE" in gate_stage["blocking_reasons"]
    assert any("gates.replay_consistency is required" in err for err in gate_stage["schema_errors"])
    assert any("orr_signoff is required" in err for err in gate_stage["schema_errors"])
    assert payload["stages"]["enable"]["applied"] is False
    assert payload["stages"]["enable"]["enabled_value_after"] is False
    assert RuntimeSetting.objects.get(key=SYNC_ENABLED_KEY).value is False
