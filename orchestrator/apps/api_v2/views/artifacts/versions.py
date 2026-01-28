from __future__ import annotations

from .common import *  # noqa: F403
from .common import _ensure_permission, _get_active_artifact

@extend_schema(
    tags=["v2"],
    summary="Upload artifact version",
    request=ArtifactVersionUploadRequestSerializer,
    responses={
        201: ArtifactVersionSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        500: ErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_artifact_version(request, artifact_id):
    artifact = _get_active_artifact(artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_UPLOAD_ARTIFACT_VERSION,
        obj=artifact,
        message="You do not have permission to upload artifact versions.",
    )
    if denied:
        return denied

    file = request.FILES.get("file")
    if not file:
        return Response(
            {"success": False, "error": {"code": "MISSING_FILE", "message": "No file provided"}},
            status=400,
        )

    if file.size > settings.FILE_UPLOAD_MAX_SIZE:
        return Response(
            {
                "success": False,
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": "File too large",
                },
            },
            status=400,
        )

    filename = request.data.get("filename") or file.name
    filename = FileStorageService.sanitize_filename(filename)
    version = request.data.get("version")
    metadata = ArtifactService.parse_metadata(request.data.get("metadata"))

    if ArtifactVersion.objects.filter(filename=filename).exists():
        return Response(
            {
                "success": False,
                "error": {"code": "FILENAME_EXISTS", "message": "Filename already exists"},
            },
            status=400,
        )

    try:
        version_obj = ArtifactService.create_version(
            artifact=artifact,
            file_obj=file,
            filename=filename,
            version=version,
            metadata=metadata,
            content_type=getattr(file, "content_type", None),
            created_by=request.user,
        )
    except ValueError as exc:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
            status=400,
        )
    except IntegrityError:
        return Response(
            {"success": False, "error": {"code": "DUPLICATE", "message": "Artifact version already exists"}},
            status=400,
        )
    except ArtifactStorageError as exc:
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )

    serializer = ArtifactVersionSerializer(version_obj)
    return Response(serializer.data, status=201)


@extend_schema(
    tags=["v2"],
    summary="List artifact versions",
    responses={
        200: ArtifactVersionListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_artifact_versions(request, artifact_id):
    artifact = _get_active_artifact(artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_VIEW_ARTIFACT,
        obj=artifact,
        message="You do not have permission to access this artifact.",
    )
    if denied:
        return denied

    versions = list(artifact.versions.order_by("-created_at"))
    response = ArtifactVersionListResponseSerializer({"versions": versions, "count": len(versions)})
    return Response(response.data)


@extend_schema(
    tags=["v2"],
    summary="Upsert artifact alias",
    request=ArtifactAliasUpsertRequestSerializer,
    responses={
        200: ArtifactAliasSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_artifact_alias(request, artifact_id):
    artifact = _get_active_artifact(artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_MANAGE_ARTIFACT,
        obj=artifact,
        message="You do not have permission to manage this artifact.",
    )
    if denied:
        return denied

    serializer = ArtifactAliasUpsertRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": serializer.errors},
            status=400,
        )

    data = serializer.validated_data
    version_obj = None
    if data.get("version_id"):
        version_obj = get_object_or_404(ArtifactVersion, id=data["version_id"], artifact=artifact)
    elif data.get("version"):
        version_obj = get_object_or_404(ArtifactVersion, artifact=artifact, version=data["version"])

    alias_obj, _ = ArtifactAlias.objects.update_or_create(
        artifact=artifact,
        alias=data["alias"],
        defaults={"version": version_obj},
    )

    response = ArtifactAliasSerializer(
        {
            "id": alias_obj.id,
            "alias": alias_obj.alias,
            "version": alias_obj.version.version,
            "version_id": alias_obj.version.id,
            "updated_at": alias_obj.updated_at,
        }
    )
    return Response(response.data)


@extend_schema(
    tags=["v2"],
    summary="List artifact aliases",
    responses={
        200: ArtifactAliasListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_artifact_aliases(request, artifact_id):
    artifact = _get_active_artifact(artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_VIEW_ARTIFACT,
        obj=artifact,
        message="You do not have permission to access this artifact.",
    )
    if denied:
        return denied

    aliases = list(artifact.aliases.select_related("version").order_by("alias"))
    response = ArtifactAliasListResponseSerializer(
        {
            "aliases": [
                {
                    "id": alias.id,
                    "alias": alias.alias,
                    "version": alias.version.version,
                    "version_id": alias.version.id,
                    "updated_at": alias.updated_at,
                }
                for alias in aliases
            ],
            "count": len(aliases),
        }
    )
    return Response(response.data)


@extend_schema(
    tags=["v2"],
    summary="Download artifact version",
    responses={
        200: OpenApiResponse(description="File download"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_artifact_version(request, artifact_id, version):
    artifact = _get_active_artifact(artifact_id)
    version_obj = get_object_or_404(ArtifactVersion, artifact=artifact, version=version)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_DOWNLOAD_ARTIFACT_VERSION,
        obj=version_obj,
        message="You do not have permission to download this artifact version.",
    )
    if denied:
        return denied

    storage = ArtifactStorageClient()
    try:
        data = storage.get_object(version_obj.storage_key)
    except ArtifactStorageError as exc:
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )

    response = FileResponse(data, as_attachment=True, filename=version_obj.filename)
    response["Content-Type"] = version_obj.content_type or "application/octet-stream"
    return response

