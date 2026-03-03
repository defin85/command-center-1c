from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.runtime_settings.models import RuntimeSetting


SYNC_ENABLED_KEY = "pools.master_data.sync.enabled"


def _write_gate_report(path, *, overall_status: str = "pass") -> None:
    payload = {
        "schema_version": "pool_master_data_sync_readiness_gate_report.v1",
        "generated_at_utc": "2026-03-03T00:00:00Z",
        "overall_status": overall_status,
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
