from __future__ import annotations

from datetime import timezone as dt_timezone
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max
from django.utils import timezone

from apps.intercompany_pools.models import (
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
)
from apps.intercompany_pools.master_data_sync_readiness_gates import (
    READINESS_GATE_SCHEMA_VERSION,
    validate_readiness_gate_report_shape,
)
from apps.operations.models import WorkflowEnqueueOutbox
from apps.runtime_settings.models import RuntimeSetting


REPO_ROOT = Path(__file__).resolve().parents[5]
SYNC_ENABLED_KEY = "pools.master_data.sync.enabled"
DEFAULT_CUTOVER_REPORT_PATH = (
    REPO_ROOT
    / "docs"
    / "observability"
    / "artifacts"
    / "refactor-08"
    / "pool-master-data-sync-cutover-report.json"
)
DEFAULT_GATE_REPORT_PATH = (
    REPO_ROOT
    / "docs"
    / "observability"
    / "artifacts"
    / "refactor-08"
    / "pool-master-data-sync-readiness-gate-report.json"
)
SYNC_ROLES = {"inbound", "outbound", "reconcile", "manual_remediation"}


def _to_rfc3339_utc(value) -> str | None:
    if value is None:
        return None
    normalized = value.astimezone(dt_timezone.utc).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


class Command(BaseCommand):
    help = (
        "Run pool master-data sync cutover workflow "
        "(freeze -> drain -> watermark capture -> enable) and persist JSON report."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--report-path",
            default=str(DEFAULT_CUTOVER_REPORT_PATH),
            help=f"Path to JSON report (default: {DEFAULT_CUTOVER_REPORT_PATH}).",
        )
        parser.add_argument(
            "--gate-report-path",
            default=str(DEFAULT_GATE_REPORT_PATH),
            help=f"Path to readiness gate report JSON (default: {DEFAULT_GATE_REPORT_PATH}).",
        )
        parser.add_argument(
            "--execute-enable",
            action="store_true",
            help="Apply freeze+enable in runtime settings (non-prod single-shot cutover mode).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print report payload as JSON.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail with non-zero exit when gate report is not pass, drain is not clean, or enable failed.",
        )

    def handle(self, *args: Any, **options: Any):
        report_path = self._resolve_path(str(options.get("report_path") or str(DEFAULT_CUTOVER_REPORT_PATH)))
        gate_report_path = self._resolve_path(str(options.get("gate_report_path") or str(DEFAULT_GATE_REPORT_PATH)))
        execute_enable = bool(options.get("execute_enable"))
        strict = bool(options.get("strict"))
        as_json = bool(options.get("json"))

        before = self._read_sync_enabled_setting()
        freeze_stage = self._freeze_stage(apply_changes=execute_enable)
        drain_stage = self._collect_drain_stage()
        watermark_stage = self._capture_watermark_stage()
        gate_report_stage = self._load_gate_report_stage(gate_report_path)
        enable_blockers = self._collect_enablement_blockers(
            gate_report_stage=gate_report_stage,
            drain_stage=drain_stage,
        )
        apply_enable = execute_enable and not enable_blockers
        enable_stage = self._enable_stage(apply_changes=apply_enable)
        if execute_enable and enable_blockers:
            enable_stage["blocked"] = True
            enable_stage["blocking_reasons"] = list(enable_blockers)
        after = self._read_sync_enabled_setting()

        report = {
            "schema_version": "pool_master_data_sync_cutover_report.v1",
            "generated_at_utc": _to_rfc3339_utc(timezone.now()),
            "execution_mode": "apply" if execute_enable else "dry_run",
            "overall_status": "pass",
            "runtime_setting_key": SYNC_ENABLED_KEY,
            "before": before,
            "stages": {
                "freeze": freeze_stage,
                "drain": drain_stage,
                "watermark_capture": watermark_stage,
                "gate_report": gate_report_stage,
                "enable": enable_stage,
            },
            "after": after,
        }

        if str(gate_report_stage.get("overall_status") or "") != "pass":
            report["overall_status"] = "fail"
        if not bool(gate_report_stage.get("enablement_allowed")):
            report["overall_status"] = "fail"
        if not bool(drain_stage.get("drained") is True):
            report["overall_status"] = "fail"
        if execute_enable and bool(enable_stage.get("enabled_value_after") is not True):
            report["overall_status"] = "fail"

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if as_json:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self._print_human_report(report=report, report_path=report_path)

        if strict and str(report.get("overall_status") or "") != "pass":
            raise CommandError(
                "Pool master-data sync cutover check failed: "
                f"overall_status={report.get('overall_status')} "
                f"gate_report={gate_report_stage.get('overall_status')} "
                f"drained={drain_stage.get('drained')} "
                f"enable_blockers={enable_blockers}."
            )

    def _resolve_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (REPO_ROOT / candidate).resolve()
        return candidate

    def _read_sync_enabled_setting(self) -> dict[str, Any]:
        setting = RuntimeSetting.objects.filter(key=SYNC_ENABLED_KEY).first()
        if setting is None:
            return {
                "exists": False,
                "value": None,
                "updated_at_utc": None,
            }
        return {
            "exists": True,
            "value": bool(setting.value) if isinstance(setting.value, bool) else setting.value,
            "updated_at_utc": _to_rfc3339_utc(setting.updated_at),
        }

    def _freeze_stage(self, *, apply_changes: bool) -> dict[str, Any]:
        before = self._read_sync_enabled_setting()
        applied = False
        if apply_changes:
            RuntimeSetting.objects.update_or_create(
                key=SYNC_ENABLED_KEY,
                defaults={"value": False},
            )
            applied = True
        after = self._read_sync_enabled_setting()
        return {
            "applied": applied,
            "target_value": False,
            "before": before,
            "after": after,
        }

    def _enable_stage(self, *, apply_changes: bool) -> dict[str, Any]:
        before = self._read_sync_enabled_setting()
        applied = False
        if apply_changes:
            RuntimeSetting.objects.update_or_create(
                key=SYNC_ENABLED_KEY,
                defaults={"value": True},
            )
            applied = True
        after = self._read_sync_enabled_setting()
        return {
            "applied": applied,
            "target_value": True,
            "before": before,
            "after": after,
            "enabled_value_after": bool(after.get("value")) if after.get("exists") else False,
        }

    def _collect_drain_stage(self) -> dict[str, Any]:
        pending_outbox_count = PoolMasterDataSyncOutbox.objects.filter(
            status__in=[
                PoolMasterDataSyncOutboxStatus.PENDING,
                PoolMasterDataSyncOutboxStatus.FAILED,
            ]
        ).count()
        active_jobs_count = PoolMasterDataSyncJob.objects.filter(
            status__in=[
                PoolMasterDataSyncJobStatus.PENDING,
                PoolMasterDataSyncJobStatus.RUNNING,
            ]
        ).count()
        active_conflicts_count = PoolMasterDataSyncConflict.objects.filter(
            status__in=[
                PoolMasterDataSyncConflictStatus.PENDING,
                PoolMasterDataSyncConflictStatus.RETRYING,
            ]
        ).count()

        workflow_pending_rows = WorkflowEnqueueOutbox.objects.filter(
            status=WorkflowEnqueueOutbox.STATUS_PENDING
        ).values("message_payload")
        workflow_pending_total = 0
        workflow_pending_sync = 0
        for row in workflow_pending_rows:
            workflow_pending_total += 1
            payload = row.get("message_payload")
            if not isinstance(payload, dict):
                continue
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            role = str(metadata.get("role") or "").strip().lower()
            if role in SYNC_ROLES:
                workflow_pending_sync += 1

        drained = (
            pending_outbox_count == 0
            and workflow_pending_sync == 0
            and active_jobs_count == 0
            and active_conflicts_count == 0
        )
        return {
            "captured_at_utc": _to_rfc3339_utc(timezone.now()),
            "pending_sync_outbox_count": int(pending_outbox_count),
            "pending_workflow_enqueue_outbox_total": int(workflow_pending_total),
            "pending_workflow_enqueue_outbox_sync": int(workflow_pending_sync),
            "active_sync_jobs_count": int(active_jobs_count),
            "active_sync_conflicts_count": int(active_conflicts_count),
            "drained": bool(drained),
        }

    def _capture_watermark_stage(self) -> dict[str, Any]:
        outbox_max_id = (
            PoolMasterDataSyncOutbox.objects.order_by("-id").values_list("id", flat=True).first()
        )
        outbox_latest_updated_at = (
            PoolMasterDataSyncOutbox.objects.aggregate(latest_updated_at=Max("updated_at")).get("latest_updated_at")
        )
        checkpoint_aggr = PoolMasterDataSyncCheckpoint.objects.aggregate(
            latest_applied_at=Max("last_applied_at"),
            latest_updated_at=Max("updated_at"),
        )
        workflow_outbox_aggr = WorkflowEnqueueOutbox.objects.aggregate(
            max_id=Max("id"),
            latest_updated_at=Max("updated_at"),
        )
        jobs_max_id = PoolMasterDataSyncJob.objects.order_by("-id").values_list("id", flat=True).first()
        jobs_latest_updated_at = (
            PoolMasterDataSyncJob.objects.aggregate(latest_updated_at=Max("updated_at")).get("latest_updated_at")
        )
        return {
            "captured_at_utc": _to_rfc3339_utc(timezone.now()),
            "pool_master_data_sync_outbox": {
                "max_id": str(outbox_max_id) if outbox_max_id is not None else None,
                "latest_updated_at_utc": _to_rfc3339_utc(outbox_latest_updated_at),
            },
            "pool_master_data_sync_checkpoint": {
                "latest_applied_at_utc": _to_rfc3339_utc(checkpoint_aggr.get("latest_applied_at")),
                "latest_updated_at_utc": _to_rfc3339_utc(checkpoint_aggr.get("latest_updated_at")),
            },
            "workflow_enqueue_outbox": {
                "max_id": workflow_outbox_aggr.get("max_id"),
                "latest_updated_at_utc": _to_rfc3339_utc(workflow_outbox_aggr.get("latest_updated_at")),
            },
            "pool_master_data_sync_job": {
                "max_id": str(jobs_max_id) if jobs_max_id is not None else None,
                "latest_updated_at_utc": _to_rfc3339_utc(jobs_latest_updated_at),
            },
        }

    def _load_gate_report_stage(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {
                "path": str(path),
                "exists": False,
                "schema_version": "",
                "overall_status": "missing",
                "schema_valid": False,
                "schema_errors": ["gate_report file is missing"],
                "orr_status": "missing",
                "orr_missing_roles": [],
                "enablement_allowed": False,
                "blocking_reasons": ["GATE_REPORT_MISSING"],
            }
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                "path": str(path),
                "exists": True,
                "schema_version": "",
                "overall_status": "invalid",
                "schema_valid": False,
                "schema_errors": ["gate_report json decode error"],
                "orr_status": "missing",
                "orr_missing_roles": [],
                "enablement_allowed": False,
                "blocking_reasons": ["GATE_REPORT_INVALID_JSON"],
            }
        if not isinstance(payload, dict):
            return {
                "path": str(path),
                "exists": True,
                "schema_version": "",
                "overall_status": "invalid",
                "schema_valid": False,
                "schema_errors": ["gate_report payload must be object"],
                "orr_status": "missing",
                "orr_missing_roles": [],
                "enablement_allowed": False,
                "blocking_reasons": ["GATE_REPORT_INVALID_PAYLOAD"],
            }

        schema_errors = validate_readiness_gate_report_shape(payload)
        schema_version = str(payload.get("schema_version") or "")
        overall_status = str(payload.get("overall_status") or "missing")
        orr_signoff = payload.get("orr_signoff")
        orr_payload = orr_signoff if isinstance(orr_signoff, dict) else {}
        orr_status = str(orr_payload.get("status") or "missing")
        orr_missing_roles_raw = orr_payload.get("missing_roles")
        orr_missing_roles = (
            [str(role) for role in orr_missing_roles_raw]
            if isinstance(orr_missing_roles_raw, list)
            else []
        )

        blocking_reasons: list[str] = []
        if schema_version != READINESS_GATE_SCHEMA_VERSION:
            blocking_reasons.append("GATE_REPORT_SCHEMA_VERSION_MISMATCH")
        if schema_errors:
            blocking_reasons.append("GATE_REPORT_SCHEMA_INVALID")
        if overall_status != "pass":
            blocking_reasons.append("GATE_REPORT_NOT_PASS")
        if orr_status != "complete":
            blocking_reasons.append("GATE_REPORT_ORR_INCOMPLETE")

        return {
            "path": str(path),
            "exists": True,
            "schema_version": schema_version,
            "overall_status": overall_status,
            "schema_valid": not schema_errors,
            "schema_errors": list(schema_errors),
            "orr_status": orr_status,
            "orr_missing_roles": orr_missing_roles,
            "enablement_allowed": len(blocking_reasons) == 0,
            "blocking_reasons": blocking_reasons,
        }

    def _collect_enablement_blockers(
        self,
        *,
        gate_report_stage: dict[str, Any],
        drain_stage: dict[str, Any],
    ) -> list[str]:
        blockers: list[str] = []
        gate_blockers = gate_report_stage.get("blocking_reasons")
        if isinstance(gate_blockers, list):
            blockers.extend(str(item) for item in gate_blockers if str(item).strip())
        if not bool(drain_stage.get("drained") is True):
            blockers.append("CUTOVER_DRAIN_NOT_CLEAN")
        deduplicated: list[str] = []
        for code in blockers:
            if code not in deduplicated:
                deduplicated.append(code)
        return deduplicated

    def _print_human_report(self, *, report: dict[str, Any], report_path: Path) -> None:
        self.stdout.write("pool master-data sync cutover report")
        self.stdout.write(f"schema_version: {report.get('schema_version')}")
        self.stdout.write(f"generated_at_utc: {report.get('generated_at_utc')}")
        self.stdout.write(f"execution_mode: {report.get('execution_mode')}")
        self.stdout.write(f"overall_status: {report.get('overall_status')}")
        self.stdout.write(f"report_path: {report_path}")

        stages = report.get("stages") if isinstance(report.get("stages"), dict) else {}
        drain_stage = stages.get("drain") if isinstance(stages.get("drain"), dict) else {}
        gate_stage = stages.get("gate_report") if isinstance(stages.get("gate_report"), dict) else {}
        self.stdout.write(f"drain.drained: {drain_stage.get('drained')}")
        self.stdout.write(f"gate_report.overall_status: {gate_stage.get('overall_status')}")
