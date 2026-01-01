"""Serializers для databases app."""

from typing import Optional

from rest_framework import serializers
from .models import Database, DatabaseGroup, Cluster, InfobaseUserMapping


class DatabaseSerializer(serializers.ModelSerializer):
    """Serializer для Database model."""

    password = serializers.CharField(write_only=True)
    password_configured = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_healthy = serializers.BooleanField(read_only=True)
    sessions_deny = serializers.SerializerMethodField()
    scheduled_jobs_deny = serializers.SerializerMethodField()
    denied_from = serializers.SerializerMethodField()
    denied_to = serializers.SerializerMethodField()
    denied_message = serializers.SerializerMethodField()
    permission_code = serializers.SerializerMethodField()
    denied_parameter = serializers.SerializerMethodField()
    last_health_error = serializers.SerializerMethodField()
    last_health_error_code = serializers.SerializerMethodField()

    def _get_metadata_value(self, obj: Database, key: str) -> Optional[object]:
        metadata = obj.metadata or {}
        if isinstance(metadata, dict):
            return metadata.get(key)
        return None

    def get_sessions_deny(self, obj: Database) -> Optional[bool]:
        return self._get_metadata_value(obj, 'sessions_deny')

    def get_scheduled_jobs_deny(self, obj: Database) -> Optional[bool]:
        return self._get_metadata_value(obj, 'scheduled_jobs_deny')

    def get_denied_from(self, obj: Database) -> Optional[str]:
        return self._get_metadata_value(obj, 'denied_from')

    def get_denied_to(self, obj: Database) -> Optional[str]:
        return self._get_metadata_value(obj, 'denied_to')

    def get_denied_message(self, obj: Database) -> Optional[str]:
        return self._get_metadata_value(obj, 'denied_message')

    def get_permission_code(self, obj: Database) -> Optional[str]:
        return self._get_metadata_value(obj, 'permission_code')

    def get_denied_parameter(self, obj: Database) -> Optional[str]:
        return self._get_metadata_value(obj, 'denied_parameter')

    def get_last_health_error(self, obj: Database) -> Optional[str]:
        return self._get_metadata_value(obj, 'last_health_error')

    def get_last_health_error_code(self, obj: Database) -> Optional[str]:
        return self._get_metadata_value(obj, 'last_health_error_code')

    def get_password_configured(self, obj: Database) -> bool:
        return bool(obj.password)

    class Meta:
        model = Database
        fields = [
            'id',
            'name',
            'description',
            'host',
            'port',
            'base_name',
            'odata_url',
            'username',
            'password',  # write-only
            'password_configured',
            'server_address',
            'server_port',
            'infobase_name',
            'status',
            'status_display',
            'version',
            'last_check',
            'last_check_status',
            'consecutive_failures',
            'avg_response_time',
            'max_connections',
            'connection_timeout',
            'health_check_enabled',
            'cluster_id',
            'is_healthy',
            'sessions_deny',
            'scheduled_jobs_deny',
            'denied_from',
            'denied_to',
            'denied_message',
            'permission_code',
            'denied_parameter',
            'last_health_error',
            'last_health_error_code',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'last_check',
            'last_check_status',
            'consecutive_failures',
            'avg_response_time',
            'created_at',
            'updated_at',
            'password_configured',
            'server_address',
            'server_port',
            'infobase_name',
        ]


