from __future__ import annotations

import json
import re
from datetime import UTC, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.monitoring.models import UiIncidentTelemetryBatch, UiIncidentTelemetryEvent
from apps.tenancy.models import Tenant

_OMIT = object()
_CORRELATION_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(auth|authorization|cookie|csrf|passwd|password|secret|session|token|api[_-]?key|access[_-]?key|stdin)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|token|authorization|secret|cookie|api[_-]?key|access[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)
_KNOWN_EVENT_FIELDS = {
    "event_id",
    "event_type",
    "occurred_at",
    "route",
    "context",
    "request_id",
    "ui_action_id",
    "trace_id",
}
_SIGNAL_EVENT_TYPES = {
    "http.request.failure",
    "http.request.slow",
    "route.loop_warning",
    "ui.error.boundary",
    "ui.error.global",
    "ui.error.unhandled_rejection",
    "websocket.churn_warning",
}
_MAX_BATCH_EVENTS = 100
_MAX_OBJECT_ITEMS = 40
_MAX_STRING_LENGTH = 512
_MAX_JSON_LENGTH = 8_192
_TIMELINE_EXPANSION = timedelta(seconds=30)


def _retention_days() -> int:
    value = int(getattr(settings, "UI_INCIDENT_TELEMETRY_RETENTION_DAYS", 7) or 7)
    return max(1, value)


def _sanitize_string(value: Any, *, max_length: int = _MAX_STRING_LENGTH) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    redacted = _SENSITIVE_VALUE_PATTERN.sub(r"\1=[redacted]", text)
    if len(redacted) > max_length:
        return f"{redacted[: max_length - 3]}..."
    return redacted


def _normalize_correlation(value: Any) -> str:
    text = str(value or "").strip()
    if not text or not _CORRELATION_VALUE_PATTERN.fullmatch(text):
        return ""
    return text


def _is_sensitive_key(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    if text.endswith("_password") or text.endswith("_pwd"):
        return True
    return _SENSITIVE_KEY_PATTERN.search(text) is not None


def _sanitize_value(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    if key and _is_sensitive_key(key):
        return _OMIT
    if depth >= 6:
        return "[truncated-depth]"

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        items = list(value.items())[:_MAX_OBJECT_ITEMS]
        for child_key, child_value in items:
            normalized_key = str(child_key or "").strip()
            if not normalized_key:
                continue
            safe_value = _sanitize_value(child_value, key=normalized_key, depth=depth + 1)
            if safe_value is _OMIT:
                continue
            sanitized[normalized_key] = safe_value
        if len(value) > _MAX_OBJECT_ITEMS:
            sanitized["_truncated"] = True
        return sanitized

    if isinstance(value, list):
        sanitized_list: list[Any] = []
        for child_value in value[:_MAX_OBJECT_ITEMS]:
            safe_value = _sanitize_value(child_value, depth=depth + 1)
            if safe_value is _OMIT:
                continue
            sanitized_list.append(safe_value)
        if len(value) > _MAX_OBJECT_ITEMS:
            sanitized_list.append("[truncated]")
        return sanitized_list

    if isinstance(value, tuple):
        return _sanitize_value(list(value), depth=depth + 1)

    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str):
            return _sanitize_string(value)
        return value

    return _sanitize_string(value)


def _sanitize_json_blob(value: Any) -> dict[str, Any]:
    sanitized = _sanitize_value(value)
    if sanitized is _OMIT:
        return {}
    if not isinstance(sanitized, (dict, list)):
        sanitized = {"value": sanitized}

    serialized = json.dumps(sanitized, ensure_ascii=False, default=str)
    if len(serialized) <= _MAX_JSON_LENGTH:
        return sanitized if isinstance(sanitized, dict) else {"items": sanitized}

    preview = _sanitize_string(serialized, max_length=_MAX_JSON_LENGTH - 96)
    return {
        "truncated": True,
        "preview": preview,
    }


def _parse_occurred_at(value: Any) -> timezone.datetime | None:
    parsed = parse_datetime(str(value or "").strip())
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, UTC)
    return parsed.astimezone(UTC)


