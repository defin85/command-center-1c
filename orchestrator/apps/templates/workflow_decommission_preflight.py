from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from django.db.models import Count, Q
from jsonschema import Draft202012Validator

from apps.templates.workflow.models import WorkflowExecution


REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = (
    REPO_ROOT
    / "openspec/changes/refactor-unify-pools-workflow-execution-core/execution-consumers-registry.yaml"
)
REGISTRY_SCHEMA_PATH = (
    REPO_ROOT
    / "openspec/changes/refactor-unify-pools-workflow-execution-core/execution-consumers-registry.schema.yaml"
)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(content)
    if not isinstance(payload, dict):
        raise ValueError(f"YAML payload must be an object: {path}")
    return payload


def _schema_errors(*, schema: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for item in sorted(validator.iter_errors(registry), key=lambda error: str(error.path)):
        path = ".".join(str(segment) for segment in item.path)
        location = path or "<root>"
        errors.append(f"{location}: {item.message}")
    return errors


def run_workflow_decommission_preflight() -> dict[str, Any]:
    registry = _load_yaml_file(REGISTRY_PATH)
    schema = _load_yaml_file(REGISTRY_SCHEMA_PATH)
    schema_errors = _schema_errors(schema=schema, registry=registry)

    consumers_payload = registry.get("consumers")
    consumers = consumers_payload if isinstance(consumers_payload, list) else []
    registry_consumers = {
        str(item.get("consumer")): item
        for item in consumers
        if isinstance(item, dict) and item.get("consumer")
    }

    runtime_stats_rows = list(
        WorkflowExecution.objects.values("execution_consumer")
        .annotate(
            total=Count("id"),
            null_tenant_total=Count("id", filter=Q(tenant__isnull=True)),
        )
        .order_by("execution_consumer")
    )
    runtime_stats = {
        str(row.get("execution_consumer") or ""): {
            "total": int(row.get("total") or 0),
            "null_tenant_total": int(row.get("null_tenant_total") or 0),
        }
        for row in runtime_stats_rows
    }

    unknown_runtime_consumers = sorted(
        consumer for consumer in runtime_stats.keys() if consumer and consumer not in registry_consumers
    )
    unmigrated_consumers = sorted(
        consumer
        for consumer, meta in registry_consumers.items()
        if not bool(meta.get("migrated"))
    )

    tenant_mode_violations: list[dict[str, Any]] = []
    transition_null_tenant_consumers: list[dict[str, Any]] = []
    for consumer, runtime in runtime_stats.items():
        if not consumer:
            continue
        meta = registry_consumers.get(consumer)
        if not isinstance(meta, dict):
            continue
        tenant_mode = str(meta.get("tenant_mode") or "required")
        null_tenant_total = int(runtime.get("null_tenant_total") or 0)

        if tenant_mode == "required" and null_tenant_total > 0:
            tenant_mode_violations.append(
                {
                    "consumer": consumer,
                    "tenant_mode": tenant_mode,
                    "null_tenant_total": null_tenant_total,
                }
            )
            continue

        if tenant_mode == "nullable_transition" and null_tenant_total > 0:
            transition_null_tenant_consumers.append(
                {
                    "consumer": consumer,
                    "null_tenant_total": null_tenant_total,
                }
            )

    checks = [
        {
            "key": "registry_schema",
            "ok": len(schema_errors) == 0,
            "errors": schema_errors,
        },
        {
            "key": "runtime_consumers_registered",
            "ok": len(unknown_runtime_consumers) == 0,
            "unknown_runtime_consumers": unknown_runtime_consumers,
        },
        {
            "key": "all_consumers_migrated",
            "ok": len(unmigrated_consumers) == 0,
            "unmigrated_consumers": unmigrated_consumers,
        },
        {
            "key": "tenant_mode_requirements",
            "ok": len(tenant_mode_violations) == 0,
            "violations": tenant_mode_violations,
            "transition_null_tenant_consumers": transition_null_tenant_consumers,
        },
    ]

    decision = "go" if all(bool(item.get("ok")) for item in checks) else "no_go"
    return {
        "decision": decision,
        "registry": {
            "path": str(REGISTRY_PATH),
            "schema_path": str(REGISTRY_SCHEMA_PATH),
            "registry_version": registry.get("registry_version"),
            "owner": registry.get("owner"),
        },
        "runtime": {
            "consumers": runtime_stats,
        },
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "failed_checks": sum(1 for item in checks if not bool(item.get("ok"))),
            "unknown_runtime_consumers": len(unknown_runtime_consumers),
            "unmigrated_consumers": len(unmigrated_consumers),
            "tenant_mode_violations": len(tenant_mode_violations),
        },
    }