class DatabaseGroupSerializer(serializers.ModelSerializer):
    """Serializer для DatabaseGroup model."""

    databases = DatabaseSerializer(many=True, read_only=True)
    database_count = serializers.IntegerField(read_only=True)
    healthy_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DatabaseGroup
        fields = [
            'id',
            'name',
            'description',
            'databases',
            'database_count',
            'healthy_count',
            'metadata',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClusterSerializer(serializers.ModelSerializer):
    """Serializer для Cluster model."""

    databases_count = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    cluster_pwd = serializers.CharField(write_only=True, required=False, allow_blank=True)
    cluster_pwd_configured = serializers.SerializerMethodField()
    ras_server = serializers.CharField(read_only=True)

    def get_cluster_pwd_configured(self, obj: Cluster) -> bool:
        return bool(obj.cluster_pwd)

    class Meta:
        model = Cluster
        fields = [
            'id',
            'name',
            'description',
            'ras_host',
            'ras_port',
            'ras_server',
            'rmngr_host',
            'rmngr_port',
            'ragent_host',
            'ragent_port',
            'rphost_port_from',
            'rphost_port_to',
            'cluster_service_url',
            'cluster_user',
            'cluster_pwd',  # write-only
            'cluster_pwd_configured',
            'status',
            'status_display',
            'last_sync',
            'metadata',
            'databases_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'ras_server',
            'last_sync',
            'created_at',
            'updated_at',
            'cluster_pwd_configured',
        ]

    def validate(self, attrs):
        if self.instance is None:
            ras_host = attrs.get('ras_host')
            ras_port = attrs.get('ras_port')
            rmngr_host = attrs.get('rmngr_host')
            rmngr_port = attrs.get('rmngr_port')
            missing = []
            if not ras_host:
                missing.append('ras_host')
            if not ras_port:
                missing.append('ras_port')
            if not rmngr_host:
                missing.append('rmngr_host')
            if not rmngr_port:
                missing.append('rmngr_port')
            if missing:
                raise serializers.ValidationError(
                    {key: 'This field is required.' for key in missing}
                )
        return attrs

    def _apply_ras_server(self, attrs):
        ras_host = attrs.get('ras_host') or (self.instance.ras_host if self.instance else "")
        ras_port = attrs.get('ras_port') or (self.instance.ras_port if self.instance else None)
        if ras_host and ras_port:
            attrs['ras_server'] = f"{ras_host}:{ras_port}"
        return attrs

    def create(self, validated_data):
        validated_data = self._apply_ras_server(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._apply_ras_server(validated_data)
        return super().update(instance, validated_data)


class UserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class InfobaseUserMappingSerializer(serializers.ModelSerializer):
    user = UserRefSerializer(allow_null=True, required=False)
    ib_password_configured = serializers.SerializerMethodField()

    class Meta:
        model = InfobaseUserMapping
        fields = [
            'id',
            'database_id',
            'user',
            'ib_username',
            'ib_display_name',
            'ib_roles',
            'ib_password_configured',
            'auth_type',
            'is_service',
            'notes',
            'created_at',
            'updated_at',
        ]

    def get_ib_password_configured(self, obj: InfobaseUserMapping) -> bool:
        return bool(obj.ib_password)


class InfobaseUserMappingCreateSerializer(serializers.Serializer):
    database_id = serializers.CharField()
    user_id = serializers.IntegerField(required=False, allow_null=True)
    ib_username = serializers.CharField()
    ib_display_name = serializers.CharField(required=False, allow_blank=True)
    ib_roles = serializers.ListField(child=serializers.CharField(), required=False)
    ib_password = serializers.CharField(required=False, allow_blank=False, write_only=True)
    auth_type = serializers.ChoiceField(
        choices=InfobaseUserMapping._meta.get_field('auth_type').choices,
        required=False,
    )
    is_service = serializers.BooleanField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class InfobaseUserMappingUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField(required=False, allow_null=True)
    ib_username = serializers.CharField(required=False)
    ib_display_name = serializers.CharField(required=False, allow_blank=True)
    ib_roles = serializers.ListField(child=serializers.CharField(), required=False)
    auth_type = serializers.ChoiceField(
        choices=InfobaseUserMapping._meta.get_field('auth_type').choices,
        required=False,
    )
    is_service = serializers.BooleanField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class InfobaseUserMappingDeleteSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class InfobaseUserPasswordSetSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    password = serializers.CharField(write_only=True)


class InfobaseUserPasswordResetSerializer(serializers.Serializer):
    id = serializers.IntegerField()
