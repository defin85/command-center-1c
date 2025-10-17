"""Serializers для databases app."""

from rest_framework import serializers
from .models import Database, DatabaseGroup


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
            'last_error',
            'consecutive_failures',
            'avg_response_time',
            'max_connections',
            'connection_timeout',
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
    databases_count = serializers.IntegerField(
        source='databases.count',
        read_only=True
    )

    class Meta:
        model = DatabaseGroup
        fields = [
            'id',
            'name',
            'description',
            'databases',
            'databases_count',
            'tags',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
