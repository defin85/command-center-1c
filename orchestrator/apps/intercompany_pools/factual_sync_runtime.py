from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone as dt_timezone
from typing import Any, Iterable

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.databases.models import Database

from .factual_read_boundary import build_default_factual_odata_read_boundary
from .factual_scheduling import build_factual_read_contract
from .factual_source_profile import (
    REQUIRED_FACTUAL_ACCOUNTING_REGISTER,
    REQUIRED_FACTUAL_DOCUMENTS,
    REQUIRED_FACTUAL_INFORMATION_REGISTER,
)
from .master_data_sync_redaction import sanitize_master_data_sync_text
from .models import PoolFactualSyncCheckpoint


logger = logging.getLogger(__name__)


ERROR_CODE_POOL_FACTUAL_SYNC_SCOPE_INVALID = "POOL_FACTUAL_SYNC_SCOPE_INVALID"
ERROR_CODE_POOL_FACTUAL_SYNC_SOURCE_MAINTENANCE = "POOL_FACTUAL_SYNC_SOURCE_MAINTENANCE"
ERROR_CODE_POOL_FACTUAL_SYNC_EXTERNAL_SESSIONS_BLOCKED = "POOL_FACTUAL_SYNC_EXTERNAL_SESSIONS_BLOCKED"
ERROR_CODE_POOL_FACTUAL_SYNC_SOURCE_UNAVAILABLE = "POOL_FACTUAL_SYNC_SOURCE_UNAVAILABLE"
ERROR_CODE_POOL_FACTUAL_SYNC_FAILED = "POOL_FACTUAL_SYNC_FAILED"

SOURCE_STATE_AVAILABLE = "available"
SOURCE_STATE_MAINTENANCE = "maintenance"
SOURCE_STATE_BLOCKED_EXTERNAL_SESSIONS = "blocked_external_sessions"
SOURCE_STATE_UNAVAILABLE = "unavailable"

FACTUAL_SOURCE_PROFILE_SALES_REPORT_V1 = "sales_report_v1"
FACTUAL_SALES_REPORT_ACCOUNTING_FUNCTION = "Turnovers"
FACTUAL_SYNC_FRESHNESS_TARGET_SECONDS = 120


class FactualSyncTransportError(RuntimeError):
    def __init__(self, *, code: str, detail: str) -> None:
        self.code = str(code or "").strip() or ERROR_CODE_POOL_FACTUAL_SYNC_FAILED
        self.detail = str(detail or "").strip() or "factual sync failed"
        super().__init__(f"{self.code}: {self.detail}")


@dataclass(frozen=True)
class FactualSalesReportSyncScope:
    quarter_start: date
    quarter_end: date
    organization_ids: tuple[str, ...]
    account_codes: tuple[str, ...]
    movement_kinds: tuple[str, ...]
    document_entities: tuple[str, ...]
    accounting_register_entity: str
    accounting_register_function: str
    information_register_entity: str
    source_profile: str
    freshness_target_seconds: int
    scope_fingerprint: str

    def as_metadata(self) -> dict[str, Any]:
        return {
            "quarter_start": self.quarter_start.isoformat(),
            "quarter_end": self.quarter_end.isoformat(),
            "organization_ids": list(self.organization_ids),
            "account_codes": list(self.account_codes),
            "movement_kinds": list(self.movement_kinds),
            "document_entities": list(self.document_entities),
            "accounting_register_entity": self.accounting_register_entity,
            "accounting_register_function": self.accounting_register_function,
            "information_register_entity": self.information_register_entity,
            "scope_fingerprint": self.scope_fingerprint,
        }


@dataclass(frozen=True)
class FactualSyncSourceState:
    state: str
    code: str
    detail: str
    window_from: datetime | None = None
    window_to: datetime | None = None

    def as_metadata(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_availability": self.state,
            "source_availability_code": self.code,
            "source_availability_detail": self.detail,
        }
        if self.window_from is not None:
            payload["source_availability_window_from"] = self.window_from.isoformat()
        if self.window_to is not None:
            payload["source_availability_window_to"] = self.window_to.isoformat()
        return payload


