"""
Runtime settings endpoints for API v2.
"""
import logging

from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.runtime_settings.models import RuntimeSetting
from apps.runtime_settings.registry import RUNTIME_SETTINGS
from apps.runtime_settings.action_catalog import UI_ACTION_CATALOG_KEY, validate_action_catalog_references, validate_action_catalog_v1

logger = logging.getLogger(__name__)


class RuntimeSettingSerializer(serializers.Serializer):
    key = serializers.CharField()
    value = serializers.JSONField()
    value_type = serializers.CharField()
    description = serializers.CharField()
    min_value = serializers.IntegerField(required=False, allow_null=True)
    max_value = serializers.IntegerField(required=False, allow_null=True)
    default = serializers.JSONField()


class RuntimeSettingsResponseSerializer(serializers.Serializer):
    settings = RuntimeSettingSerializer(many=True)


class RuntimeSettingUpdateSerializer(serializers.Serializer):
    value = serializers.JSONField()


def _ensure_defaults():
    for definition in RUNTIME_SETTINGS.values():
        RuntimeSetting.objects.get_or_create(
            key=definition.key,
            defaults={"value": definition.default},
        )


def _validate_value(definition, value):
    if definition.value_type == "int":
        if isinstance(value, bool):
            raise serializers.ValidationError("value must be integer")
        if isinstance(value, float):
            if not value.is_integer():
                raise serializers.ValidationError("value must be integer")
            value = int(value)
        if not isinstance(value, int):
            raise serializers.ValidationError("value must be integer")
        if definition.min_value is not None and value < definition.min_value:
            raise serializers.ValidationError("value below minimum")
        if definition.max_value is not None and value > definition.max_value:
            raise serializers.ValidationError("value above maximum")
        return value
    if definition.value_type == "bool":
        if not isinstance(value, bool):
            raise serializers.ValidationError("value must be boolean")
        return value
    if definition.value_type == "string":
        if not isinstance(value, str):
            raise serializers.ValidationError("value must be string")
        return value
    return value


@extend_schema(
    tags=['v2'],
    summary='List runtime settings',
    description='List runtime-configurable settings for SPA and operations.',
    responses={
        200: RuntimeSettingsResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_runtime_settings(request):
    if not request.user.is_staff:
        return Response(
            {'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Staff only'}},
            status=status.HTTP_403_FORBIDDEN
        )

    _ensure_defaults()

    settings_map = {setting.key: setting for setting in RuntimeSetting.objects.all()}
    payload = []
    for definition in RUNTIME_SETTINGS.values():
        setting = settings_map.get(definition.key)
        payload.append({
            "key": definition.key,
            "value": setting.value if setting else definition.default,
            "value_type": definition.value_type,
            "description": definition.description,
            "min_value": definition.min_value,
            "max_value": definition.max_value,
            "default": definition.default,
        })

    return Response({"settings": payload})


@extend_schema(
    tags=['v2'],
    summary='Update runtime setting',
    description='Update a runtime-configurable setting.',
    parameters=[
        OpenApiParameter(
            name='key',
            type=str,
            required=True,
            description='Setting key'
        ),
    ],
    request=RuntimeSettingUpdateSerializer,
    responses={
        200: RuntimeSettingSerializer,
        400: OpenApiResponse(description='Validation error'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Not found'),
    }
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_runtime_setting(request, key: str):
    if not request.user.is_staff:
        return Response(
            {'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Staff only'}},
            status=status.HTTP_403_FORBIDDEN
        )

    definition = RUNTIME_SETTINGS.get(key)
    if not definition:
        return Response(
            {'success': False, 'error': {'code': 'NOT_FOUND', 'message': 'Setting not found'}},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = RuntimeSettingUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST
        )

    value = serializer.validated_data['value']
    try:
        value = _validate_value(definition, value)
    except serializers.ValidationError as exc:
        return Response(
            {'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': exc.detail}},
            status=status.HTTP_400_BAD_REQUEST
        )

    if definition.key == UI_ACTION_CATALOG_KEY:
        schema_errors = validate_action_catalog_v1(value)
        if schema_errors:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": [err.to_text() for err in schema_errors],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ref_errors = validate_action_catalog_references(value)
        if ref_errors:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": [err.to_text() for err in ref_errors],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    setting, _ = RuntimeSetting.objects.get_or_create(
        key=definition.key,
        defaults={"value": definition.default},
    )
    setting.value = value
    setting.save(update_fields=['value', 'updated_at'])

    return Response({
        "key": definition.key,
        "value": setting.value,
        "value_type": definition.value_type,
        "description": definition.description,
        "min_value": definition.min_value,
        "max_value": definition.max_value,
        "default": definition.default,
    })
