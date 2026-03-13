from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from django.utils import timezone

from apps.databases.models import Database
from apps.intercompany_pools.business_configuration_profile import (
    get_business_configuration_profile,
    persist_business_configuration_profile,
)
from apps.operations.driver_catalog_effective import (
    get_effective_driver_catalog,
    resolve_driver_catalog_versions,
)
from apps.operations.ibcmd_catalog_v2 import build_base_catalog_from_its
from apps.operations.ibcmd_cli_builder import (
    build_ibcmd_cli_argv,
    build_ibcmd_connection_args,
)
from apps.operations.models import BatchOperation, Task
from apps.operations.services.operations_service import OperationsService


BUSINESS_CONFIGURATION_SNAPSHOT_KIND = "business_configuration_profile"
BUSINESS_CONFIGURATION_COMMAND_GENERATION_ID = "infobase.config.generation-id"
BUSINESS_CONFIGURATION_COMMAND_EXPORT_OBJECTS = "infobase.config.export.objects"

BUSINESS_CONFIGURATION_JOB_KIND_GENERATION_PROBE = "generation_probe"
BUSINESS_CONFIGURATION_JOB_KIND_VERIFICATION = "verification"

BUSINESS_CONFIGURATION_GENERATION_PROBE_INTERVAL = timedelta(hours=24)