def build_factual_sales_report_sync_scope(
    *,
    quarter_start: date,
    quarter_end: date,
    organization_ids: Iterable[str],
    account_codes: Iterable[str],
    movement_kinds: Iterable[str],
) -> FactualSalesReportSyncScope:
    if quarter_end < quarter_start:
        raise ValueError(
            f"{ERROR_CODE_POOL_FACTUAL_SYNC_SCOPE_INVALID}: quarter_end must be on or after quarter_start"
        )

    normalized_org_ids = _normalize_scope_tokens(values=organization_ids, field_name="organization_ids")
    normalized_account_codes = _normalize_scope_tokens(values=account_codes, field_name="account_codes")
    normalized_movement_kinds = _normalize_scope_tokens(values=movement_kinds, field_name="movement_kinds")
    document_entities = tuple(sorted(REQUIRED_FACTUAL_DOCUMENTS))
    fingerprint_payload = {
        "quarter_start": quarter_start.isoformat(),
        "quarter_end": quarter_end.isoformat(),
        "organization_ids": normalized_org_ids,
        "account_codes": normalized_account_codes,
        "movement_kinds": normalized_movement_kinds,
        "document_entities": document_entities,
        "accounting_register_entity": REQUIRED_FACTUAL_ACCOUNTING_REGISTER,
        "accounting_register_function": FACTUAL_SALES_REPORT_ACCOUNTING_FUNCTION,
        "information_register_entity": REQUIRED_FACTUAL_INFORMATION_REGISTER,
        "source_profile": FACTUAL_SOURCE_PROFILE_SALES_REPORT_V1,
        "freshness_target_seconds": FACTUAL_SYNC_FRESHNESS_TARGET_SECONDS,
    }
    scope_fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return FactualSalesReportSyncScope(
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        organization_ids=normalized_org_ids,
        account_codes=normalized_account_codes,
        movement_kinds=normalized_movement_kinds,
        document_entities=document_entities,
        accounting_register_entity=REQUIRED_FACTUAL_ACCOUNTING_REGISTER,
        accounting_register_function=FACTUAL_SALES_REPORT_ACCOUNTING_FUNCTION,
        information_register_entity=REQUIRED_FACTUAL_INFORMATION_REGISTER,
        source_profile=FACTUAL_SOURCE_PROFILE_SALES_REPORT_V1,
        freshness_target_seconds=FACTUAL_SYNC_FRESHNESS_TARGET_SECONDS,
        scope_fingerprint=scope_fingerprint,
    )


def build_factual_sales_report_sync_contract(
    *,
    database: Any,
    quarter_start: date,
    quarter_end: date,
    organization_ids: Iterable[str],
    account_codes: Iterable[str],
    movement_kinds: Iterable[str],
    activity: str = "active",
    now: datetime | None = None,
) -> dict[str, str]:
    scope = build_factual_sales_report_sync_scope(
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        organization_ids=organization_ids,
        account_codes=account_codes,
        movement_kinds=movement_kinds,
    )
    contract = build_factual_read_contract(
        database=database,
        activity=activity,
        now=now,
    )
    read_boundary = build_default_factual_odata_read_boundary()
    return {
        **contract,
        **read_boundary.as_contract(),
        "source_profile": scope.source_profile,
        "quarter_start": scope.quarter_start.isoformat(),
        "quarter_end": scope.quarter_end.isoformat(),
        "organization_ids": ",".join(scope.organization_ids),
        "account_codes": ",".join(scope.account_codes),
        "movement_kinds": ",".join(scope.movement_kinds),
        "document_entities": ",".join(scope.document_entities),
        "accounting_register_entity": scope.accounting_register_entity,
        "accounting_register_function": scope.accounting_register_function,
        "information_register_entity": scope.information_register_entity,
        "freshness_target_seconds": str(scope.freshness_target_seconds),
        "scope_fingerprint": scope.scope_fingerprint,
    }


