from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from jsonschema import Draft202012Validator

UI_ACTION_CATALOG_KEY = "ui.action_catalog"
ACTION_CATALOG_VERSION_V1 = 1

# Backend-understood reserved capabilities (MVP).
RESERVED_ACTION_CAPABILITIES: set[str] = {
    "extensions.list",
    "extensions.sync",
}

# Legacy mapping while `capability` is optional.
LEGACY_RESERVED_ACTION_IDS: dict[str, str] = {
    "extensions.list": "extensions.list",
    "extensions.sync": "extensions.sync",
}

SNAPSHOT_KIND_EXTENSIONS = "extensions"


DEFAULT_UI_ACTION_CATALOG: dict[str, Any] = {
    "catalog_version": ACTION_CATALOG_VERSION_V1,
    "extensions": {"actions": []},
}


_ACTION_CONTEXTS: list[str] = [
    "database_card",
    "bulk_page",
]


_ACTION_EXECUTOR_KINDS: list[str] = [
    "ibcmd_cli",
    "designer_cli",
    "workflow",
]


ACTION_CATALOG_SCHEMA_V1: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["catalog_version", "extensions"],
    "additionalProperties": False,
    "properties": {
        "catalog_version": {"type": "integer", "const": ACTION_CATALOG_VERSION_V1},
        "extensions": {
            "type": "object",
            "required": ["actions"],
            "additionalProperties": False,
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "label", "contexts", "executor"],
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string", "minLength": 1, "maxLength": 128},
                            "capability": {
                                "type": "string",
                                "minLength": 3,
                                "maxLength": 128,
                                # "<namespace>.<name>[.<more>]" (ASCII, lowercase, with - and _ allowed).
                                "pattern": r"^[a-z0-9_-]+(\.[a-z0-9_-]+)+$",
                            },
                            "label": {"type": "string", "minLength": 1, "maxLength": 256},
                            "contexts": {
                                "type": "array",
                                "items": {"type": "string", "enum": _ACTION_CONTEXTS},
                                "minItems": 1,
                                "uniqueItems": True,
                            },
                            "executor": {
                                "type": "object",
                                "required": ["kind"],
                                "additionalProperties": False,
                                "properties": {
                                    "kind": {"type": "string", "enum": _ACTION_EXECUTOR_KINDS},
                                    "driver": {"type": "string", "minLength": 1, "maxLength": 64},
                                    "command_id": {"type": "string", "minLength": 1, "maxLength": 256},
                                    "workflow_id": {"type": "string", "minLength": 1, "maxLength": 64},
                                    "mode": {"type": "string", "enum": ["guided", "manual"]},
                                    "params": {"type": "object"},
                                    "additional_args": {"type": "array", "items": {"type": "string"}, "maxItems": 64},
                                    "stdin": {"type": "string"},
                                    "fixed": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "confirm_dangerous": {"type": "boolean"},
                                            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
                                        },
                                    },
                                },
                                "allOf": [
                                    {
                                        "if": {"properties": {"kind": {"const": "workflow"}}},
                                        "then": {"required": ["workflow_id"]},
                                    },
                                    {
                                        "if": {"properties": {"kind": {"enum": ["ibcmd_cli", "designer_cli"]}}},
                                        "then": {"required": ["driver", "command_id"]},
                                    },
                                ],
                            },
                        },
                    },
                },
            },
        },
    },
}


_VALIDATOR_V1 = Draft202012Validator(ACTION_CATALOG_SCHEMA_V1)


@dataclass(frozen=True)
class ActionCatalogValidationError:
    path: str
    message: str

    def to_text(self) -> str:
        if self.path:
            return f"{self.path}: {self.message}"
        return self.message


def _format_path(path: Iterable[Any]) -> str:
    parts: list[str] = []
    for item in path:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            safe = str(item)
            if not parts:
                parts.append(safe)
            else:
                parts.append(f".{safe}")
    return "".join(parts)


def validate_action_catalog_v1(payload: Any) -> list[ActionCatalogValidationError]:
    errors: list[ActionCatalogValidationError] = []
    for err in sorted(_VALIDATOR_V1.iter_errors(payload), key=lambda e: (list(e.path), e.message)):
        errors.append(
            ActionCatalogValidationError(
                path=_format_path(err.path),
                message=str(err.message),
            )
        )
    return errors


