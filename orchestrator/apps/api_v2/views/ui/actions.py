"""UI action catalog endpoint."""

from __future__ import annotations

import logging
import uuid

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.operations.driver_catalog_effective import (
    filter_catalog_for_user,
    get_effective_driver_catalog,
    resolve_driver_catalog_versions,
)
from apps.runtime_settings.action_catalog import UI_ACTION_CATALOG_KEY, ensure_valid_action_catalog
from apps.runtime_settings.models import RuntimeSetting
from apps.templates.workflow.models import WorkflowTemplate

logger = logging.getLogger(__name__)


class ActionCatalogResponseSerializer(serializers.Serializer):
    catalog_version = serializers.IntegerField()
    extensions = serializers.DictField()


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
    raw = RuntimeSetting.objects.filter(key=UI_ACTION_CATALOG_KEY).values_list("value", flat=True).first()
    catalog, errors = ensure_valid_action_catalog(raw)
    if errors:
        logger.warning(
            "ui.action_catalog is invalid; failing closed",
            extra={
                "error_count": len(errors),
                "errors": [err.to_text() for err in errors[:10]],
            },
        )

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