def resolve_factual_sync_source_state(
    *,
    database: Database,
    now: datetime | None = None,
) -> FactualSyncSourceState:
    current_time = _ensure_aware_datetime(now or timezone.now())
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    denied_message = str(metadata.get("denied_message") or "").strip()

    if str(database.status or "").strip().lower() == Database.STATUS_MAINTENANCE:
        return FactualSyncSourceState(
            state=SOURCE_STATE_MAINTENANCE,
            code=ERROR_CODE_POOL_FACTUAL_SYNC_SOURCE_MAINTENANCE,
            detail=denied_message or "Database is in maintenance mode.",
            window_from=_parse_metadata_datetime(metadata.get("denied_from")),
            window_to=_parse_metadata_datetime(metadata.get("denied_to")),
        )

    window_from = _parse_metadata_datetime(metadata.get("denied_from"))
    window_to = _parse_metadata_datetime(metadata.get("denied_to"))
    sessions_deny = bool(metadata.get("sessions_deny"))
    if sessions_deny and _is_block_window_active(
        now=current_time,
        window_from=window_from,
        window_to=window_to,
    ):
        detail_parts = [denied_message or "External sessions are blocked for this infobase."]
        permission_code = str(metadata.get("permission_code") or "").strip()
        if permission_code:
            detail_parts.append(f"permission_code={permission_code}")
        return FactualSyncSourceState(
            state=SOURCE_STATE_BLOCKED_EXTERNAL_SESSIONS,
            code=ERROR_CODE_POOL_FACTUAL_SYNC_EXTERNAL_SESSIONS_BLOCKED,
            detail=" ".join(part for part in detail_parts if part),
            window_from=window_from,
            window_to=window_to,
        )

    if str(database.status or "").strip().lower() in {Database.STATUS_INACTIVE, Database.STATUS_ERROR}:
        detail = str(metadata.get("last_health_error") or "").strip() or "Database is not available for factual sync."
        return FactualSyncSourceState(
            state=SOURCE_STATE_UNAVAILABLE,
            code=ERROR_CODE_POOL_FACTUAL_SYNC_SOURCE_UNAVAILABLE,
            detail=detail,
        )

    return FactualSyncSourceState(
        state=SOURCE_STATE_AVAILABLE,
        code="",
        detail="",
    )


def mark_factual_sync_checkpoint_success(
    *,
    checkpoint: PoolFactualSyncCheckpoint,
    scope: FactualSalesReportSyncScope,
    source_state: FactualSyncSourceState,
    source_checkpoint_token: str,
    synced_at: datetime | None = None,
) -> None:
    timestamp = _ensure_aware_datetime(synced_at or timezone.now())
    metadata = dict(checkpoint.metadata or {})
    metadata.update(_build_checkpoint_scope_metadata(scope=scope, source_state=source_state))
    metadata["source_checkpoint_token"] = str(source_checkpoint_token or checkpoint.source_checkpoint_token or "")
    metadata["freshness_target_seconds"] = int(scope.freshness_target_seconds)
    metadata["freshness_state"] = "fresh"
    metadata["freshness_at"] = timestamp.isoformat()
    metadata["last_synced_at"] = timestamp.isoformat()
    metadata.pop("last_error_at", None)
    checkpoint.source_checkpoint_token = str(source_checkpoint_token or checkpoint.source_checkpoint_token or "")
    checkpoint.last_synced_at = timestamp
    checkpoint.last_error_code = ""
    checkpoint.last_error = ""
    checkpoint.metadata = metadata
    checkpoint.save(
        update_fields=[
            "source_checkpoint_token",
            "last_synced_at",
            "last_error_code",
            "last_error",
            "metadata",
            "updated_at",
        ]
    )
    _refresh_factual_rollout_telemetry(timestamp=timestamp)


