from __future__ import annotations

from datetime import date
from typing import Any, Mapping


CCPOOL_TRACEABILITY_VERSION = "1"
CCPOOL_TRACEABILITY_PREFIX = f"CCPOOL:v={CCPOOL_TRACEABILITY_VERSION}"
CCPOOL_COMMENT_FIELD_CANDIDATES = ("Comment", "Комментарий")
CCPOOL_DIRECT_KINDS = {"receipt", "sale", "carry", "manual"}
CCPOOL_REQUIRED_MARKER_FIELDS = ("pool", "run", "batch", "org", "q", "kind")
_CCPOOL_ROLE_KIND_OVERRIDES = {
    "base": "sale",
    "invoice": "sale",
    "purchase": "receipt",
}


def build_ccpool_quarter_token(*, period_start: date) -> str:
    quarter = ((int(period_start.month) - 1) // 3) + 1
    return f"{period_start.year}Q{quarter}"


def build_ccpool_document_traceability(
    *,
    pool_id: str,
    run_id: str,
    batch_id: str | None,
    organization_id: str | None,
    period_start: date,
    document_role: str,
    direction: str,
    batch_kind: str | None,
) -> dict[str, str] | None:
    normalized_batch_id = str(batch_id or "").strip()
    normalized_organization_id = str(organization_id or "").strip()
    if not normalized_batch_id and not normalized_organization_id:
        return None
    if not normalized_batch_id or not normalized_organization_id:
        raise ValueError(
            "POOL_DOCUMENT_TRACEABILITY_INVALID: batch-backed traceability requires "
            "both batch_id and organization_id"
        )

    kind = _resolve_traceability_kind(
        document_role=document_role,
        direction=direction,
        batch_kind=batch_kind,
    )
    if kind is None:
        raise ValueError(
            "POOL_DOCUMENT_TRACEABILITY_INVALID: unsupported document_role for "
            f"CCPOOL marker '{str(document_role or '').strip() or '<empty>'}'"
        )

    return {
        "pool_id": str(pool_id).strip(),
        "run_id": str(run_id).strip(),
        "batch_id": normalized_batch_id,
        "organization_id": normalized_organization_id,
        "quarter": build_ccpool_quarter_token(period_start=period_start),
        "kind": kind,
    }


def build_ccpool_traceability_marker(*, traceability: Mapping[str, Any]) -> str:
    normalized = _normalize_traceability(traceability=traceability)
    marker_fields = {
        "pool": normalized["pool_id"],
        "run": normalized["run_id"] or "-",
        "batch": normalized["batch_id"] or "-",
        "org": normalized["organization_id"],
        "q": normalized["quarter"],
        "kind": normalized["kind"],
    }
    marker_tokens = [
        CCPOOL_TRACEABILITY_PREFIX,
        *(f"{field_name}={marker_fields[field_name]}" for field_name in CCPOOL_REQUIRED_MARKER_FIELDS),
    ]
    return ";".join(marker_tokens)


def parse_ccpool_traceability_marker(comment: Any) -> dict[str, str] | None:
    if not isinstance(comment, str):
        return None
    marker_block, separator, human_tail = comment.partition("||")
    if not marker_block.startswith(f"{CCPOOL_TRACEABILITY_PREFIX};"):
        return None

    fields: dict[str, str] = {}
    for token in marker_block.split(";")[1:]:
        key, has_separator, value = token.partition("=")
        key = key.strip()
        value = value.strip()
        if not has_separator or not key or not value:
            return None
        if key in fields:
            return None
        fields[key] = value

    if tuple(fields.keys()) != CCPOOL_REQUIRED_MARKER_FIELDS:
        return None

    pool_id = fields["pool"]
    organization_id = fields["org"]
    quarter = fields["q"]
    kind = fields["kind"]
    if not pool_id or pool_id == "-":
        return None
    if not organization_id or organization_id == "-":
        return None
    if len(quarter) != 6 or quarter[4] != "Q" or quarter[5] not in {"1", "2", "3", "4"}:
        return None
    if not quarter[:4].isdigit():
        return None
    if kind not in CCPOOL_DIRECT_KINDS:
        return None

    return {
        "pool_id": pool_id,
        "run_id": _normalize_marker_optional_id(fields["run"]),
        "batch_id": _normalize_marker_optional_id(fields["batch"]),
        "organization_id": organization_id,
        "quarter": quarter,
        "kind": kind,
        "human_tail": human_tail if separator else "",
    }


def inject_ccpool_traceability_comment(
    *,
    payload: Mapping[str, Any],
    traceability: Mapping[str, Any],
) -> dict[str, Any]:
    resolved_payload = dict(payload)
    comment_field_name = _resolve_comment_field_name(payload=resolved_payload)
    existing_comment = resolved_payload.get(comment_field_name)
    parsed_marker = parse_ccpool_traceability_marker(existing_comment)
    if parsed_marker is not None:
        human_tail = parsed_marker["human_tail"]
    elif existing_comment is None:
        human_tail = ""
    else:
        human_tail = str(existing_comment)

    marker = build_ccpool_traceability_marker(traceability=traceability)
    resolved_payload[comment_field_name] = f"{marker}||{human_tail}" if human_tail else marker
    return resolved_payload


def _normalize_traceability(*, traceability: Mapping[str, Any]) -> dict[str, str]:
    normalized = {
        "pool_id": str(traceability.get("pool_id") or "").strip(),
        "run_id": str(traceability.get("run_id") or "").strip(),
        "batch_id": str(traceability.get("batch_id") or "").strip(),
        "organization_id": str(traceability.get("organization_id") or "").strip(),
        "quarter": str(traceability.get("quarter") or "").strip(),
        "kind": str(traceability.get("kind") or "").strip().lower(),
    }
    if not normalized["pool_id"]:
        raise ValueError("CCPOOL traceability requires pool_id")
    if not normalized["organization_id"]:
        raise ValueError("CCPOOL traceability requires organization_id")
    if not normalized["quarter"]:
        raise ValueError("CCPOOL traceability requires quarter")
    if normalized["kind"] not in CCPOOL_DIRECT_KINDS:
        raise ValueError("CCPOOL traceability requires a supported kind")
    return normalized


def _resolve_traceability_kind(
    *,
    document_role: str,
    direction: str,
    batch_kind: str | None,
) -> str | None:
    normalized_role = str(document_role or "").strip().lower()
    if normalized_role in CCPOOL_DIRECT_KINDS:
        return normalized_role
    if normalized_role in _CCPOOL_ROLE_KIND_OVERRIDES:
        return _CCPOOL_ROLE_KIND_OVERRIDES[normalized_role]
    if normalized_role == "" and str(direction or "").strip().lower() == "top_down":
        return "sale"

    normalized_batch_kind = str(batch_kind or "").strip().lower()
    if normalized_batch_kind in CCPOOL_DIRECT_KINDS:
        return normalized_batch_kind
    return None


def _normalize_marker_optional_id(value: str) -> str:
    return "" if value == "-" else value


def _resolve_comment_field_name(*, payload: Mapping[str, Any]) -> str:
    for field_name in CCPOOL_COMMENT_FIELD_CANDIDATES:
        if field_name in payload:
            return field_name
    return CCPOOL_COMMENT_FIELD_CANDIDATES[0]
