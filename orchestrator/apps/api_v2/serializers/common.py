"""
Common serializers for API v2.

Provides reusable serializers for error responses and other shared structures.
"""

from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""

    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""

    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()
