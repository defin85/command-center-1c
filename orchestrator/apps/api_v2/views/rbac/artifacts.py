"""RBAC endpoints: artifact permissions (user and group)."""

from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.artifacts.models import Artifact, ArtifactGroupPermission, ArtifactPermission
from apps.databases.models import PermissionLevel
from apps.operations.services.admin_action_audit import log_admin_action

from .common import (
    _bulk_delete_group_permissions,
    _bulk_upsert_group_permissions,
    _dedupe_keep_order,
    _ensure_manage_rbac,
    _group_ref,
    _level_code,
    _parse_pagination,
    _user_ref,
)
from .serializers_permissions import (
    ArtifactGroupPermissionListResponseSerializer,
    ArtifactGroupPermissionUpsertResponseSerializer,
    ArtifactPermissionListResponseSerializer,
    ArtifactPermissionUpsertResponseSerializer,
    BulkDeleteResponseSerializer,
    BulkGrantArtifactGroupPermissionRequestSerializer,
    BulkUpsertResponseSerializer,
    BulkRevokeArtifactGroupPermissionRequestSerializer,
    GrantArtifactGroupPermissionRequestSerializer,
    GrantArtifactPermissionRequestSerializer,
    RevokePermissionResponseSerializer,
    RevokeArtifactGroupPermissionRequestSerializer,
    RevokeArtifactPermissionRequestSerializer,
)