def _sanitize_route_snapshot(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    context = _sanitize_value(raw.get("context") if isinstance(raw.get("context"), dict) else {})
    return {
        "path": _sanitize_string(raw.get("path"), max_length=255),
        "search": _sanitize_string(raw.get("search"), max_length=255),
        "hash": _sanitize_string(raw.get("hash"), max_length=255),
        "context": context if isinstance(context, dict) else {},
    }


def _sanitize_event(raw_event: Any) -> dict[str, Any] | None:
    if not isinstance(raw_event, dict):
        return None

    event_id = _normalize_correlation(raw_event.get("event_id"))
    event_type = _sanitize_string(raw_event.get("event_type"), max_length=80)
    occurred_at = _parse_occurred_at(raw_event.get("occurred_at"))
    if not event_id or not event_type or occurred_at is None:
        return None

    route = _sanitize_route_snapshot(raw_event.get("route"))
    raw_context = raw_event.get("context")
    context = _sanitize_value(raw_context if isinstance(raw_context, dict) else {})
    payload = _sanitize_json_blob({
        key: value
        for key, value in raw_event.items()
        if key not in _KNOWN_EVENT_FIELDS
    })
    if isinstance(context, dict) and context:
        payload = {
            "context": context,
            **payload,
        }

    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "route_path": route["path"],
        "route_search": route["search"],
        "route_hash": route["hash"],
        "route_context": route["context"],
        "request_id": _normalize_correlation(raw_event.get("request_id")),
        "ui_action_id": _normalize_correlation(raw_event.get("ui_action_id")),
        "trace_id": _normalize_correlation(raw_event.get("trace_id")),
        "payload": payload,
    }


def cleanup_expired_ui_incident_telemetry(*, now: timezone.datetime | None = None) -> timezone.datetime:
    current_time = now or timezone.now()
    cutoff = current_time - timedelta(days=_retention_days())
    UiIncidentTelemetryBatch.objects.filter(
        Q(last_occurred_at__lt=cutoff)
        | (Q(last_occurred_at__isnull=True) & Q(created_at__lt=cutoff))
    ).delete()
    return cutoff


