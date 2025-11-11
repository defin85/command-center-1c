"""Serializers для databases app."""

from rest_framework import serializers
from .models import Database, DatabaseGroup, ExtensionInstallation, Cluster


class DatabaseSerializer(serializers.ModelSerializer):
    """Serializer для Database model."""

    password = serializers.CharField(write_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_healthy = serializers.BooleanField(read_only=True)

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
            'is_healthy',
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
            'updated_at'
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


class ExtensionInstallationSerializer(serializers.ModelSerializer):
    """Serializer для ExtensionInstallation model."""

    database_name = serializers.CharField(source='database.name', read_only=True)
    database_id = serializers.CharField(source='database.id', read_only=True)

    class Meta:
        model = ExtensionInstallation
        fields = [
            'id', 'database_id', 'database_name', 'extension_name',
            'status', 'started_at', 'completed_at', 'error_message',
            'duration_seconds', 'retry_count', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'started_at', 'completed_at']


class ClusterSerializer(serializers.ModelSerializer):
    """Serializer для Cluster model."""

    databases_count = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    cluster_pwd = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Cluster
        fields = [
            'id',
            'name',
            'description',
            'ras_server',
            'cluster_service_url',
            'cluster_user',
            'cluster_pwd',  # write-only
            'status',
            'status_display',
            'last_sync',
            'metadata',
            'databases_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'last_sync', 'created_at', 'updated_at']

