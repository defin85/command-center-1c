from rest_framework import serializers
from .models import OperationTemplate


class OperationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationTemplate
        fields = [
            'id', 'name', 'description', 'operation_type',
            'target_entity', 'template_data', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
