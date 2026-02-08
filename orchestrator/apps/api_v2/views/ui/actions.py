"""UI action catalog endpoint."""

from __future__ import annotations

import logging
import uuid

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.operations.driver_catalog_effective import (
    filter_catalog_for_user,
    get_effective_driver_catalog,
    resolve_driver_catalog_versions,
)
from apps.templates.operation_catalog_service import build_effective_action_catalog_payload
from apps.templates.workflow.models import WorkflowTemplate

logger = logging.getLogger(__name__)


class ActionCatalogExtensionsSerializer(serializers.Serializer):
    actions = serializers.ListField(child=serializers.JSONField())


class ActionCatalogResponseSerializer(serializers.Serializer):
    catalog_version = serializers.IntegerField()
    extensions = ActionCatalogExtensionsSerializer()


class ActionCatalogEditorHintHelpSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    description = serializers.CharField(required=False)


class ActionCatalogEditorCapabilityHintsSerializer(serializers.Serializer):
    fixed_schema = serializers.JSONField(required=False)
    fixed_ui_schema = serializers.JSONField(required=False)
    target_binding_schema = serializers.JSONField(required=False)
    help = ActionCatalogEditorHintHelpSerializer(required=False)


class ActionCatalogEditorHintsResponseSerializer(serializers.Serializer):
    hints_version = serializers.IntegerField()
    # keys are capability ids; values are hint objects (schema + uiSchema)
    capabilities = serializers.DictField()


def _build_extensions_set_flags_hints() -> dict:
    fixed_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "apply_mask": {
                "type": "object",
                "title": "apply_mask (preset)",
                "description": (
                    "Optional preset mask for extensions.set_flags. "
                    "If omitted, caller provides apply_mask or system applies all flags."
                ),
                "additionalProperties": False,
                "required": ["active", "safe_mode", "unsafe_action_protection"],
                "properties": {
                    "active": {
                        "type": "boolean",
                        "title": "active",
                        "description": "Apply only the active flag (extension enabled/disabled).",
                        "default": False,
                    },
                    "safe_mode": {
                        "type": "boolean",
                        "title": "safe_mode",
                        "description": "Apply only the safe_mode flag.",
                        "default": False,
                    },
                    "unsafe_action_protection": {
                        "type": "boolean",
                        "title": "unsafe_action_protection",
                        "description": "Apply only the unsafe_action_protection flag.",
                        "default": False,
                    },
                },
            }
        },
    }

    fixed_ui_schema = {
        "apply_mask": {
            "active": {"ui:widget": "switch"},
            "safe_mode": {"ui:widget": "switch"},
            "unsafe_action_protection": {"ui:widget": "switch"},
        }
    }

    target_binding_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["extension_name_param"],
        "properties": {
            "extension_name_param": {
                "type": "string",
                "title": "Target command param",
                "description": "Command-level parameter name to bind runtime extension_name value.",
                "minLength": 1,
            }
        },
    }

    return {
        "fixed_schema": fixed_schema,
        "fixed_ui_schema": fixed_ui_schema,
        "target_binding_schema": target_binding_schema,
        "help": {
            "title": "Set flags presets",
            "description": "Capability-specific fields for extensions.set_flags, including target binding.",
        },
    }


@extend_schema(
    tags=["v2"],
    summary="Get operation exposure editor hints (capability UI hints)",
    description="Returns capability-driven UI hints for unified operation exposure editor (staff-only).",
    responses={
        200: ActionCatalogEditorHintsResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_operation_exposure_editor_hints(request):
    if not getattr(request.user, "is_staff", False):
        return Response(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Staff only"}},
            status=http_status.HTTP_403_FORBIDDEN,
        )

    return Response(
        {
            "hints_version": 1,
            "capabilities": {
                "extensions.set_flags": _build_extensions_set_flags_hints(),
            },
        }
    )


def _get_effective_commands_by_id(user, driver: str) -> dict[str, dict] | None:
    try:
        versions = resolve_driver_catalog_versions(driver)
        if versions.base_version is None:
            return None
        effective = get_effective_driver_catalog(
            driver=driver,
            base_version=versions.base_version,
            overrides_version=versions.overrides_version,
        )
        filtered = filter_catalog_for_user(user, effective.catalog)
        commands_by_id = filtered.get("commands_by_id")
        if isinstance(commands_by_id, dict):
            return commands_by_id
        return None
    except Exception as exc:
        logger.warning(
            "Failed to resolve effective driver catalog for action catalog",
            extra={
                "driver": str(driver),
                "error": str(exc),
            },
        )
        return None


def _filter_extensions_actions_for_user(user, actions: list[dict]) -> list[dict]:
    if not actions:
        return []

    commands_cache: dict[str, dict[str, dict] | None] = {}
    filtered_actions: list[dict] = []

    for action in actions:
        if not isinstance(action, dict):
            continue

        executor = action.get("executor")
        if not isinstance(executor, dict):
            continue

        kind = executor.get("kind")
        if kind in ("ibcmd_cli", "designer_cli"):
            driver = executor.get("driver")
            command_id = executor.get("command_id")
            if not isinstance(driver, str):
                continue
            cache_key = driver.strip().lower()
            if not cache_key:
                continue
            if not isinstance(command_id, str):
                continue
            normalized_command_id = command_id.strip()
            if not normalized_command_id:
                continue
            if cache_key not in commands_cache:
                commands_cache[cache_key] = _get_effective_commands_by_id(user, cache_key)
            commands_by_id = commands_cache.get(cache_key) or {}
            if normalized_command_id not in commands_by_id:
                continue
            filtered_actions.append(action)
            continue

        if kind == "workflow":
            workflow_id = executor.get("workflow_id")
            if not isinstance(workflow_id, str) or not workflow_id.strip():
                continue
            normalized_workflow_id = workflow_id.strip()
            try:
                workflow_uuid = uuid.UUID(normalized_workflow_id)
            except (ValueError, AttributeError):
                continue
            workflow = WorkflowTemplate.objects.filter(id=workflow_uuid).first()
            if workflow is None:
                continue
            if not workflow.is_active or not workflow.is_valid:
                continue
            if not user.has_perm(perms.PERM_TEMPLATES_EXECUTE_WORKFLOW_TEMPLATE, workflow):
                continue
            filtered_actions.append(action)
            continue

    return filtered_actions


@extend_schema(
    tags=["v2"],
    summary="Get effective action catalog",
    description="Returns effective action catalog for the current user (RBAC + driver catalogs + workflows).",
    responses={
        200: ActionCatalogResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_action_catalog(request):
    tenant_id = str(getattr(request, "tenant_id", "") or "").strip() or None
    catalog = build_effective_action_catalog_payload(tenant_id=tenant_id)
    extensions = catalog.get("extensions")
    if not isinstance(extensions, dict):
        return Response({"catalog_version": 1, "extensions": {"actions": []}})

    actions = extensions.get("actions")
    if not isinstance(actions, list):
        return Response({"catalog_version": 1, "extensions": {"actions": []}})

    filtered_actions = _filter_extensions_actions_for_user(request.user, actions)
    return Response(
        {
            "catalog_version": catalog.get("catalog_version", 1),
            "extensions": {"actions": filtered_actions},
        }
    )
