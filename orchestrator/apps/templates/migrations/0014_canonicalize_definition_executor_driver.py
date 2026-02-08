from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import migrations


_SUPPORTED_EXECUTOR_KINDS = {"ibcmd_cli", "designer_cli", "workflow"}
_CANONICAL_DRIVER_BY_KIND = {"ibcmd_cli": "ibcmd", "designer_cli": "cli"}


def _clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value.keys()):
            normalized = _clean_json(value[key])
            if normalized is None:
                continue
            out[str(key)] = normalized
        return out
    if isinstance(value, list):
        return [_clean_json(item) for item in value]
    return value


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(_clean_json(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_kind(raw_kind: Any) -> str:
    kind = str(raw_kind or "").strip().lower()
    if kind in _SUPPORTED_EXECUTOR_KINDS:
        return kind
    return "workflow"


def _canonicalize_payload(
    *,
    executor_kind: Any,
    executor_payload: Any,
) -> tuple[str, dict[str, Any], list[dict[str, str]]]:
    normalized_kind = _normalize_kind(executor_kind)
    payload = _clean_json(executor_payload if isinstance(executor_payload, dict) else {})
    errors: list[dict[str, str]] = []

    payload_kind = str(payload.get("kind") or "").strip().lower()
    if payload_kind and payload_kind != normalized_kind:
        errors.append(
            {
                "code": "KIND_MISMATCH",
                "message": f"executor_payload.kind={payload_kind} conflicts with executor_kind={normalized_kind}",
            }
        )

    payload["kind"] = normalized_kind
    expected_driver = _CANONICAL_DRIVER_BY_KIND.get(normalized_kind)
    payload_driver = str(payload.get("driver") or "").strip().lower()

    if expected_driver is None:
        if payload_driver:
            errors.append(
                {
                    "code": "DRIVER_NOT_ALLOWED",
                    "message": f"driver is not allowed for executor kind: {normalized_kind}",
                }
            )
        payload.pop("driver", None)
    else:
        if payload_driver and payload_driver != expected_driver:
            errors.append(
                {
                    "code": "DRIVER_KIND_MISMATCH",
                    "message": f"driver={payload_driver} conflicts with executor kind {normalized_kind} (expected {expected_driver})",
                }
            )
        payload["driver"] = expected_driver

    return normalized_kind, payload, errors


def _record_issue(
    *,
    OperationMigrationIssue,
    OperationExposure,
    definition,
    code: str,
    message: str,
    severity: str,
    details: dict[str, Any],
) -> None:
    exposure = OperationExposure.objects.filter(definition_id=definition.id).order_by("id").first()
    OperationMigrationIssue.objects.create(
        source_type="operation_definition",
        source_id=str(definition.id),
        tenant_id=getattr(exposure, "tenant_id", None),
        exposure_id=getattr(exposure, "id", None),
        severity=severity,
        code=code,
        message=message,
        details=details,
    )


def canonicalize_definition_executor_driver(apps, schema_editor):
    OperationDefinition = apps.get_model("templates", "OperationDefinition")
    OperationExposure = apps.get_model("templates", "OperationExposure")
    OperationMigrationIssue = apps.get_model("templates", "OperationMigrationIssue")

    definitions = OperationDefinition.objects.all().order_by("tenant_scope", "id")
    for definition in definitions.iterator():
        normalized_kind, normalized_payload, errors = _canonicalize_payload(
            executor_kind=definition.executor_kind,
            executor_payload=definition.executor_payload,
        )

        if errors:
            for issue in errors:
                _record_issue(
                    OperationMigrationIssue=OperationMigrationIssue,
                    OperationExposure=OperationExposure,
                    definition=definition,
                    code=issue["code"],
                    message=issue["message"],
                    severity="error",
                    details={
                        "executor_kind": definition.executor_kind,
                        "executor_payload": definition.executor_payload if isinstance(definition.executor_payload, dict) else {},
                    },
                )
            continue

        normalized_fingerprint = _fingerprint(normalized_payload)
        if (
            definition.executor_kind == normalized_kind
            and definition.executor_payload == normalized_payload
            and definition.fingerprint == normalized_fingerprint
        ):
            continue

        conflict = (
            OperationDefinition.objects.filter(
                tenant_scope=definition.tenant_scope,
                fingerprint=normalized_fingerprint,
            )
            .exclude(id=definition.id)
            .first()
        )
        if conflict is not None:
            OperationExposure.objects.filter(definition_id=definition.id).update(definition_id=conflict.id)
            _record_issue(
                OperationMigrationIssue=OperationMigrationIssue,
                OperationExposure=OperationExposure,
                definition=definition,
                code="CANONICAL_DEFINITION_MERGED",
                message="Definition merged into canonical fingerprint-equivalent definition",
                severity="warning",
                details={
                    "merged_into_definition_id": str(conflict.id),
                    "fingerprint": normalized_fingerprint,
                },
            )
            definition.delete()
            continue

        definition.executor_kind = normalized_kind
        definition.executor_payload = normalized_payload
        definition.fingerprint = normalized_fingerprint
        definition.save(update_fields=["executor_kind", "executor_payload", "fingerprint", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("templates", "0013_operationdefinition_operationexposure_and_more"),
    ]

    operations = [
        migrations.RunPython(canonicalize_definition_executor_driver, migrations.RunPython.noop),
    ]
