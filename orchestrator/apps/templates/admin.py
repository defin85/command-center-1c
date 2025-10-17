from django.contrib import admin
from .models import OperationTemplate


@admin.register(OperationTemplate)
class OperationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'operation_type', 'target_entity', 'is_active', 'created_at']
    list_filter = ['operation_type', 'is_active', 'created_at']
    search_fields = ['name', 'target_entity']
    readonly_fields = ['id', 'created_at', 'updated_at']
