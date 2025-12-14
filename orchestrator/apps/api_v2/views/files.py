"""
File upload endpoints for API v2.

Provides secure file upload, download, and deletion.
"""

import logging
import uuid

from django.http import FileResponse
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, parser_classes, throttle_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.files.models import UploadedFile, FilePurpose
from apps.files.services import FileStorageService
from apps.api_v2.serializers.common import ErrorResponseSerializer


logger = logging.getLogger(__name__)


# =============================================================================
# Throttling
# =============================================================================

class FileUploadThrottle(UserRateThrottle):
    """Rate limit for file uploads: 20 per hour per user."""
    rate = '20/hour'


# =============================================================================
# Serializers
# =============================================================================

class UploadedFileSerializer(serializers.Serializer):
    """Serializer for UploadedFile response."""

    id = serializers.UUIDField()
    filename = serializers.CharField()
    original_filename = serializers.CharField()
    size = serializers.IntegerField()
    size_human = serializers.CharField()
    mime_type = serializers.CharField()
    purpose = serializers.CharField()
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    is_processed = serializers.BooleanField()
    checksum = serializers.CharField()


class FileUploadResponseSerializer(serializers.Serializer):
    """Response for file upload endpoint."""

    file = UploadedFileSerializer()
    message = serializers.CharField()


class FileDeleteResponseSerializer(serializers.Serializer):
    """Response for file delete endpoint."""

    file_id = serializers.UUIDField()
    deleted = serializers.BooleanField()
    message = serializers.CharField()


# =============================================================================
# Endpoints
# =============================================================================

