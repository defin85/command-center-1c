"""DBMS metadata endpoints (Database.metadata)."""

from __future__ import annotations

from .common import *  # noqa: F403
from .common import _permission_denied


@extend_schema(
    tags=["v2"],
    summary="Update database DBMS metadata",
    description="Set or reset database DBMS metadata (dbms, db_server, db_name) stored in Database.metadata.",
    request=DatabaseDbmsMetadataUpdateRequestSerializer,
    responses={
        200: DatabaseDbmsMetadataUpdateResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: DatabaseErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_dbms_metadata(request):
    """
    POST /api/v2/databases/update-dbms-metadata/

    Update or reset Database.metadata.{dbms,db_server,db_name}.
    """
    serializer = DatabaseDbmsMetadataUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid payload",
                    "details": serializer.errors,
                },
            },
            status=400,
        )

    data = serializer.validated_data
    database_id = data["database_id"]
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return _permission_denied("Tenant context is missing.")
    try:
        db = Database.all_objects.get(id=database_id, tenant_id=str(tenant_id))
    except Database.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": {"code": "DATABASE_NOT_FOUND", "message": "Database not found"},
            },
            status=404,
        )

    if not request.user.has_perm(perms.PERM_DATABASES_MANAGE_DATABASE, db):
        return _permission_denied("You do not have permission to update database metadata.")

    reset = bool(data.get("reset") or False)
    meta = dict(db.metadata) if isinstance(getattr(db, "metadata", None), dict) else {}

    keys = ("dbms", "db_server", "db_name")
    updated_fields: list[str] = []

    if reset:
        for k in keys:
            if k in meta:
                meta.pop(k, None)
        updated_fields.extend(list(keys))
    else:
        provided_any = any(k in data for k in keys)
        if not provided_any:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "MISSING_PARAMETER",
                        "message": "At least one of dbms, db_server, db_name is required unless reset=true",
                    },
                },
                status=400,
            )

        for k in keys:
            if k not in data:
                continue
            value = data.get(k)
            if value == "":
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_PARAMETER",
                            "message": f"{k} cannot be empty (use reset=true to clear)",
                        },
                    },
                    status=400,
                )
            meta[k] = value
            updated_fields.append(k)

    db.metadata = meta
    db.save(update_fields=["metadata", "updated_at"])

    log_admin_action(
        request,
        action="database.dbms_metadata.update",
        outcome="success",
        target_type="database",
        target_id=str(db.id),
        metadata={
            "reset": reset,
            "updated_fields": updated_fields,
            "configured": {k: bool(str(meta.get(k) or "").strip()) for k in keys},
        },
    )

    return Response(
        {
            "database": DatabaseSerializer(db).data,
            "message": "Database DBMS metadata updated",
        }
    )
