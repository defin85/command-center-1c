"""
UI metadata endpoints for API v2.

Provides server-driven table metadata for dynamic UI configuration.
"""

from rest_framework import serializers

_SENSITIVE_KEYS: set[str] = {
    "db_password",
    "db_pwd",
    "password",
    "secret",
    "token",
    "api_key",
    "access_key",
    "secret_key",
    "stdin",
}


def _is_sensitive_key(key: str) -> bool:
    key_norm = (key or "").strip().lower()
    if not key_norm:
        return False
    if key_norm in _SENSITIVE_KEYS:
        return True
    if key_norm.endswith("_password") or key_norm.endswith("_pwd"):
        return True
    return False


def _mask_json_value(value):
    if isinstance(value, dict):
        return _mask_json_dict(value)
    if isinstance(value, list):
        return [_mask_json_value(item) for item in value]
    return value


def _mask_json_dict(data: dict):
    masked: dict = {}
    for key, value in data.items():
        key_str = str(key or "")
        if _is_sensitive_key(key_str):
            masked[key] = "***"
            continue
        masked[key] = _mask_json_value(value)
    return masked


class UiErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")


class UiErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = UiErrorDetailSerializer()
    request_id = serializers.CharField()
    ui_action_id = serializers.CharField(required=False)


class TableFilterOptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class TableFilterMetadataSerializer(serializers.Serializer):
    type = serializers.CharField()
    operators = serializers.ListField(child=serializers.CharField(), required=False)
    options = TableFilterOptionSerializer(many=True, required=False)
    placeholder = serializers.CharField(required=False)


class TableColumnMetadataSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    group_key = serializers.CharField(required=False, allow_null=True)
    group_label = serializers.CharField(required=False, allow_null=True)
    sortable = serializers.BooleanField(default=False)
    data_type = serializers.CharField(required=False)
    filter = TableFilterMetadataSerializer(required=False)
    server_field = serializers.CharField(required=False)


class TableMetadataResponseSerializer(serializers.Serializer):
    table_id = serializers.CharField()
    version = serializers.CharField()
    columns = TableColumnMetadataSerializer(many=True)
