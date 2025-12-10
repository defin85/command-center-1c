"""
Django admin configuration for files app.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import UploadedFile


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    """Admin interface for UploadedFile model."""

    list_display = [
        'original_filename',
        'purpose',
        'size_display',
        'uploaded_by',
        'created_at',
        'expires_at',
        'is_expired_display',
        'is_processed',
    ]
    list_filter = [
        'purpose',
        'is_processed',
        'created_at',
    ]
    search_fields = [
        'original_filename',
        'filename',
        'uploaded_by__username',
    ]
    readonly_fields = [
        'id',
        'filename',
        'file_path',
        'size',
        'checksum',
        'created_at',
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    def size_display(self, obj):
        """Display human-readable file size."""
        return obj.size_human
    size_display.short_description = 'Size'

    def is_expired_display(self, obj):
        """Display expiration status with color."""
        if obj.is_expired:
            return format_html(
                '<span style="color: red;">Expired</span>'
            )
        return format_html(
            '<span style="color: green;">Active</span>'
        )
    is_expired_display.short_description = 'Status'

    def has_add_permission(self, request):
        """Disable adding files via admin (use API instead)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Allow limited changes."""
        return True

    def get_readonly_fields(self, request, obj=None):
        """Make most fields readonly after creation."""
        if obj:
            return self.readonly_fields + [
                'original_filename',
                'mime_type',
                'purpose',
                'uploaded_by',
            ]
        return self.readonly_fields
