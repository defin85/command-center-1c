from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .views_common import RUNTIME_SETTINGS, RuntimeSetting, _ensure_runtime_defaults, exclude_schema


@exclude_schema
@api_view(["GET"])
@permission_classes([IsInternalService])
def list_runtime_settings(request):
    """
    GET /api/v2/internal/runtime-settings

    Get runtime settings for internal services.
    """
    _ensure_runtime_defaults()

    settings_map = {setting.key: setting for setting in RuntimeSetting.objects.all()}
    payload = []
    for definition in RUNTIME_SETTINGS.values():
        setting = settings_map.get(definition.key)
        payload.append(
            {
                "key": definition.key,
                "value": setting.value if setting else definition.default,
                "value_type": definition.value_type,
                "description": definition.description,
                "min_value": definition.min_value,
                "max_value": definition.max_value,
                "default": definition.default,
            }
        )

    return Response({"success": True, "settings": payload}, status=status.HTTP_200_OK)

