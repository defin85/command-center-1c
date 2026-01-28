"""Operations filtering and sorting helpers."""

from __future__ import annotations

import json

from django.utils.dateparse import parse_datetime

# =============================================================================
# Filters & Sorting
# =============================================================================

OPERATION_FILTER_FIELDS = {
    "name": {"field": "name", "type": "text"},
    "id": {"field": "id", "type": "text"},
    "status": {"field": "status", "type": "enum"},
    "operation_type": {"field": "operation_type", "type": "enum"},
    "created_by": {"field": "created_by", "type": "text"},
    "created_at": {"field": "created_at", "type": "datetime"},
    "duration_seconds": {"field": "duration_seconds", "type": "number"},
    "workflow_execution_id": {"field": "metadata__workflow_execution_id", "type": "text"},
    "node_id": {"field": "metadata__node_id", "type": "text"},
}

OPERATION_SORT_FIELDS = {
    "created_at": "created_at",
    "name": "name",
    "status": "status",
    "operation_type": "operation_type",
    "duration_seconds": "duration_seconds",
}

TASK_FILTER_FIELDS = {
    "database_name": {"field": "database_name", "type": "text"},
    "status": {"field": "status", "type": "enum"},
    "worker_id": {"field": "worker_id", "type": "text"},
    "error_message": {"field": "error_message", "type": "text"},
    "started_at": {"field": "started_at", "type": "datetime"},
    "completed_at": {"field": "completed_at", "type": "datetime"},
    "duration_seconds": {"field": "duration_seconds", "type": "number"},
}

TASK_SORT_FIELDS = {
    "database_name": "database_name",
    "status": "status",
    "worker_id": "worker_id",
    "started_at": "started_at",
    "completed_at": "completed_at",
    "duration_seconds": "duration_seconds",
}


def _parse_filters(raw_filters: str | None) -> tuple[dict, dict | None]:
    if not raw_filters:
        return {}, None
    try:
        payload = json.loads(raw_filters)
    except json.JSONDecodeError:
        return {}, {
            "code": "INVALID_FILTERS",
            "message": "filters must be valid JSON object",
        }
    if not isinstance(payload, dict):
        return {}, {
            "code": "INVALID_FILTERS",
            "message": "filters must be a JSON object",
        }
    return payload, None


def _parse_sort(raw_sort: str | None) -> tuple[dict | None, dict | None]:
    if not raw_sort:
        return None, None
    try:
        payload = json.loads(raw_sort)
    except json.JSONDecodeError:
        return None, {
            "code": "INVALID_SORT",
            "message": "sort must be valid JSON object",
        }
    if not isinstance(payload, dict):
        return None, {
            "code": "INVALID_SORT",
            "message": "sort must be a JSON object",
        }
    return payload, None


def _apply_text_filter(qs, field: str, op: str, value: str):
    if op == "contains":
        return qs.filter(**{f"{field}__icontains": value})
    if op == "eq":
        return qs.filter(**{field: value})
    return qs


def _apply_number_filter(qs, field: str, op: str, value: int | float):
    if op == "eq":
        return qs.filter(**{field: value})
    if op == "gt":
        return qs.filter(**{f"{field}__gt": value})
    if op == "gte":
        return qs.filter(**{f"{field}__gte": value})
    if op == "lt":
        return qs.filter(**{f"{field}__lt": value})
    if op == "lte":
        return qs.filter(**{f"{field}__lte": value})
    return qs


def _apply_datetime_filter(qs, field: str, op: str, value: str):
    parsed = parse_datetime(value)
    if op in ("contains", "eq") and parsed is None:
        return qs.filter(**{f"{field}__icontains": value})
    if parsed:
        if op == "eq":
            return qs.filter(**{f"{field}__date": parsed.date()})
        if op == "before":
            return qs.filter(**{f"{field}__date__lt": parsed.date()})
        if op == "after":
            return qs.filter(**{f"{field}__date__gt": parsed.date()})
    return qs


def _apply_enum_filter(qs, field: str, op: str, value):
    if op == "in" and isinstance(value, list):
        return qs.filter(**{f"{field}__in": value})
    return qs.filter(**{field: value})


def _apply_filters(qs, filters: dict, config: dict) -> tuple:
    for key, payload in filters.items():
        if key not in config:
            return qs, {
                "code": "UNKNOWN_FILTER",
                "message": f"Unknown filter key: {key}",
            }
        value = payload
        op = "eq"
        if isinstance(payload, dict):
            op = payload.get("op", "eq")
            value = payload.get("value")
        if value in (None, ""):
            continue
        field_meta = config[key]
        field = field_meta["field"]
        field_type = field_meta["type"]
        if field_type == "text":
            qs = _apply_text_filter(qs, field, op, str(value))
        elif field_type == "number":
            try:
                num = float(value)
            except (ValueError, TypeError):
                return qs, {
                    "code": "INVALID_FILTER_VALUE",
                    "message": f"Invalid numeric value for {key}",
                }
            qs = _apply_number_filter(qs, field, op, num)
        elif field_type == "datetime":
            qs = _apply_datetime_filter(qs, field, op, str(value))
        elif field_type == "enum":
            qs = _apply_enum_filter(qs, field, op, value)
    return qs, None


def _apply_sort(qs, sort_payload: dict | None, config: dict) -> tuple:
    if not sort_payload:
        return qs, None
    key = sort_payload.get("key")
    order = sort_payload.get("order")
    if key not in config:
        return qs, {
            "code": "UNKNOWN_SORT",
            "message": f"Unknown sort key: {key}",
        }
    field = config[key]
    if order == "desc":
        return qs.order_by(f"-{field}"), None
    if order == "asc":
        return qs.order_by(field), None
    return qs, {
        "code": "INVALID_SORT",
        "message": "sort order must be 'asc' or 'desc'",
    }


