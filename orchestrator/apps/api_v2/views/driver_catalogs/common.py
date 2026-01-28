"""
Command Schemas management endpoints (staff-only).

Supports:
- schema-driven command catalogs (cli/ibcmd) stored as versioned artifacts
- guided and raw editing flows for base/overrides/effective
"""

from __future__ import annotations

import copy
import json

from rest_framework import status as http_status
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.artifacts.models import ArtifactAlias, ArtifactVersion
from apps.core import permission_codes as perms
from apps.operations.cli_catalog import (
    build_cli_catalog_from_its,
    validate_cli_catalog,
)
from apps.operations.ibcmd_catalog_v2 import build_base_catalog_from_its as build_ibcmd_catalog_v2_from_its
from apps.operations.ibcmd_catalog_v2 import validate_catalog_v2 as validate_ibcmd_catalog_v2
from apps.operations.driver_catalog_artifacts import (
    build_empty_overrides_catalog,
    get_or_create_catalog_artifacts,
    promote_base_alias,
    upload_base_catalog_version,
    upload_overrides_catalog_version,
)
from apps.operations.driver_catalog_v2 import cli_catalog_v1_to_v2
from apps.operations.driver_catalog_effective import (
    compute_driver_catalog_etag,
    get_effective_driver_catalog,
    invalidate_driver_catalog_cache,
    load_catalog_json,
)
from apps.operations.ibcmd_cli_builder import (
    build_ibcmd_cli_argv,
    build_ibcmd_cli_argv_manual,
    build_ibcmd_connection_args,
    detect_connection_option_conflicts,
    flatten_connection_params,
    mask_argv,
)
from apps.operations.models import AdminActionAuditLog
from apps.operations.services.admin_action_audit import log_admin_action
from apps.operations.prometheus_metrics import (
    record_driver_catalog_editor_conflict,
    record_driver_catalog_editor_validation_failed,
    record_driver_catalog_editor_error,
)
from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.artifacts.storage import ArtifactStorageError

COMMAND_SCHEMA_DRIVERS = {
    "cli": {
        "supports_guided": True,
        "supports_raw_base_edit": True,
        "supports_raw_overrides_edit": True,
        "supports_raw_effective_edit": True,
        "supports_import_its": True,
    },
    "ibcmd": {
        "supports_guided": True,
        "supports_raw_base_edit": True,
        "supports_raw_overrides_edit": True,
        "supports_raw_effective_edit": True,
        "supports_import_its": True,
    },
}

COMMAND_SCHEMA_DRIVER_CHOICES = tuple(COMMAND_SCHEMA_DRIVERS.keys())


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=http_status.HTTP_403_FORBIDDEN,
    )


def _ensure_manage_driver_catalogs(request, *, action: str | None = None):
    user = request.user
    if getattr(user, "is_superuser", False):
        return None

    all_permissions = user.get_all_permissions()
    if perms.PERM_OPERATIONS_MANAGE_DRIVER_CATALOGS in all_permissions:
        return None

    record_driver_catalog_editor_error("unknown", action=action or "permission_denied", code="PERMISSION_DENIED")
    return _permission_denied("You do not have permission to manage driver catalogs.")


class CommandSchemasEditorViewResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    etag = serializers.CharField()
    base = serializers.DictField()
    overrides = serializers.DictField()
    catalogs = serializers.DictField()


class CommandSchemasVersionsListResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    artifact = serializers.CharField()
    versions = serializers.ListField(child=serializers.DictField())
    count = serializers.IntegerField()


class CommandSchemasOverridesUpdateRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=COMMAND_SCHEMA_DRIVER_CHOICES)
    catalog = serializers.DictField()
    reason = serializers.CharField()
    expected_etag = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CommandSchemasOverridesUpdateResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    overrides_version = serializers.CharField()
    etag = serializers.CharField()


class CommandSchemasOverridesRollbackRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=COMMAND_SCHEMA_DRIVER_CHOICES)
    version = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    version_id = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField()
    expected_etag = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        if attrs.get("version_id") is None and not str(attrs.get("version") or "").strip():
            raise serializers.ValidationError("version or version_id is required")
        return attrs


class CommandSchemasOverridesRollbackResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    overrides_version = serializers.CharField()
    etag = serializers.CharField()


class CommandSchemasImportRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=COMMAND_SCHEMA_DRIVER_CHOICES, default="cli")
    its_payload = serializers.DictField()
    save = serializers.BooleanField(default=True)
    reason = serializers.CharField()


class CommandSchemasImportResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    catalog = serializers.DictField()


class CommandSchemasPromoteRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=COMMAND_SCHEMA_DRIVER_CHOICES)
    version = serializers.CharField()
    alias = serializers.CharField(required=False, default="approved")
    reason = serializers.CharField()


class CommandSchemasPromoteResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    alias = serializers.CharField()
    version = serializers.CharField()


class CommandSchemasBaseUpdateRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=COMMAND_SCHEMA_DRIVER_CHOICES)
    catalog = serializers.DictField()
    reason = serializers.CharField()
    expected_etag = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CommandSchemasBaseUpdateResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    base_version = serializers.CharField()
    etag = serializers.CharField()


class CommandSchemasEffectiveUpdateRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=COMMAND_SCHEMA_DRIVER_CHOICES)
    catalog = serializers.DictField()
    reason = serializers.CharField()
    expected_etag = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CommandSchemasEffectiveUpdateResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    base_version = serializers.CharField()
    overrides_version = serializers.CharField()
    etag = serializers.CharField()


class CommandSchemasIssueSerializer(serializers.Serializer):
    severity = serializers.ChoiceField(choices=["error", "warning"])
    code = serializers.CharField()
    message = serializers.CharField()
    command_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    path = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class CommandSchemasValidateRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=COMMAND_SCHEMA_DRIVER_CHOICES)
    catalog = serializers.DictField(required=False, allow_null=True)
    effective_catalog = serializers.DictField(required=False, allow_null=True)


class CommandSchemasValidateResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    ok = serializers.BooleanField()
    base_version = serializers.CharField(allow_null=True)
    base_version_id = serializers.CharField(allow_null=True)
    overrides_version = serializers.CharField(allow_null=True)
    overrides_version_id = serializers.CharField(allow_null=True)
    issues = CommandSchemasIssueSerializer(many=True)
    errors_count = serializers.IntegerField()
    warnings_count = serializers.IntegerField()


class CommandSchemasPreviewRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=COMMAND_SCHEMA_DRIVER_CHOICES)
    command_id = serializers.CharField()
    mode = serializers.ChoiceField(choices=["guided", "manual"], default="guided")
    connection = serializers.DictField(required=False, allow_null=True, default=dict)
    params = serializers.DictField(required=False, default=dict)
    additional_args = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    catalog = serializers.DictField(required=False, allow_null=True)


class CommandSchemasPreviewResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    command_id = serializers.CharField()
    argv = serializers.ListField(child=serializers.CharField())
    argv_masked = serializers.ListField(child=serializers.CharField())
    risk_level = serializers.CharField(required=False, allow_null=True)
    scope = serializers.CharField(required=False, allow_null=True)
    disabled = serializers.BooleanField(required=False, allow_null=True)


class CommandSchemasDiffRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=COMMAND_SCHEMA_DRIVER_CHOICES)
    command_id = serializers.CharField()
    catalog = serializers.DictField(required=False, allow_null=True)


class CommandSchemasDiffItemSerializer(serializers.Serializer):
    path = serializers.CharField()
    base_present = serializers.BooleanField()
    base = serializers.JSONField(required=False, allow_null=True)
    effective_present = serializers.BooleanField()
    effective = serializers.JSONField(required=False, allow_null=True)


class CommandSchemasDiffResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    command_id = serializers.CharField()
    has_overrides = serializers.BooleanField()
    changes = CommandSchemasDiffItemSerializer(many=True)
    count = serializers.IntegerField()


class CommandSchemasAuditLogItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    action = serializers.CharField()
    outcome = serializers.CharField()
    actor_username = serializers.CharField()
    target_type = serializers.CharField()
    target_id = serializers.CharField()
    metadata = serializers.DictField()
    error_message = serializers.CharField()


class CommandSchemasAuditListResponseSerializer(serializers.Serializer):
    items = CommandSchemasAuditLogItemSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()