_ACTIVE_BATCH_OPERATION_STATUSES = (
    BatchOperation.STATUS_PENDING,
    BatchOperation.STATUS_QUEUED,
    BatchOperation.STATUS_PROCESSING,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CHECKED_IN_IBCMD_ITS_PATH = _REPO_ROOT / "generated" / "its" / "ibcmd.json"


def ensure_business_configuration_profile_runtime(*, database: Database) -> dict[str, Any] | None:
    profile = get_business_configuration_profile(database=database)
    if profile is None:
        enqueue_business_configuration_verification(
            database=database,
            reason="profile_missing",
        )
        return None

    verification_status = str(profile.get("verification_status") or "").strip()
    if verification_status in {"migrated_legacy", "reverify_required", "verification_failed"}:
        enqueue_business_configuration_verification(
            database=database,
            reason=verification_status or "verification_required",
        )

    if _should_enqueue_generation_probe(profile=profile):
        enqueue_business_configuration_generation_probe(
            database=database,
            reason="scheduled_generation_probe",
        )

    return get_business_configuration_profile(database=database)


def enqueue_business_configuration_generation_probe(
    *,
    database: Database,
    reason: str,
) -> BatchOperation | None:
    existing = _find_active_operation(
        database=database,
        job_kind=BUSINESS_CONFIGURATION_JOB_KIND_GENERATION_PROBE,
    )
    if existing is not None:
        return existing

    operation = _enqueue_business_configuration_operation(
        database=database,
        command_id=BUSINESS_CONFIGURATION_COMMAND_GENERATION_ID,
        job_kind=BUSINESS_CONFIGURATION_JOB_KIND_GENERATION_PROBE,
        reason=reason,
        params={},
    )
    profile = get_business_configuration_profile(database=database)
    if operation is not None and profile is not None:
        updated_profile = dict(profile)
        updated_profile["generation_probe_operation_id"] = str(operation.id)
        updated_profile["generation_probe_requested_at"] = timezone.now().isoformat()
        persist_business_configuration_profile(database=database, profile=updated_profile)
    return operation


def find_active_business_configuration_operation(
    *,
    database: Database,
    job_kind: str,
) -> BatchOperation | None:
    return _find_active_operation(database=database, job_kind=job_kind)


def enqueue_business_configuration_verification(
    *,
    database: Database,
    reason: str,
    triggered_by_operation_id: str | None = None,
) -> BatchOperation | None:
    existing = _find_active_operation(
        database=database,
        job_kind=BUSINESS_CONFIGURATION_JOB_KIND_VERIFICATION,
    )
    if existing is not None:
        return existing

    artifact_key = (
        f"business-configuration-profile/{str(database.id)}/"
        f"{uuid4().hex}/Configuration.zip"
    )
    metadata = {}
    if triggered_by_operation_id:
        metadata["triggered_by_operation_id"] = str(triggered_by_operation_id)
    operation = _enqueue_business_configuration_operation(
        database=database,
        command_id=BUSINESS_CONFIGURATION_COMMAND_EXPORT_OBJECTS,
        job_kind=BUSINESS_CONFIGURATION_JOB_KIND_VERIFICATION,
        reason=reason,
        params={
            "arg1": "Configuration",
            "archive": True,
            "out": artifact_key,
        },
        metadata=metadata,
    )
    profile = get_business_configuration_profile(database=database)
    if operation is not None and profile is not None:
        updated_profile = dict(profile)
        updated_profile["verification_operation_id"] = str(operation.id)
        persist_business_configuration_profile(database=database, profile=updated_profile)
    return operation


def _enqueue_business_configuration_operation(
    *,
    database: Database,
    command_id: str,
    job_kind: str,
    reason: str,
    params: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> BatchOperation | None:
    command, catalog, command_catalog_source = _resolve_ibcmd_command(command_id=command_id)
    if command is None or catalog is None:
        return None
    if not _has_executable_database_profile_connection(database=database):
        return None

    pre_args = build_ibcmd_connection_args(
        driver_schema=catalog.get("driver_schema") if isinstance(catalog, dict) else None,
        connection={},
    )
    argv, argv_masked = build_ibcmd_cli_argv(
        command=command,
        params=params,
        additional_args=[],
        pre_args=pre_args,
    )

    operation_id = str(uuid4())
    payload = {
        "data": {
            "command_id": command_id,
            "mode": "guided",
            "argv": argv,
            "argv_masked": argv_masked,
            "stdin": "",
            "connection": {},
            "connection_source": "database_profile",
            "ib_auth": {"strategy": "service"},
            "dbms_auth": {"strategy": "service"},
        },
        "filters": {},
        "options": {},
    }
    batch_operation = BatchOperation.objects.create(
        id=operation_id,
        name=f"business_configuration_profile {job_kind}",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="Infobase",
        status=BatchOperation.STATUS_PENDING,
        payload=payload,
        config={
            "batch_size": 1,
            "timeout_seconds": 900,
            "retry_count": 1,
            "priority": "normal",
        },
        total_tasks=1,
        created_by="system",
        metadata={
            "tags": ["ibcmd", "ibcmd_cli", command_id, "business_configuration_profile"],
            "command_id": command_id,
            "mode": "guided",
            "snapshot_kinds": [BUSINESS_CONFIGURATION_SNAPSHOT_KIND],
            "snapshot_source": f"business_configuration_profile.{job_kind}",
            "command_catalog_source": command_catalog_source,
            "business_configuration_job_kind": job_kind,
            "business_configuration_reason": reason,
            **(metadata or {}),
        },
    )
    batch_operation.target_databases.set([database])
    Task.objects.create(
        id=str(uuid4()),
        batch_operation=batch_operation,
        database=database,
        status=Task.STATUS_PENDING,
    )

    enqueue_result = OperationsService.enqueue_operation(operation_id)
    if not enqueue_result.success:
        batch_operation.status = BatchOperation.STATUS_FAILED
        batch_operation.metadata = {
            **(batch_operation.metadata or {}),
            "error": getattr(enqueue_result, "error", None) or "enqueue_failed",
            "error_code": getattr(enqueue_result, "error_code", None) or "ENQUEUE_FAILED",
        }
        batch_operation.save(update_fields=["status", "metadata", "updated_at"])
    return batch_operation


def _resolve_ibcmd_command(*, command_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    fallback_catalog = _load_checked_in_ibcmd_catalog()
    versions = resolve_driver_catalog_versions("ibcmd")
    if versions.base_version is None:
        commands_by_id = fallback_catalog.get("commands_by_id") if isinstance(fallback_catalog, dict) else None
        command = commands_by_id.get(command_id) if isinstance(commands_by_id, dict) else None
        if not isinstance(command, dict):
            return None, None, ""
        return command, fallback_catalog, "checked_in_preset"
    effective = get_effective_driver_catalog(
        driver="ibcmd",
        base_version=versions.base_version,
        overrides_version=versions.overrides_version,
    )
    catalog = effective.catalog if isinstance(effective.catalog, dict) else None
    commands_by_id = catalog.get("commands_by_id") if isinstance(catalog, dict) else None
    command = commands_by_id.get(command_id) if isinstance(commands_by_id, dict) else None
    if isinstance(command, dict):
        return command, catalog, "approved_effective"
    fallback_commands = fallback_catalog.get("commands_by_id") if isinstance(fallback_catalog, dict) else None
    fallback_command = fallback_commands.get(command_id) if isinstance(fallback_commands, dict) else None
    if not isinstance(fallback_command, dict):
        return None, catalog, ""
    return fallback_command, fallback_catalog, "checked_in_preset"


def _has_executable_database_profile_connection(*, database: Database) -> bool:
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    profile = _normalize_ibcmd_connection_profile(metadata.get("ibcmd_connection"))
    return not _is_empty_ibcmd_connection_profile(profile)


def _normalize_ibcmd_connection_profile(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    remote_raw = raw.get("remote")
    if remote_raw in (None, ""):
        remote_raw = raw.get("remote_url")
    remote = str(remote_raw).strip() if remote_raw not in (None, "") else ""
    if remote and not remote.lower().startswith("ssh://"):
        remote = ""

    pid_raw = raw.get("pid")
    pid = pid_raw if isinstance(pid_raw, int) and pid_raw > 0 else None

    offline_in = raw.get("offline")
    offline: dict[str, str] | None = None
    if isinstance(offline_in, dict):
        sanitized_offline: dict[str, str] = {}
        for key, value in offline_in.items():
            normalized_key = str(key).strip()
            if not normalized_key:
                continue
            if normalized_key.lower() in {"db_user", "db_pwd", "db_password"}:
                continue
            if value in (None, ""):
                continue
            normalized_value = str(value).strip()
            if not normalized_value:
                continue
            sanitized_offline[normalized_key] = normalized_value
        offline = sanitized_offline or None

    profile: dict[str, Any] = {}
    if remote:
        profile["remote"] = remote
    if pid is not None:
        profile["pid"] = pid
    if offline:
        profile["offline"] = offline
    return profile


def _is_empty_ibcmd_connection_profile(profile: dict[str, Any] | None) -> bool:
    if not isinstance(profile, dict) or not profile:
        return True

    remote = str(profile.get("remote") or "").strip()
    if remote:
        return False

    pid = profile.get("pid")
    if isinstance(pid, int) and pid > 0:
        return False

    offline = profile.get("offline")
    if isinstance(offline, dict) and len(offline) > 0:
        return False

    return True


@lru_cache(maxsize=1)
def _load_checked_in_ibcmd_catalog() -> dict[str, Any] | None:
    try:
        payload = json.loads(_CHECKED_IN_IBCMD_ITS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    catalog = build_base_catalog_from_its(payload)
    return catalog if isinstance(catalog, dict) else None


def _find_active_operation(
    *,
    database: Database,
    job_kind: str,
) -> BatchOperation | None:
    queryset = (
        BatchOperation.objects.filter(
            operation_type=BatchOperation.TYPE_IBCMD_CLI,
            status__in=_ACTIVE_BATCH_OPERATION_STATUSES,
            target_databases=database,
        )
        .order_by("-created_at")
    )
    for operation in queryset:
        metadata = operation.metadata if isinstance(operation.metadata, dict) else {}
        if (
            str(metadata.get("business_configuration_job_kind") or "").strip() == job_kind
            and BUSINESS_CONFIGURATION_SNAPSHOT_KIND in (metadata.get("snapshot_kinds") or [])
        ):
            return operation
    return None


def _should_enqueue_generation_probe(*, profile: dict[str, Any]) -> bool:
    verification_status = str(profile.get("verification_status") or "").strip()
    if verification_status in {"verification_pending", "migrated_legacy", "reverify_required"}:
        return False

    requested_at = _parse_profile_datetime(profile.get("generation_probe_requested_at"))
    checked_at = _parse_profile_datetime(profile.get("generation_probe_checked_at"))
    reference = requested_at or checked_at
    if reference is None:
        return True
    return timezone.now() - reference >= BUSINESS_CONFIGURATION_GENERATION_PROBE_INTERVAL


def _parse_profile_datetime(raw: object) -> datetime | None:
    token = str(raw or "").strip()
    if not token:
        return None
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, UTC)
    return parsed
