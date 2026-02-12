from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping
from uuid import UUID


@dataclass(frozen=True)
class ExternalIdentityContext:
    run_id: str
    target_database_id: str
    document_kind: str
    period_start: date
    period_end: date | None = None


@dataclass(frozen=True)
class ExternalDocumentIdentity:
    value: str
    strategy: str


PRIMARY_GUID_FIELDS = ("_IDRRef", "Ref_Key", "id", "ref")


def resolve_external_document_identity(
    *,
    odata_payload: Mapping[str, Any] | None,
    context: ExternalIdentityContext,
) -> ExternalDocumentIdentity:
    guid = _extract_guid(odata_payload or {})
    if guid is not None:
        return ExternalDocumentIdentity(value=guid, strategy="guid_from_odata")

    return ExternalDocumentIdentity(
        value=build_external_run_key(context),
        strategy="external_run_key_fallback",
    )


def build_external_run_key(context: ExternalIdentityContext) -> str:
    period_signature = context.period_start.isoformat()
    if context.period_end is not None:
        period_signature = f"{period_signature}:{context.period_end.isoformat()}"

    raw = "|".join(
        [
            context.run_id,
            context.target_database_id,
            context.document_kind,
            period_signature,
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"runkey-{digest[:32]}"


def _extract_guid(payload: Mapping[str, Any]) -> str | None:
    for field_name in PRIMARY_GUID_FIELDS:
        value = payload.get(field_name)
        if not value:
            continue
        normalized = str(value).strip()
        if not normalized:
            continue

        candidate = normalized
        if candidate.startswith("guid'") and candidate.endswith("'"):
            candidate = candidate[5:-1]

        try:
            parsed = UUID(candidate)
        except (ValueError, AttributeError):
            continue
        return str(parsed)

    return None