def ensure_valid_action_catalog(payload: Any) -> tuple[dict[str, Any], list[ActionCatalogValidationError]]:
    default_value: dict[str, Any] = {
        "catalog_version": ACTION_CATALOG_VERSION_V1,
        "extensions": {"actions": []},
    }
    if payload is None:
        return default_value, []
    if not isinstance(payload, dict):
        return default_value, [ActionCatalogValidationError(path="", message="must be an object")]

    errors = validate_action_catalog_v1(payload)
    if errors:
        return default_value, errors
    return payload, []


def validate_action_catalog_references(payload: Any) -> list[ActionCatalogValidationError]:
    """
    Validate action catalog external references (driver commands and workflows).
    Intended for update-time validation in staff-only runtime setting update flow.
    """
    if not isinstance(payload, dict):
        return []

    extensions = payload.get("extensions")
    if not isinstance(extensions, dict):
        return []

    actions = extensions.get("actions")
    if not isinstance(actions, list):
        return []

    errors: list[ActionCatalogValidationError] = []
    commands_cache: dict[str, dict[str, Any] | None] = {}

    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            continue

        executor = action.get("executor")
        if not isinstance(executor, dict):
            continue

        kind = executor.get("kind")
        path_prefix = f"extensions.actions[{idx}].executor"

        if kind in ("ibcmd_cli", "designer_cli"):
            driver = executor.get("driver")
            command_id = executor.get("command_id")
            if not isinstance(driver, str) or not driver.strip():
                errors.append(ActionCatalogValidationError(path=f"{path_prefix}.driver", message="must be a non-empty string"))
                continue
            if not isinstance(command_id, str) or not command_id.strip():
                errors.append(ActionCatalogValidationError(path=f"{path_prefix}.command_id", message="must be a non-empty string"))
                continue

            normalized_driver = driver.strip().lower()
            normalized_command_id = command_id.strip()

            if normalized_driver not in commands_cache:
                try:
                    from apps.operations.driver_catalog_effective import get_effective_driver_catalog, resolve_driver_catalog_versions

                    resolved = resolve_driver_catalog_versions(normalized_driver)
                    if resolved.base_version is None:
                        commands_cache[normalized_driver] = None
                    else:
                        effective = get_effective_driver_catalog(
                            driver=normalized_driver,
                            base_version=resolved.base_version,
                            overrides_version=resolved.overrides_version,
                        )
                        catalog = effective.catalog
                        commands_by_id = catalog.get("commands_by_id") if isinstance(catalog, dict) else None
                        commands_cache[normalized_driver] = commands_by_id if isinstance(commands_by_id, dict) else None
                except Exception:
                    commands_cache[normalized_driver] = None

            commands_by_id = commands_cache.get(normalized_driver)
            if not isinstance(commands_by_id, dict):
                errors.append(
                    ActionCatalogValidationError(
                        path=f"{path_prefix}.driver",
                        message=f"driver catalog not available: {normalized_driver}",
                    )
                )
                continue

            command = commands_by_id.get(normalized_command_id)
            if not isinstance(command, dict):
                errors.append(
                    ActionCatalogValidationError(
                        path=f"{path_prefix}.command_id",
                        message=f"unknown command_id: {normalized_command_id}",
                    )
                )
                continue
            if command.get("disabled") is True:
                errors.append(
                    ActionCatalogValidationError(
                        path=f"{path_prefix}.command_id",
                        message=f"command_id is disabled: {normalized_command_id}",
                    )
                )
                continue

        if kind == "workflow":
            workflow_id = executor.get("workflow_id")
            if not isinstance(workflow_id, str) or not workflow_id.strip():
                errors.append(ActionCatalogValidationError(path=f"{path_prefix}.workflow_id", message="must be a non-empty string"))
                continue

            normalized_workflow_id = workflow_id.strip()
            try:
                workflow_uuid = uuid.UUID(normalized_workflow_id)
            except (ValueError, AttributeError):
                errors.append(
                    ActionCatalogValidationError(
                        path=f"{path_prefix}.workflow_id",
                        message=f"must be a valid UUID: {normalized_workflow_id}",
                    )
                )
                continue

            try:
                from apps.templates.workflow.models import WorkflowTemplate

                workflow = WorkflowTemplate.objects.filter(id=workflow_uuid).only("id", "is_active", "is_valid").first()
            except Exception:
                workflow = None

            if workflow is None:
                errors.append(
                    ActionCatalogValidationError(
                        path=f"{path_prefix}.workflow_id",
                        message=f"workflow not found: {normalized_workflow_id}",
                    )
                )
                continue

            if not getattr(workflow, "is_active", False):
                errors.append(
                    ActionCatalogValidationError(
                        path=f"{path_prefix}.workflow_id",
                        message=f"workflow is inactive: {normalized_workflow_id}",
                    )
                )
                continue

            if not getattr(workflow, "is_valid", False):
                errors.append(
                    ActionCatalogValidationError(
                        path=f"{path_prefix}.workflow_id",
                        message=f"workflow is not valid: {normalized_workflow_id}",
                    )
                )
                continue

    return errors


