"""IBCMD connection profile endpoints (Database.metadata.ibcmd_connection)."""

from __future__ import annotations

from .common import *  # noqa: F403
from .common import _permission_denied, _resolve_tenant_id


_PROFILE_KEY = "ibcmd_connection"


@extend_schema(
    tags=["v2"],
    summary="Update database IBCMD connection profile",
    description="Set or reset per-database IBCMD connection profile stored in Database.metadata.",
    request=DatabaseIbcmdConnectionProfileUpdateRequestSerializer,
    responses={
        200: DatabaseIbcmdConnectionProfileUpdateResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: DatabaseErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_ibcmd_connection_profile(request):
    """
    POST /api/v2/databases/update-ibcmd-connection-profile/

    Update or reset Database.metadata.ibcmd_connection.
    """
    serializer = DatabaseIbcmdConnectionProfileUpdateRequestSerializer(data=request.data)
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
    tenant_id = _resolve_tenant_id(request)  # noqa: F405
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
    updated_fields: list[str] = []

    if reset:
        if _PROFILE_KEY in meta:
            meta.pop(_PROFILE_KEY, None)
            updated_fields.append(_PROFILE_KEY)
    else:
        remote = str(data.get("remote") or "").strip()
        pid = data.get("pid")

        offline_in = data.get("offline")
        offline: dict[str, str] | None = None
        if isinstance(offline_in, dict):
            # Serializer already validates values as strings, but normalize consistently.
            offline = {
                str(k).strip(): str(v).strip()
                for k, v in offline_in.items()
                if v not in (None, "") and str(v).strip() != ""
            }
            # Defensive: never keep secrets even if stored accidentally.
            for key in ("db_user", "db_pwd", "db_password"):
                offline.pop(key, None)
            if not offline:
                offline = None

        profile: dict[str, object] = {}
        if remote:
            profile["remote"] = remote
        if isinstance(pid, int) and pid > 0:
            profile["pid"] = pid
        if offline:
            profile["offline"] = offline

        # Empty profile is allowed (stored explicitly as {}).
        meta[_PROFILE_KEY] = profile
        updated_fields.append(_PROFILE_KEY)

    db.metadata = meta
    db.save(update_fields=["metadata", "updated_at"])

    log_admin_action(
        request,
        action="database.ibcmd_connection_profile.update",
        outcome="success",
        target_type="database",
        target_id=str(db.id),
        metadata={
            "reset": reset,
            "updated_fields": updated_fields,
        },
    )

    return Response(
        {
            "database": DatabaseSerializer(db).data,
            "message": "Database IBCMD connection profile updated",
        }
    )