@extend_schema(
    tags=['v2'],
    summary='Upload file',
    description='Upload a file for use in operations. Supports operation_input, extension, and export purposes.',
    parameters=[
        OpenApiParameter(
            name='purpose',
            type=str,
            required=True,
            description='File purpose: operation_input, extension, export'
        ),
        OpenApiParameter(
            name='expiry_hours',
            type=int,
            required=False,
            description='Custom expiration hours (default: 24)'
        ),
    ],
    responses={
        201: FileUploadResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        413: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([FileUploadThrottle])
@parser_classes([MultiPartParser])
def upload_file(request):
    """
    POST /api/v2/files/upload/

    Upload a file for operations.

    Form Data:
        - file: The file to upload (multipart/form-data)
        - purpose: File purpose (operation_input, extension, export)
        - expiry_hours: Optional custom expiration (default: 24)

    Response (201):
        {
            "file": {...},
            "message": "File uploaded successfully"
        }
    """
    # Get file from request
    file = request.FILES.get('file')
    if not file:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_FILE',
                'message': 'No file provided in request'
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get purpose
    purpose = request.data.get('purpose')
    if not purpose:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'purpose is required'
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validate purpose
    valid_purposes = [choice[0] for choice in FilePurpose.choices]
    if purpose not in valid_purposes:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_PURPOSE',
                'message': f'purpose must be one of: {", ".join(valid_purposes)}'
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get optional expiry hours
    from django.conf import settings
    max_expiry = getattr(settings, 'FILE_UPLOAD_MAX_EXPIRY_HOURS', 168)

    expiry_hours = request.data.get('expiry_hours')
    if expiry_hours:
        try:
            expiry_hours = int(expiry_hours)
            if expiry_hours < 1 or expiry_hours > max_expiry:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_EXPIRY',
                        'message': f'expiry_hours must be between 1 and {max_expiry}'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            expiry_hours = None

    try:
        # Save file
        uploaded_file = FileStorageService.save_file(
            file=file,
            purpose=purpose,
            uploaded_by=request.user,
            expiry_hours=expiry_hours,
        )

        logger.info(
            f"File uploaded: {uploaded_file.original_filename}",
            extra={
                'file_id': str(uploaded_file.id),
                'user': request.user.username,
                'purpose': purpose,
                'size': uploaded_file.size,
            }
        )

        serializer = UploadedFileSerializer(uploaded_file)

        return Response({
            'file': serializer.data,
            'message': 'File uploaded successfully',
        }, status=status.HTTP_201_CREATED)

    except ValueError as e:
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(e)
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception(f"File upload failed: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'UPLOAD_ERROR',
                'message': 'Failed to upload file'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['v2'],
    summary='Download file',
    description='Download a previously uploaded file.',
    parameters=[
        OpenApiParameter(
            name='file_id',
            type=str,
            location=OpenApiParameter.PATH,
            required=True,
            description='File UUID'
        ),
    ],
    responses={
        200: OpenApiResponse(description='File content'),
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        410: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_file(request, file_id):
    """
    GET /api/v2/files/download/<file_id>/

    Download a file by ID.

    Path Parameters:
        - file_id: File UUID

    Response:
        File content with appropriate Content-Type and Content-Disposition headers.
    """
    # Validate UUID format
    try:
        file_uuid = uuid.UUID(str(file_id))
    except ValueError:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_UUID',
                'message': 'file_id must be a valid UUID'
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get file record
    try:
        uploaded_file = UploadedFile.objects.get(id=file_uuid)
    except UploadedFile.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': 'File not found'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    # Check ownership (IDOR protection)
    if uploaded_file.uploaded_by != request.user and not request.user.is_staff:
        return Response({
            'success': False,
            'error': {
                'code': 'PERMISSION_DENIED',
                'message': 'You do not have permission to access this file'
            }
        }, status=status.HTTP_403_FORBIDDEN)

    # Check if expired
    if uploaded_file.is_expired:
        return Response({
            'success': False,
            'error': {
                'code': 'FILE_EXPIRED',
                'message': 'File has expired and is no longer available'
            }
        }, status=status.HTTP_410_GONE)

    # Get file path with path traversal protection
    try:
        file_path_str = uploaded_file.get_absolute_path()
    except ValueError as e:
        logger.error(f"Path traversal attempt detected for file {file_uuid}: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_PATH',
                'message': 'Invalid file path'
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    from pathlib import Path
    file_path = Path(file_path_str)

    # Check file exists and is a regular file before opening
    if not file_path.exists() or not file_path.is_file():
        logger.error(f"File not found on disk: {file_path}")
        return Response({
            'success': False,
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': 'File not found on storage'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=uploaded_file.mime_type,
        )

        # RFC 6266 compliant Content-Disposition with UTF-8 encoding
        from urllib.parse import quote
        safe_filename = uploaded_file.filename  # sanitized version
        encoded_filename = quote(safe_filename)
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
        response['Content-Length'] = uploaded_file.size

        logger.info(
            f"File downloaded: {uploaded_file.original_filename}",
            extra={
                'file_id': str(file_uuid),
                'user': request.user.username,
            }
        )

        return response

    except FileNotFoundError:
        logger.error(f"File not found on disk: {file_path}")
        return Response({
            'success': False,
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': 'File not found on storage'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.exception(f"File download failed: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'DOWNLOAD_ERROR',
                'message': 'Failed to download file'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['v2'],
    summary='Delete file',
    description='Delete a previously uploaded file.',
    parameters=[
        OpenApiParameter(
            name='file_id',
            type=str,
            location=OpenApiParameter.PATH,
            required=True,
            description='File UUID'
        ),
    ],
    responses={
        200: FileDeleteResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_file(request, file_id):
    """
    DELETE /api/v2/files/delete/<file_id>/

    Delete a file by ID.

    Path Parameters:
        - file_id: File UUID

    Response:
        {
            "file_id": "uuid",
            "deleted": true,
            "message": "File deleted successfully"
        }
    """
    # Validate UUID format
    try:
        file_uuid = uuid.UUID(str(file_id))
    except ValueError:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_UUID',
                'message': 'file_id must be a valid UUID'
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check file exists
    try:
        uploaded_file = UploadedFile.objects.get(id=file_uuid)
        original_filename = uploaded_file.original_filename
    except UploadedFile.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': 'File not found'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    # Check ownership (IDOR protection)
    if uploaded_file.uploaded_by != request.user and not request.user.is_staff:
        return Response({
            'success': False,
            'error': {
                'code': 'PERMISSION_DENIED',
                'message': 'You do not have permission to delete this file'
            }
        }, status=status.HTTP_403_FORBIDDEN)

    # Delete file
    deleted = FileStorageService.delete_file(file_uuid)

    if deleted:
        logger.info(
            f"File deleted: {original_filename}",
            extra={
                'file_id': str(file_uuid),
                'user': request.user.username,
            }
        )

        return Response({
            'file_id': str(file_uuid),
            'deleted': True,
            'message': 'File deleted successfully',
        })
    else:
        return Response({
            'success': False,
            'error': {
                'code': 'DELETE_FAILED',
                'message': 'Failed to delete file'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