@extend_schema(
    tags=["v2"],
    summary="List artifact permissions (user)",
    parameters=[
        OpenApiParameter(name="user_id", type=int, required=False),
        OpenApiParameter(name="artifact_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: ArtifactPermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_artifact_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = ArtifactPermission.objects.select_related("user", "artifact", "granted_by").all()

    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(user_id=user_id)

    artifact_id = request.query_params.get("artifact_id")
    if artifact_id:
        qs = qs.filter(artifact_id=artifact_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(user__username__icontains=search) | Q(artifact__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "user": _user_ref(row.user),
            "artifact": {"id": row.artifact.id, "name": row.artifact.name},
            "level": _level_code(row.level),
            "granted_by": _user_ref(row.granted_by),
            "granted_at": row.granted_at,
            "notes": row.notes,
        }
        for row in rows
    ]
    return Response({"permissions": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="Grant artifact permission (user)",
    request=GrantArtifactPermissionRequestSerializer,
    responses={200: ArtifactPermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_artifact_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantArtifactPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_artifact_permission",
            outcome="error",
            target_type="artifact",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    artifact_id = serializer.validated_data["artifact_id"]
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    try:
        artifact = Artifact.objects.get(id=artifact_id, is_deleted=False)
    except Artifact.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "ARTIFACT_NOT_FOUND", "message": "Artifact not found"}},
            status=404,
        )

    old_level = None
    old_notes = None
    with transaction.atomic():
        obj, created = ArtifactPermission.objects.select_for_update().get_or_create(
            user=user,
            artifact=artifact,
            defaults={"level": level, "notes": notes, "granted_by": request.user},
        )
        if not created:
            old_level = _level_code(obj.level)
            old_notes = obj.notes or ""
            obj.level = level
            obj.notes = notes
            obj.granted_by = request.user
            obj.save(update_fields=["level", "notes", "granted_by"])

    payload = {
        "created": created,
        "permission": {
            "user": _user_ref(obj.user),
            "artifact": {"id": obj.artifact.id, "name": obj.artifact.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_artifact_permission",
        outcome="success",
        target_type="artifact",
        target_id=str(artifact_id),
        metadata={
            "reason": reason,
            "user_id": user_id,
            "level": _level_code(level),
            "created": created,
            "notes": notes,
            **({"old_level": old_level, "old_notes": old_notes} if not created else {}),
        },
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke artifact permission (user)",
    request=RevokeArtifactPermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_artifact_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeArtifactPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_artifact_permission",
            outcome="error",
            target_type="artifact",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    artifact_id = serializer.validated_data["artifact_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    old_level = None
    old_notes = None
    with transaction.atomic():
        existing = ArtifactPermission.objects.select_for_update().filter(user_id=user_id, artifact_id=artifact_id).first()
        if existing is not None:
            old_level = _level_code(existing.level)
            old_notes = existing.notes or ""
        deleted, _ = ArtifactPermission.objects.filter(user_id=user_id, artifact_id=artifact_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_artifact_permission",
        outcome="success",
        target_type="artifact",
        target_id=str(artifact_id),
        metadata={
            "reason": reason,
            "user_id": user_id,
            "deleted": deleted > 0,
            **({"old_level": old_level, "old_notes": old_notes} if deleted > 0 and old_level is not None else {}),
        },
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="List artifact permissions (group)",
    parameters=[
        OpenApiParameter(name="group_id", type=int, required=False),
        OpenApiParameter(name="artifact_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: ArtifactGroupPermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_artifact_group_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = ArtifactGroupPermission.objects.select_related("group", "artifact", "granted_by").all()

    group_id = request.query_params.get("group_id")
    if group_id:
        qs = qs.filter(group_id=group_id)

    artifact_id = request.query_params.get("artifact_id")
    if artifact_id:
        qs = qs.filter(artifact_id=artifact_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(group__name__icontains=search) | Q(artifact__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "group": _group_ref(row.group),
            "artifact": {"id": row.artifact.id, "name": row.artifact.name},
            "level": _level_code(row.level),
            "granted_by": _user_ref(row.granted_by),
            "granted_at": row.granted_at,
            "notes": row.notes,
        }
        for row in rows
    ]
    return Response({"permissions": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="Grant artifact permission (group)",
    request=GrantArtifactGroupPermissionRequestSerializer,
    responses={200: ArtifactGroupPermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_artifact_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantArtifactGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_artifact_group_permission",
            outcome="error",
            target_type="artifact",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    artifact_id = serializer.validated_data["artifact_id"]
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "GROUP_NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    try:
        artifact = Artifact.objects.get(id=artifact_id, is_deleted=False)
    except Artifact.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "ARTIFACT_NOT_FOUND", "message": "Artifact not found"}},
            status=404,
        )

    old_level = None
    old_notes = None
    with transaction.atomic():
        obj, created = ArtifactGroupPermission.objects.select_for_update().get_or_create(
            group=group,
            artifact=artifact,
            defaults={"level": level, "notes": notes, "granted_by": request.user},
        )
        if not created:
            old_level = _level_code(obj.level)
            old_notes = obj.notes or ""
            obj.level = level
            obj.notes = notes
            obj.granted_by = request.user
            obj.save(update_fields=["level", "notes", "granted_by"])

    payload = {
        "created": created,
        "permission": {
            "group": _group_ref(obj.group),
            "artifact": {"id": obj.artifact.id, "name": obj.artifact.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_artifact_group_permission",
        outcome="success",
        target_type="artifact",
        target_id=str(artifact_id),
        metadata={
            "reason": reason,
            "group_id": group_id,
            "level": _level_code(level),
            "created": created,
            "notes": notes,
            **({"old_level": old_level, "old_notes": old_notes} if not created else {}),
        },
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke artifact permission (group)",
    request=RevokeArtifactGroupPermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_artifact_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeArtifactGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_artifact_group_permission",
            outcome="error",
            target_type="artifact",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    artifact_id = serializer.validated_data["artifact_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    old_level = None
    old_notes = None
    with transaction.atomic():
        existing = ArtifactGroupPermission.objects.select_for_update().filter(group_id=group_id, artifact_id=artifact_id).first()
        if existing is not None:
            old_level = _level_code(existing.level)
            old_notes = existing.notes or ""
        deleted, _ = ArtifactGroupPermission.objects.filter(group_id=group_id, artifact_id=artifact_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_artifact_group_permission",
        outcome="success",
        target_type="artifact",
        target_id=str(artifact_id),
        metadata={
            "reason": reason,
            "group_id": group_id,
            "deleted": deleted > 0,
            **({"old_level": old_level, "old_notes": old_notes} if deleted > 0 and old_level is not None else {}),
        },
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="Bulk grant artifact group permission",
    request=BulkGrantArtifactGroupPermissionRequestSerializer,
    responses={200: BulkUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_grant_artifact_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = BulkGrantArtifactGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.bulk_grant_artifact_group_permission",
            outcome="error",
            target_type="artifact",
            target_id="bulk",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    artifact_ids = _dedupe_keep_order(serializer.validated_data["artifact_ids"])
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "GROUP_NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    found_ids = set(Artifact.objects.filter(id__in=artifact_ids, is_deleted=False).values_list("id", flat=True))
    missing = [str(aid) for aid in artifact_ids if aid not in found_ids]
    if missing:
        return Response(
            {"success": False, "error": {"code": "ARTIFACT_NOT_FOUND", "message": f"Artifacts not found: {missing}"}},
            status=404,
        )

    with transaction.atomic():
        result = _bulk_upsert_group_permissions(
            model=ArtifactGroupPermission,
            group=group,
            object_ids=artifact_ids,
            object_id_field="artifact_id",
            level=level,
            notes=notes,
            granted_by=request.user,
        )

    log_admin_action(
        request,
        action="rbac.bulk_grant_artifact_group_permission",
        outcome="success",
        target_type="artifact",
        target_id="bulk",
        metadata={
            "reason": reason,
            "group_id": group_id,
            "level": _level_code(level),
            "notes": notes,
            **result,
            "artifact_ids_sample": [str(aid) for aid in artifact_ids[:20]],
        },
    )
    return Response(result)


@extend_schema(
    tags=["v2"],
    summary="Bulk revoke artifact group permission",
    request=BulkRevokeArtifactGroupPermissionRequestSerializer,
    responses={200: BulkDeleteResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_revoke_artifact_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = BulkRevokeArtifactGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.bulk_revoke_artifact_group_permission",
            outcome="error",
            target_type="artifact",
            target_id="bulk",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    artifact_ids = _dedupe_keep_order(serializer.validated_data["artifact_ids"])
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "GROUP_NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    found_ids = set(Artifact.objects.filter(id__in=artifact_ids, is_deleted=False).values_list("id", flat=True))
    missing = [str(aid) for aid in artifact_ids if aid not in found_ids]
    if missing:
        return Response(
            {"success": False, "error": {"code": "ARTIFACT_NOT_FOUND", "message": f"Artifacts not found: {missing}"}},
            status=404,
        )

    with transaction.atomic():
        result = _bulk_delete_group_permissions(
            model=ArtifactGroupPermission,
            group=group,
            object_ids=artifact_ids,
            object_id_field="artifact_id",
        )

    log_admin_action(
        request,
        action="rbac.bulk_revoke_artifact_group_permission",
        outcome="success",
        target_type="artifact",
        target_id="bulk",
        metadata={
            "reason": reason,
            "group_id": group_id,
            **result,
            "artifact_ids_sample": [str(aid) for aid in artifact_ids[:20]],
        },
    )
    return Response(result)