def _normalize_str(value: Any) -> str:
    return str(value or "").strip()


def _get_action_capability(action: dict[str, Any]) -> str | None:
    cap = action.get("capability")
    if isinstance(cap, str) and cap.strip():
        return cap.strip()
    return None


def get_reserved_action_capability(action: dict[str, Any]) -> str | None:
    """
    Return reserved backend-understood capability for the action.

    Legacy fallback:
      - if `capability` is missing, `id=="extensions.list|extensions.sync"` is treated as the corresponding capability.
    """
    cap = _get_action_capability(action)
    if cap:
        return cap if cap in RESERVED_ACTION_CAPABILITIES else None
    action_id = _normalize_str(action.get("id"))
    return LEGACY_RESERVED_ACTION_IDS.get(action_id)


def validate_action_catalog_reserved_capabilities(payload: Any) -> list[ActionCatalogValidationError]:
    """
    Fail-closed validation for backend-understood reserved capabilities.

    Ensures at most one action per reserved capability (including legacy id fallback).
    Intended for update-time validation in staff-only runtime setting update flow.
    """
    if not isinstance(payload, dict):
        return []
    extensions = payload.get("extensions")
    if not isinstance(extensions, dict):
        return []
    actions = extensions.get("actions")
    if not isinstance(actions, list):
        return []

    errors: list[ActionCatalogValidationError] = []
    seen: dict[str, int] = {}

    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        reserved_capability = get_reserved_action_capability(action)
        if not reserved_capability:
            continue
        prev_idx = seen.get(reserved_capability)
        if prev_idx is None:
            seen[reserved_capability] = idx
            continue

        if _get_action_capability(action):
            path = f"extensions.actions[{idx}].capability"
        else:
            path = f"extensions.actions[{idx}].id"
        errors.append(
            ActionCatalogValidationError(
                path=path,
                message=f"duplicate reserved capability: {reserved_capability} (already defined at extensions.actions[{prev_idx}])",
            )
        )

    return errors


def compute_ibcmd_cli_snapshot_marker_from_action_catalog(catalog: Any, command_id: str) -> dict[str, Any]:
    """
    Compute snapshot marker for an ibcmd_cli operation based on effective `ui.action_catalog`.

    MVP: mark extensions snapshots when command_id is bound to reserved extensions capabilities.
    """
    normalized_command_id = _normalize_str(command_id)
    if not normalized_command_id:
        return {}
    if not isinstance(catalog, dict):
        return {}

    extensions = catalog.get("extensions")
    actions = extensions.get("actions") if isinstance(extensions, dict) else None
    if not isinstance(actions, list):
        return {}

    matched_caps: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            continue
        cap = get_reserved_action_capability(action)
        if cap not in RESERVED_ACTION_CAPABILITIES:
            continue
        executor = action.get("executor")
        if not isinstance(executor, dict):
            continue
        if executor.get("kind") != "ibcmd_cli":
            continue
        exec_command_id = _normalize_str(executor.get("command_id"))
        if exec_command_id != normalized_command_id:
            continue
        matched_caps.add(cap)

    if not matched_caps:
        return {}

    marker: dict[str, Any] = {
        "snapshot_kinds": [SNAPSHOT_KIND_EXTENSIONS],
        "snapshot_source": "ui.action_catalog",
    }
    if len(matched_caps) == 1:
        marker["action_capability"] = next(iter(matched_caps))
    return marker