def mark_factual_sync_checkpoint_error(
    *,
    checkpoint: PoolFactualSyncCheckpoint,
    scope: FactualSalesReportSyncScope,
    source_state: FactualSyncSourceState,
    error: Exception,
    failed_at: datetime | None = None,
) -> None:
    timestamp = _ensure_aware_datetime(failed_at or timezone.now())
    error_code, error_detail = _resolve_factual_sync_error(error=error, source_state=source_state)
    metadata = dict(checkpoint.metadata or {})
    metadata.update(_build_checkpoint_scope_metadata(scope=scope, source_state=source_state))
    metadata["freshness_target_seconds"] = int(scope.freshness_target_seconds)
    metadata["freshness_state"] = "stale"
    metadata["last_error_at"] = timestamp.isoformat()
    checkpoint.last_error_code = error_code
    checkpoint.last_error = sanitize_master_data_sync_text(error_detail)
    checkpoint.metadata = metadata
    checkpoint.save(
        update_fields=[
            "last_error_code",
            "last_error",
            "metadata",
            "updated_at",
        ]
    )
    _refresh_factual_rollout_telemetry(timestamp=timestamp)


def _build_checkpoint_scope_metadata(
    *,
    scope: FactualSalesReportSyncScope,
    source_state: FactualSyncSourceState,
) -> dict[str, Any]:
    payload = dict(source_state.as_metadata())
    payload["source_profile"] = scope.source_profile
    payload["source_scope"] = scope.as_metadata()
    return payload


def _resolve_factual_sync_error(
    *,
    error: Exception,
    source_state: FactualSyncSourceState,
) -> tuple[str, str]:
    if isinstance(error, FactualSyncTransportError):
        return error.code, error.detail
    detail = str(error or "").strip() or "factual sync failed"
    if source_state.code:
        return source_state.code, detail
    return ERROR_CODE_POOL_FACTUAL_SYNC_FAILED, detail


def _refresh_factual_rollout_telemetry(*, timestamp: datetime) -> None:
    try:
        from .factual_observability import record_pool_factual_rollout_telemetry

        record_pool_factual_rollout_telemetry(now=timestamp)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to record factual rollout telemetry: %s", exc)


def _normalize_scope_tokens(*, values: Iterable[str], field_name: str) -> tuple[str, ...]:
    normalized = sorted(
        {
            str(value or "").strip()
            for value in values
            if str(value or "").strip()
        }
    )
    if normalized:
        return tuple(normalized)
    raise ValueError(f"{ERROR_CODE_POOL_FACTUAL_SYNC_SCOPE_INVALID}: {field_name} must not be empty")


def _parse_metadata_datetime(value: object) -> datetime | None:
    token = str(value or "").strip()
    if not token:
        return None
    parsed = parse_datetime(token)
    if parsed is None:
        return None
    return _ensure_aware_datetime(parsed)


def _ensure_aware_datetime(value: datetime) -> datetime:
    if timezone.is_naive(value):
        return value.replace(tzinfo=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


def _is_block_window_active(
    *,
    now: datetime,
    window_from: datetime | None,
    window_to: datetime | None,
) -> bool:
    if window_from is not None and now < window_from:
        return False
    if window_to is not None and now > window_to:
        return False
    return True


__all__ = [
    "ERROR_CODE_POOL_FACTUAL_SYNC_EXTERNAL_SESSIONS_BLOCKED",
    "ERROR_CODE_POOL_FACTUAL_SYNC_FAILED",
    "ERROR_CODE_POOL_FACTUAL_SYNC_SCOPE_INVALID",
    "ERROR_CODE_POOL_FACTUAL_SYNC_SOURCE_MAINTENANCE",
    "ERROR_CODE_POOL_FACTUAL_SYNC_SOURCE_UNAVAILABLE",
    "FACTUAL_SOURCE_PROFILE_SALES_REPORT_V1",
    "FACTUAL_SYNC_FRESHNESS_TARGET_SECONDS",
    "FactualSalesReportSyncScope",
    "FactualSyncSourceState",
    "FactualSyncTransportError",
    "SOURCE_STATE_AVAILABLE",
    "SOURCE_STATE_BLOCKED_EXTERNAL_SESSIONS",
    "SOURCE_STATE_MAINTENANCE",
    "SOURCE_STATE_UNAVAILABLE",
    "build_factual_sales_report_sync_contract",
    "build_factual_sales_report_sync_scope",
    "mark_factual_sync_checkpoint_error",
    "mark_factual_sync_checkpoint_success",
    "resolve_factual_sync_source_state",
]
