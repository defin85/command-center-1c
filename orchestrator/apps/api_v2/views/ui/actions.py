"""UI operation exposure metadata endpoints."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
        "target_binding_schema": target_binding_schema,
        "help": {
            "title": "Runtime source for set_flags values",
            "description": (
                "extensions.set_flags stores only transport/binding in action catalog. "
                "Flag values are provided at launch via flags_values ($flags.* tokens)."
            ),
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