def ingest_ui_incident_telemetry_batch(
    *,
    tenant: Tenant,
    actor_user,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    retention_cutoff = cleanup_expired_ui_incident_telemetry()
    batch_id = _normalize_correlation(envelope.get("batch_id"))
    flush_reason = _sanitize_string(envelope.get("flush_reason"), max_length=32) or "manual"
    route = _sanitize_route_snapshot(envelope.get("route"))
    release = envelope.get("release") if isinstance(envelope.get("release"), dict) else {}
    session_id = _normalize_correlation(envelope.get("session_id"))
    raw_events = list(envelope.get("events") or [])
    client_dropped_events = max(0, int(envelope.get("dropped_events_count") or 0))
    queued_events = raw_events[:_MAX_BATCH_EVENTS]
    trimmed_events = max(0, len(raw_events) - _MAX_BATCH_EVENTS)

    defaults = {
        "actor_user": actor_user if getattr(actor_user, "is_authenticated", False) else None,
        "actor_username": getattr(actor_user, "username", "") or "",
        "flush_reason": flush_reason,
        "session_id": session_id,
        "release_app": _sanitize_string(release.get("app"), max_length=120),
        "release_fingerprint": _sanitize_string(release.get("fingerprint"), max_length=160),
        "release_mode": _sanitize_string(release.get("mode"), max_length=80),
        "release_origin": _sanitize_string(release.get("origin"), max_length=255),
        "route_path": route["path"],
        "route_search": route["search"],
        "route_hash": route["hash"],
        "route_context": route["context"],
        "dropped_event_count": client_dropped_events + trimmed_events,
    }

    with transaction.atomic():
        batch, created = UiIncidentTelemetryBatch.objects.get_or_create(
            tenant=tenant,
            batch_id=batch_id,
            defaults=defaults,
        )
        if not created:
            return {
                "batch_id": batch.batch_id,
                "accepted_events": batch.accepted_event_count,
                "duplicate_events": batch.duplicate_event_count,
                "dropped_events": batch.dropped_event_count,
                "duplicate": True,
                "retention_cutoff": retention_cutoff,
            }

        accepted_events = 0
        duplicate_events = 0
        dropped_events = client_dropped_events + trimmed_events
        first_occurred_at = None
        last_occurred_at = None

        for raw_event in queued_events:
            sanitized = _sanitize_event(raw_event)
            if sanitized is None:
                dropped_events += 1
                continue

            event, event_created = UiIncidentTelemetryEvent.objects.get_or_create(
                tenant=tenant,
                event_id=sanitized["event_id"],
                defaults={
                    "batch": batch,
                    "actor_user": actor_user if getattr(actor_user, "is_authenticated", False) else None,
                    "actor_username": getattr(actor_user, "username", "") or "",
                    "session_id": session_id,
                    **sanitized,
                },
            )
            if not event_created:
                duplicate_events += 1
                continue

            accepted_events += 1
            first_occurred_at = (
                event.occurred_at
                if first_occurred_at is None or event.occurred_at < first_occurred_at
                else first_occurred_at
            )
            last_occurred_at = (
                event.occurred_at
                if last_occurred_at is None or event.occurred_at > last_occurred_at
                else last_occurred_at
            )

        batch.accepted_event_count = accepted_events
        batch.duplicate_event_count = duplicate_events
        batch.dropped_event_count = dropped_events
        batch.first_occurred_at = first_occurred_at
        batch.last_occurred_at = last_occurred_at or first_occurred_at
        batch.save(
            update_fields=[
                "accepted_event_count",
                "duplicate_event_count",
                "dropped_event_count",
                "first_occurred_at",
                "last_occurred_at",
            ]
        )

    return {
        "batch_id": batch.batch_id,
        "accepted_events": accepted_events,
        "duplicate_events": duplicate_events,
        "dropped_events": dropped_events,
        "duplicate": False,
        "retention_cutoff": retention_cutoff,
    }


def _apply_filters(
    queryset,
    *,
    actor_username: str = "",
    user_id: int | None = None,
    session_id: str = "",
    request_id: str = "",
    ui_action_id: str = "",
    trace_id: str = "",
    route_path: str = "",
    started_at: timezone.datetime | None = None,
    ended_at: timezone.datetime | None = None,
):
    if actor_username:
        queryset = queryset.filter(actor_username=actor_username)
    if user_id is not None:
        queryset = queryset.filter(actor_user_id=user_id)
    if session_id:
        queryset = queryset.filter(session_id=session_id)
    if request_id:
        queryset = queryset.filter(request_id=request_id)
    if ui_action_id:
        queryset = queryset.filter(ui_action_id=ui_action_id)
    if trace_id:
        queryset = queryset.filter(trace_id=trace_id)
    if route_path:
        queryset = queryset.filter(route_path=route_path)
    if started_at is not None:
        queryset = queryset.filter(occurred_at__gte=started_at)
    if ended_at is not None:
        queryset = queryset.filter(occurred_at__lte=ended_at)
    return queryset


def _build_summary_preview(event: UiIncidentTelemetryEvent) -> dict[str, Any]:
    payload = event.payload if isinstance(event.payload, dict) else {}
    preview_keys = [
        "action_kind",
        "action_name",
        "error_code",
        "error_title",
        "error_name",
        "error_message",
        "outcome",
        "status",
        "latency_ms",
        "method",
        "path",
        "owner",
        "reuse_key",
        "surface_id",
        "control_id",
        "route_writer_owner",
        "write_reason",
        "navigation_mode",
        "oscillating_keys",
        "writer_owners",
        "transition_count",
        "window_ms",
    ]
    return {
        key: payload[key]
        for key in preview_keys
        if key in payload and payload[key] not in (None, "", [], {})
    }


def _build_release_metadata(batch: UiIncidentTelemetryBatch) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "app": batch.release_app or None,
            "fingerprint": batch.release_fingerprint or None,
            "mode": batch.release_mode or None,
            "origin": batch.release_origin or None,
        }.items()
        if value not in (None, "")
    }


def _derive_incident_key(event: UiIncidentTelemetryEvent) -> str:
    if event.request_id:
        return f"request:{event.request_id}"
    if event.ui_action_id:
        return f"action:{event.ui_action_id}"
    if event.session_id:
        return f"session:{event.session_id}:{event.route_path or '-'}"
    return f"event:{event.event_id}"


