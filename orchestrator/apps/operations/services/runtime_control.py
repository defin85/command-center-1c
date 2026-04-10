"""Runtime control plane services for allowlisted local runtimes."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.intercompany_pools.factual_scheduler_runtime import (
    trigger_pool_factual_active_sync_window,
    trigger_pool_factual_closed_quarter_reconcile_window,
)
from apps.operations.models import RuntimeActionRun, SchedulerJobRun
from apps.runtime_settings.models import RuntimeSetting
from apps.runtime_settings.registry import RUNTIME_SETTINGS

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ORCHESTRATOR_DIR = PROJECT_ROOT / "orchestrator"
DEBUG_DIR = PROJECT_ROOT / "debug"
LOGS_DIR = PROJECT_ROOT / "logs"
DEFAULT_PROVIDER_KEY = "local_scripts"
DEFAULT_RUNTIME_HOST = "localhost"
MAX_EXCERPT_CHARS = 4000
MAX_LOG_LINES = 120
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
AUTHORIZATION_ASSIGNMENT_RE = re.compile(r"(?im)\b(authorization)\b(\s*[:=]\s*)([^\r\n]+)")
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?im)\b(password|passwd|secret|token|authorization)\b(\s*[:=]\s*)([^\s\"']+)"
)
URL_CREDENTIALS_RE = re.compile(r"(?i)(://[^:\s/]+:)([^@\s/]+)(@)")

RUNTIME_SCHEDULER_ENABLED_KEY = "runtime.scheduler.enabled"
POOL_FACTUAL_ACTIVE_SYNC_ENABLED_KEY = "runtime.scheduler.job.pool_factual_active_sync.enabled"
POOL_FACTUAL_ACTIVE_SYNC_SCHEDULE_KEY = "runtime.scheduler.job.pool_factual_active_sync.schedule"
POOL_FACTUAL_RECONCILE_ENABLED_KEY = "runtime.scheduler.job.pool_factual_closed_quarter_reconcile.enabled"
POOL_FACTUAL_RECONCILE_SCHEDULE_KEY = "runtime.scheduler.job.pool_factual_closed_quarter_reconcile.schedule"
RUNTIME_CONTROLLED_SCHEDULER_RUNTIME = "worker-workflows"

ALLOWLISTED_RUNTIME_ACTIONS: dict[str, tuple[str, ...]] = {
    "orchestrator": (
        RuntimeActionRun.ACTION_PROBE,
        RuntimeActionRun.ACTION_RESTART,
        RuntimeActionRun.ACTION_TAIL_LOGS,
    ),
    "event-subscriber": (
        RuntimeActionRun.ACTION_PROBE,
        RuntimeActionRun.ACTION_RESTART,
        RuntimeActionRun.ACTION_TAIL_LOGS,
    ),
    "api-gateway": (
        RuntimeActionRun.ACTION_PROBE,
        RuntimeActionRun.ACTION_RESTART,
        RuntimeActionRun.ACTION_TAIL_LOGS,
    ),
    "worker": (
        RuntimeActionRun.ACTION_PROBE,
        RuntimeActionRun.ACTION_RESTART,
        RuntimeActionRun.ACTION_TAIL_LOGS,
    ),
    "worker-workflows": (
        RuntimeActionRun.ACTION_PROBE,
        RuntimeActionRun.ACTION_RESTART,
        RuntimeActionRun.ACTION_TAIL_LOGS,
        RuntimeActionRun.ACTION_TRIGGER_NOW,
    ),
    "frontend": (
        RuntimeActionRun.ACTION_PROBE,
        RuntimeActionRun.ACTION_RESTART,
        RuntimeActionRun.ACTION_TAIL_LOGS,
    ),
}

CONTROLLED_SCHEDULER_JOBS: dict[str, dict[str, Any]] = {
    "pool_factual_active_sync": {
        "runtime_name": RUNTIME_CONTROLLED_SCHEDULER_RUNTIME,
        "display_name": "Pool factual active sync",
        "description": "Scans active pools and refreshes factual checkpoint windows for the current quarter.",
        "enabled_key": POOL_FACTUAL_ACTIVE_SYNC_ENABLED_KEY,
        "schedule_key": POOL_FACTUAL_ACTIVE_SYNC_SCHEDULE_KEY,
        "runner": trigger_pool_factual_active_sync_window,
    },
    "pool_factual_closed_quarter_reconcile": {
        "runtime_name": RUNTIME_CONTROLLED_SCHEDULER_RUNTIME,
        "display_name": "Pool factual closed-quarter reconcile",
        "description": "Creates and advances reconcile checkpoints for closed-quarter factual scopes.",
        "enabled_key": POOL_FACTUAL_RECONCILE_ENABLED_KEY,
        "schedule_key": POOL_FACTUAL_RECONCILE_SCHEDULE_KEY,
        "runner": trigger_pool_factual_closed_quarter_reconcile_window,
    },
}


def build_runtime_id(runtime_name: str) -> str:
    return f"local:{DEFAULT_RUNTIME_HOST}:{runtime_name}"


def parse_runtime_id(runtime_id: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in str(runtime_id or "").split(":", 2)]
    if len(parts) != 3 or not all(parts):
        raise ValueError("Invalid runtime_id")
    return parts[0], parts[1], parts[2]


def _validate_runtime_setting_value(key: str, value: object) -> object:
    definition = RUNTIME_SETTINGS[key]
    if definition.value_type == "bool":
        if not isinstance(value, bool):
            raise ValueError("value must be boolean")
        return value
    if definition.value_type == "string":
        if not isinstance(value, str):
            raise ValueError("value must be string")
        return value
    if definition.value_type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("value must be integer")
        if definition.min_value is not None and value < definition.min_value:
            raise ValueError("value below minimum")
        if definition.max_value is not None and value > definition.max_value:
            raise ValueError("value above maximum")
        return value
    return value


def _redact_sensitive_text(value: str) -> str:
    sanitized = ANSI_ESCAPE_RE.sub("", value or "")
    sanitized = AUTHORIZATION_ASSIGNMENT_RE.sub(r"\1\2[REDACTED]", sanitized)
    sanitized = SENSITIVE_ASSIGNMENT_RE.sub(r"\1\2[REDACTED]", sanitized)
    sanitized = URL_CREDENTIALS_RE.sub(r"\1[REDACTED]\3", sanitized)
    return sanitized


def _bounded_excerpt(value: str, *, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    sanitized = _redact_sensitive_text(value).strip()
    if len(sanitized) <= max_chars:
        return sanitized
    return f"...[truncated]...\n{sanitized[-max_chars:]}"


def _run_command(args: list[str], *, timeout: int = 120, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=os.environ.copy(),
    )


def _load_runtime_inventory() -> list[dict[str, Any]]:
    completed = _run_command([str(DEBUG_DIR / "runtime-inventory.sh"), "--json"], timeout=15)
    if completed.returncode != 0:
        raise RuntimeError(_bounded_excerpt(completed.stderr or completed.stdout or "Failed to load runtime inventory"))
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid runtime inventory payload: {exc}") from exc
    if not isinstance(payload, list):
        raise RuntimeError("Runtime inventory payload must be a list")
    return [item for item in payload if isinstance(item, dict)]


def _parse_probe_output(runtime_name: str, output: str) -> dict[str, Any]:
    line = ""
    for candidate in (output or "").splitlines():
        if candidate.strip().startswith(runtime_name):
            line = candidate.strip()
            break
    proc_match = re.search(r"proc=(?P<proc>\S+)", line)
    http_match = re.search(r"http=(?P<http>\S+)", line)
    process_status = proc_match.group("proc") if proc_match else "unknown"
    http_status = http_match.group("http") if http_match else "unknown"

    if process_status.startswith("up") and (http_status.startswith("up") or http_status == "n/a"):
        status = "online"
    elif process_status.startswith("up"):
        status = "degraded"
    else:
        status = "offline"

    return {
        "status": status,
        "process_status": process_status,
        "http_status": http_status,
        "raw_probe": _bounded_excerpt(line or output),
    }


def probe_runtime(runtime_name: str) -> dict[str, Any]:
    completed = _run_command([str(DEBUG_DIR / "probe.sh"), runtime_name], timeout=15)
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    parsed = _parse_probe_output(runtime_name, output)
    parsed["command_status"] = "success" if completed.returncode == 0 else "failed"
    return parsed


def get_runtime_logs_excerpt(runtime_name: str, *, max_lines: int = MAX_LOG_LINES) -> dict[str, Any]:
    log_path = LOGS_DIR / f"{runtime_name}.log"
    if not log_path.exists():
        return {
            "available": False,
            "excerpt": "",
            "path": str(log_path),
        }

    lines: deque[str] = deque(maxlen=max_lines)
    with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            lines.append(line.rstrip("\n"))

    excerpt = _bounded_excerpt("\n".join(lines))
    return {
        "available": True,
        "excerpt": excerpt,
        "path": str(log_path),
        "updated_at": datetime.fromtimestamp(log_path.stat().st_mtime, tz=UTC).isoformat(),
    }


def _runtime_inventory_by_id() -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for item in _load_runtime_inventory():
        runtime_name = str(item.get("runtime") or "").strip()
        if not runtime_name:
            continue
        mapping[build_runtime_id(runtime_name)] = item
    return mapping


def get_runtime_inventory_item(runtime_id: str) -> dict[str, Any]:
    mapping = _runtime_inventory_by_id()
    item = mapping.get(runtime_id)
    if item is None:
        raise KeyError(f"Unknown runtime_id: {runtime_id}")
    return item


def _latest_scheduler_run(job_name: str) -> SchedulerJobRun | None:
    return SchedulerJobRun.objects.filter(job_name=job_name).order_by("-started_at").first()


def _build_scheduler_job_state(job_name: str) -> dict[str, Any]:
    job_meta = CONTROLLED_SCHEDULER_JOBS[job_name]
    enabled_key = job_meta["enabled_key"]
    schedule_key = job_meta["schedule_key"]
    enabled = RuntimeSetting.objects.filter(key=enabled_key).values_list("value", flat=True).first()
    schedule = RuntimeSetting.objects.filter(key=schedule_key).values_list("value", flat=True).first()
    latest_run = _latest_scheduler_run(job_name)
    return {
        "job_name": job_name,
        "runtime_id": build_runtime_id(job_meta["runtime_name"]),
        "runtime_name": job_meta["runtime_name"],
        "display_name": job_meta["display_name"],
        "description": job_meta["description"],
        "enabled": bool(RUNTIME_SETTINGS[enabled_key].default if enabled is None else enabled),
        "schedule": str(RUNTIME_SETTINGS[schedule_key].default if schedule in {None, ""} else schedule),
        "schedule_apply_mode": "controlled_restart",
        "enablement_apply_mode": "live",
        "latest_run_id": latest_run.id if latest_run else None,
        "latest_run_status": latest_run.status if latest_run else None,
        "latest_run_started_at": latest_run.started_at.isoformat() if latest_run else None,
    }


def get_scheduler_desired_state() -> dict[str, Any]:
    scheduler_enabled = RuntimeSetting.objects.filter(key=RUNTIME_SCHEDULER_ENABLED_KEY).values_list("value", flat=True).first()
    return {
        "scheduler_enabled": bool(
            RUNTIME_SETTINGS[RUNTIME_SCHEDULER_ENABLED_KEY].default if scheduler_enabled is None else scheduler_enabled
        ),
        "jobs": [_build_scheduler_job_state(job_name) for job_name in CONTROLLED_SCHEDULER_JOBS],
    }


def list_scheduler_jobs() -> list[dict[str, Any]]:
    return get_scheduler_desired_state()["jobs"]


def list_runtime_instances() -> list[dict[str, Any]]:
    runtimes: list[dict[str, Any]] = []
    for runtime_id, item in sorted(_runtime_inventory_by_id().items(), key=lambda pair: pair[1].get("runtime", "")):
        runtime_name = str(item.get("runtime") or "")
        probe = probe_runtime(runtime_name)
        supported_actions = list(ALLOWLISTED_RUNTIME_ACTIONS.get(runtime_name, ()))
        runtime_entry = {
            "runtime_id": runtime_id,
            "runtime_name": runtime_name,
            "display_name": runtime_name,
            "provider": {
                "key": DEFAULT_PROVIDER_KEY,
                "host": DEFAULT_RUNTIME_HOST,
            },
            "observed_state": probe,
            "type": item.get("type"),
            "stack": item.get("stack"),
            "entrypoint": item.get("entrypoint"),
            "health": item.get("health"),
            "supported_actions": supported_actions,
            "logs_available": (LOGS_DIR / f"{runtime_name}.log").exists(),
            "scheduler_supported": runtime_name == RUNTIME_CONTROLLED_SCHEDULER_RUNTIME,
        }
        if runtime_name == RUNTIME_CONTROLLED_SCHEDULER_RUNTIME:
            runtime_entry["desired_state"] = get_scheduler_desired_state()
        runtimes.append(runtime_entry)
    return runtimes


def get_runtime_detail(runtime_id: str) -> dict[str, Any]:
    for item in list_runtime_instances():
        if item["runtime_id"] == runtime_id:
            item["logs_excerpt"] = get_runtime_logs_excerpt(item["runtime_name"])
            item["recent_actions"] = list_runtime_action_runs(runtime_id, limit=10)
            return item
    raise KeyError(f"Unknown runtime_id: {runtime_id}")


def list_runtime_action_runs(runtime_id: str, *, limit: int = 25) -> list[RuntimeActionRun]:
    return list(
        RuntimeActionRun.objects.select_related("requested_by", "scheduler_job_run")
        .filter(runtime_id=runtime_id)
        .order_by("-requested_at")[:limit]
    )


def get_runtime_action_run(action_id: str) -> RuntimeActionRun:
    return RuntimeActionRun.objects.select_related("requested_by", "scheduler_job_run").get(id=action_id)


def _validate_action_request(*, runtime_id: str, action_type: str, reason: str, target_job_name: str) -> dict[str, Any]:
    inventory_item = get_runtime_inventory_item(runtime_id)
    runtime_name = str(inventory_item.get("runtime") or "")
    supported_actions = ALLOWLISTED_RUNTIME_ACTIONS.get(runtime_name, ())
    if action_type not in supported_actions:
        raise ValueError("Unsupported action for runtime")
    if action_type == RuntimeActionRun.ACTION_RESTART and not reason.strip():
        raise ValueError("Reason is required for restart")
    if action_type == RuntimeActionRun.ACTION_TRIGGER_NOW:
        job_meta = CONTROLLED_SCHEDULER_JOBS.get(target_job_name)
        if job_meta is None or job_meta["runtime_name"] != runtime_name:
            raise ValueError("Unsupported scheduler job")
    return inventory_item


def dispatch_runtime_action_run(action_run: RuntimeActionRun) -> None:
    python_path = ORCHESTRATOR_DIR / "venv" / "bin" / "python"
    executable = str(python_path if python_path.exists() else Path(sys.executable))
    subprocess.Popen(
        [
            executable,
            "manage.py",
            "execute_runtime_control_action",
            "--action-run-id",
            str(action_run.id),
        ],
        cwd=str(ORCHESTRATOR_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


def create_runtime_action_run(
    *,
    runtime_id: str,
    action_type: str,
    actor,
    reason: str = "",
    target_job_name: str = "",
    request_payload: dict[str, Any] | None = None,
) -> RuntimeActionRun:
    inventory_item = _validate_action_request(
        runtime_id=runtime_id,
        action_type=action_type,
        reason=reason,
        target_job_name=target_job_name,
    )
    runtime_name = str(inventory_item.get("runtime") or "")
    action_run = RuntimeActionRun.objects.create(
        provider=DEFAULT_PROVIDER_KEY,
        runtime_id=runtime_id,
        runtime_name=runtime_name,
        action_type=action_type,
        target_job_name=target_job_name,
        requested_by=actor if getattr(actor, "is_authenticated", False) else None,
        requested_by_username=getattr(actor, "username", "") or "",
        reason=reason or "",
        request_payload=request_payload or {},
    )
    try:
        dispatch_runtime_action_run(action_run)
    except Exception as exc:
        _update_action_run(
            action_run,
            status=RuntimeActionRun.STATUS_FAILED,
            error_message=f"Dispatch failed: {exc}",
            result_excerpt=str(exc),
        )
    return action_run


def _update_action_run(
    action_run: RuntimeActionRun,
    *,
    status: str,
    result_excerpt: str = "",
    result_payload: dict[str, Any] | None = None,
    error_message: str = "",
) -> RuntimeActionRun:
    action_run.status = status
    action_run.result_excerpt = _bounded_excerpt(result_excerpt)
    action_run.result_payload = result_payload or {}
    action_run.error_message = _bounded_excerpt(error_message)
    if status == RuntimeActionRun.STATUS_RUNNING:
        action_run.started_at = timezone.now()
    if status in {RuntimeActionRun.STATUS_SUCCESS, RuntimeActionRun.STATUS_FAILED}:
        action_run.finished_at = timezone.now()
    action_run.save(
        update_fields=[
            "status",
            "result_excerpt",
            "result_payload",
            "error_message",
            "started_at",
            "finished_at",
            "scheduler_job_run",
        ]
    )
    return action_run


def _execute_probe_action(action_run: RuntimeActionRun) -> tuple[str, dict[str, Any]]:
    completed = _run_command([str(DEBUG_DIR / "probe.sh"), action_run.runtime_name], timeout=15)
    combined = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    parsed = _parse_probe_output(action_run.runtime_name, combined)
    parsed["exit_code"] = completed.returncode
    if completed.returncode != 0:
        raise RuntimeError(combined or "Runtime probe failed")
    return combined, parsed


def _execute_restart_action(action_run: RuntimeActionRun) -> tuple[str, dict[str, Any]]:
    completed = _run_command([str(DEBUG_DIR / "restart-runtime.sh"), action_run.runtime_name], timeout=240)
    combined = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    if completed.returncode != 0:
        raise RuntimeError(combined or "Runtime restart failed")
    return combined, {"exit_code": completed.returncode}


def _execute_tail_logs_action(action_run: RuntimeActionRun) -> tuple[str, dict[str, Any]]:
    logs_excerpt = get_runtime_logs_excerpt(action_run.runtime_name)
    if not logs_excerpt["available"]:
        return "", logs_excerpt
    return str(logs_excerpt["excerpt"]), logs_excerpt


def _complete_scheduler_job_run(
    scheduler_run: SchedulerJobRun,
    *,
    status: str,
    result_summary: str = "",
    error_message: str = "",
    items_processed: int = 0,
) -> SchedulerJobRun:
    finished_at = timezone.now()
    scheduler_run.status = status
    scheduler_run.finished_at = finished_at
    scheduler_run.duration_ms = int((finished_at - scheduler_run.started_at).total_seconds() * 1000)
    scheduler_run.result_summary = _bounded_excerpt(result_summary)
    scheduler_run.error_message = _bounded_excerpt(error_message)
    scheduler_run.items_processed = items_processed
    scheduler_run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "result_summary",
            "error_message",
            "items_processed",
        ]
    )
    return scheduler_run


def _execute_trigger_now_action(action_run: RuntimeActionRun) -> tuple[str, dict[str, Any]]:
    job_meta = CONTROLLED_SCHEDULER_JOBS[action_run.target_job_name]
    scheduler_run = SchedulerJobRun.objects.create(
        job_name=action_run.target_job_name,
        worker_instance=f"runtime-control:{action_run.runtime_id}",
        status=SchedulerJobRun.STATUS_RUNNING,
        started_at=timezone.now(),
        job_config={
            "trigger_source": "runtime_control",
            "runtime_action_run_id": str(action_run.id),
        },
    )
    action_run.scheduler_job_run = scheduler_run
    action_run.save(update_fields=["scheduler_job_run"])

    try:
        payload = job_meta["runner"]()
    except Exception as exc:
        _complete_scheduler_job_run(
            scheduler_run,
            status=SchedulerJobRun.STATUS_FAILED,
            error_message=str(exc),
        )
        raise

    items_processed = int(
        payload.get("checkpoints_touched")
        or payload.get("reconcile_checkpoints_touched")
        or payload.get("pools_scanned")
        or 0
    )
    _complete_scheduler_job_run(
        scheduler_run,
        status=SchedulerJobRun.STATUS_SUCCESS,
        result_summary=json.dumps(payload, ensure_ascii=True),
        items_processed=items_processed,
    )
    return json.dumps(payload, ensure_ascii=True, indent=2), {
        "scheduler_job_run_id": scheduler_run.id,
        "job_result": payload,
    }


def execute_runtime_action_run(action_run_id: str) -> RuntimeActionRun:
    with transaction.atomic():
        action_run = RuntimeActionRun.objects.select_for_update().get(id=action_run_id)
        if action_run.status not in {RuntimeActionRun.STATUS_ACCEPTED, RuntimeActionRun.STATUS_RUNNING}:
            return action_run
        _update_action_run(action_run, status=RuntimeActionRun.STATUS_RUNNING)

    try:
        if action_run.action_type == RuntimeActionRun.ACTION_PROBE:
            excerpt, payload = _execute_probe_action(action_run)
        elif action_run.action_type == RuntimeActionRun.ACTION_RESTART:
            excerpt, payload = _execute_restart_action(action_run)
        elif action_run.action_type == RuntimeActionRun.ACTION_TAIL_LOGS:
            excerpt, payload = _execute_tail_logs_action(action_run)
        elif action_run.action_type == RuntimeActionRun.ACTION_TRIGGER_NOW:
            excerpt, payload = _execute_trigger_now_action(action_run)
        else:
            raise RuntimeError(f"Unsupported action type: {action_run.action_type}")
    except Exception as exc:
        _update_action_run(
            action_run,
            status=RuntimeActionRun.STATUS_FAILED,
            error_message=str(exc),
            result_excerpt=str(exc),
        )
        return action_run

    _update_action_run(
        action_run,
        status=RuntimeActionRun.STATUS_SUCCESS,
        result_excerpt=excerpt,
        result_payload=payload,
    )
    return action_run


def update_runtime_desired_state(runtime_id: str, *, scheduler_enabled: bool | None, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    inventory_item = get_runtime_inventory_item(runtime_id)
    runtime_name = str(inventory_item.get("runtime") or "")
    if runtime_name != RUNTIME_CONTROLLED_SCHEDULER_RUNTIME:
        raise ValueError("Desired state is unsupported for this runtime")

    if scheduler_enabled is not None:
        RuntimeSetting.objects.update_or_create(
            key=RUNTIME_SCHEDULER_ENABLED_KEY,
            defaults={"value": _validate_runtime_setting_value(RUNTIME_SCHEDULER_ENABLED_KEY, scheduler_enabled)},
        )

    for job_patch in jobs:
        job_name = str(job_patch.get("job_name") or "").strip()
        job_meta = CONTROLLED_SCHEDULER_JOBS.get(job_name)
        if job_meta is None:
            raise ValueError(f"Unsupported scheduler job: {job_name}")
        if "enabled" in job_patch:
            RuntimeSetting.objects.update_or_create(
                key=job_meta["enabled_key"],
                defaults={"value": _validate_runtime_setting_value(job_meta["enabled_key"], job_patch["enabled"])},
            )
        if "schedule" in job_patch:
            RuntimeSetting.objects.update_or_create(
                key=job_meta["schedule_key"],
                defaults={"value": _validate_runtime_setting_value(job_meta["schedule_key"], job_patch["schedule"])},
            )

    return get_scheduler_desired_state()


def serialize_runtime_action_run(action_run: RuntimeActionRun) -> dict[str, Any]:
    return {
        "id": str(action_run.id),
        "provider": action_run.provider,
        "runtime_id": action_run.runtime_id,
        "runtime_name": action_run.runtime_name,
        "action_type": action_run.action_type,
        "target_job_name": action_run.target_job_name,
        "status": action_run.status,
        "reason": action_run.reason,
        "requested_by_username": action_run.requested_by_username,
        "requested_at": action_run.requested_at.isoformat() if action_run.requested_at else None,
        "started_at": action_run.started_at.isoformat() if action_run.started_at else None,
        "finished_at": action_run.finished_at.isoformat() if action_run.finished_at else None,
        "result_excerpt": action_run.result_excerpt,
        "result_payload": action_run.result_payload,
        "error_message": action_run.error_message,
        "scheduler_job_run_id": action_run.scheduler_job_run_id,
    }


def serialize_runtime_instance(runtime: dict[str, Any]) -> dict[str, Any]:
    return runtime


def get_runtime_action_queryset():
    return RuntimeActionRun.objects.select_related("requested_by", "scheduler_job_run")


def resolve_user(username: str):
    user_model = get_user_model()
    return user_model.objects.get(username=username)