def list_ui_incident_summaries(
    *,
    tenant: Tenant,
    actor_username: str = "",
    user_id: int | None = None,
    session_id: str = "",
    request_id: str = "",
    ui_action_id: str = "",
    trace_id: str = "",
    route_path: str = "",
    started_at: timezone.datetime | None = None,
    ended_at: timezone.datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    queryset = UiIncidentTelemetryEvent.objects.filter(tenant=tenant)
    queryset = _apply_filters(
        queryset,
        actor_username=actor_username,
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        ui_action_id=ui_action_id,
        trace_id=trace_id,
        route_path=route_path,
        started_at=started_at,
        ended_at=ended_at,
    )
    signal_events = list(
        queryset
        .filter(event_type__in=_SIGNAL_EVENT_TYPES)
        .select_related("batch")
        .order_by("-occurred_at", "-id")[: max(limit * 20, 200)]
    )

    grouped: dict[str, dict[str, Any]] = {}
    for event in signal_events:
        incident_key = _derive_incident_key(event)
        item = grouped.setdefault(
            incident_key,
            {
                "incident_id": incident_key,
                "actor_username": event.actor_username,
                "user_id": event.actor_user_id,
                "session_id": event.session_id or None,
                "request_id": event.request_id or None,
                "ui_action_id": event.ui_action_id or None,
                "trace_id": event.trace_id or None,
                "route_path": event.route_path or None,
                "release": _build_release_metadata(event.batch),
                "started_at": event.occurred_at,
                "ended_at": event.occurred_at,
                "signal_event_types": [],
                "signal_count": 0,
                "last_event_type": event.event_type,
                "preview": _build_summary_preview(event),
            },
        )
        item["signal_count"] += 1
        if event.event_type not in item["signal_event_types"]:
            item["signal_event_types"].append(event.event_type)
        if event.trace_id and not item["trace_id"]:
            item["trace_id"] = event.trace_id
        if event.occurred_at < item["started_at"]:
            item["started_at"] = event.occurred_at
        if event.occurred_at >= item["ended_at"]:
            item["ended_at"] = event.occurred_at
            item["last_event_type"] = event.event_type
            item["preview"] = _build_summary_preview(event)
            if event.trace_id:
                item["trace_id"] = event.trace_id
            item["release"] = _build_release_metadata(event.batch)

    ordered = sorted(grouped.values(), key=lambda item: item["ended_at"], reverse=True)
    sliced = ordered[offset:offset + limit]
    return {
        "incidents": sliced,
        "count": len(sliced),
        "total": len(ordered),
    }


def _serialize_event(event: UiIncidentTelemetryEvent) -> dict[str, Any]:
    return {
        "batch_id": event.batch.batch_id,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at,
        "actor_username": event.actor_username or None,
        "user_id": event.actor_user_id,
        "session_id": event.session_id or None,
        "request_id": event.request_id or None,
        "ui_action_id": event.ui_action_id or None,
        "trace_id": event.trace_id or None,
        "release": _build_release_metadata(event.batch),
        "route": {
            "path": event.route_path,
            "search": event.route_search,
            "hash": event.route_hash,
            "context": event.route_context if isinstance(event.route_context, dict) else {},
        },
        "payload": event.payload if isinstance(event.payload, dict) else {},
    }


def get_ui_incident_timeline(
    *,
    tenant: Tenant,
    actor_username: str = "",
    user_id: int | None = None,
    session_id: str = "",
    request_id: str = "",
    ui_action_id: str = "",
    trace_id: str = "",
    route_path: str = "",
    started_at: timezone.datetime | None = None,
    ended_at: timezone.datetime | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    queryset = UiIncidentTelemetryEvent.objects.filter(tenant=tenant)
    queryset = _apply_filters(
        queryset,
        actor_username=actor_username,
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        ui_action_id=ui_action_id,
        trace_id=trace_id,
        route_path=route_path,
        started_at=started_at,
        ended_at=ended_at,
    )

    if not session_id and (request_id or ui_action_id or trace_id):
        anchors = list(queryset.order_by("occurred_at", "id")[:200])
        if anchors:
            session_ids = sorted({event.session_id for event in anchors if event.session_id})
            earliest = min(event.occurred_at for event in anchors) - _TIMELINE_EXPANSION
            latest = max(event.occurred_at for event in anchors) + _TIMELINE_EXPANSION
            expanded_queryset = UiIncidentTelemetryEvent.objects.filter(tenant=tenant)
            expanded_queryset = _apply_filters(
                expanded_queryset,
                actor_username=actor_username,
                user_id=user_id,
                route_path=route_path,
            )
            if session_ids:
                expanded_queryset = expanded_queryset.filter(
                    session_id__in=session_ids,
                    occurred_at__gte=earliest,
                    occurred_at__lte=latest,
                )
            queryset = expanded_queryset

    total = queryset.count()
    rows = list(queryset.order_by("occurred_at", "id")[offset:offset + limit].select_related("batch"))
    return {
        "timeline": [_serialize_event(row) for row in rows],
        "count": len(rows),
        "total": total,
    }
