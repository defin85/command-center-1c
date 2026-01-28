"""RBAC endpoints: workflow template permissions (user and group)."""

from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import PermissionLevel
from apps.templates.models import WorkflowTemplateGroupPermission, WorkflowTemplatePermission
from apps.templates.workflow.models import WorkflowTemplate
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
    BulkDeleteResponseSerializer,
    BulkGrantWorkflowTemplateGroupPermissionRequestSerializer,
    BulkUpsertResponseSerializer,
    BulkRevokeWorkflowTemplateGroupPermissionRequestSerializer,
    GrantWorkflowTemplateGroupPermissionRequestSerializer,
    GrantWorkflowTemplatePermissionRequestSerializer,
    RevokePermissionResponseSerializer,
    RevokeWorkflowTemplateGroupPermissionRequestSerializer,
    RevokeWorkflowTemplatePermissionRequestSerializer,
    WorkflowTemplateGroupPermissionListResponseSerializer,
    WorkflowTemplateGroupPermissionUpsertResponseSerializer,
    WorkflowTemplatePermissionListResponseSerializer,
    WorkflowTemplatePermissionUpsertResponseSerializer,
)

@extend_schema(
    tags=["v2"],
    summary="List workflow template permissions (user)",
    parameters=[
        OpenApiParameter(name="user_id", type=int, required=False),
        OpenApiParameter(name="template_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: WorkflowTemplatePermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_workflow_template_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = WorkflowTemplatePermission.objects.select_related("user", "workflow_template", "granted_by").all()

    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(user_id=user_id)

    template_id = request.query_params.get("template_id")
    if template_id:
        qs = qs.filter(workflow_template_id=template_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(user__username__icontains=search) | Q(workflow_template__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "user": _user_ref(row.user),
            "template": {"id": row.workflow_template.id, "name": row.workflow_template.name},
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
    summary="Grant workflow template permission (user)",
    request=GrantWorkflowTemplatePermissionRequestSerializer,
    responses={200: WorkflowTemplatePermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_workflow_template_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantWorkflowTemplatePermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_workflow_template_permission",
            outcome="error",
            target_type="workflow_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    template_id = serializer.validated_data["template_id"]
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
        template = WorkflowTemplate.objects.get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"}},
            status=404,
        )

    old_level = None
    old_notes = None
    with transaction.atomic():
        obj, created = WorkflowTemplatePermission.objects.select_for_update().get_or_create(
            user=user,
            workflow_template=template,
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
            "template": {"id": obj.workflow_template.id, "name": obj.workflow_template.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_workflow_template_permission",
        outcome="success",
        target_type="workflow_template",
        target_id=str(template_id),
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
    summary="Revoke workflow template permission (user)",
    request=RevokeWorkflowTemplatePermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_workflow_template_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeWorkflowTemplatePermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_workflow_template_permission",
            outcome="error",
            target_type="workflow_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    template_id = serializer.validated_data["template_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    old_level = None
    old_notes = None
    with transaction.atomic():
        existing = WorkflowTemplatePermission.objects.select_for_update().filter(user_id=user_id, workflow_template_id=template_id).first()
        if existing is not None:
            old_level = _level_code(existing.level)
            old_notes = existing.notes or ""
        deleted, _ = WorkflowTemplatePermission.objects.filter(user_id=user_id, workflow_template_id=template_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_workflow_template_permission",
        outcome="success",
        target_type="workflow_template",
        target_id=str(template_id),
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
    summary="List workflow template permissions (group)",
    parameters=[
        OpenApiParameter(name="group_id", type=int, required=False),
        OpenApiParameter(name="template_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: WorkflowTemplateGroupPermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_workflow_template_group_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = WorkflowTemplateGroupPermission.objects.select_related("group", "workflow_template", "granted_by").all()

    group_id = request.query_params.get("group_id")
    if group_id:
        qs = qs.filter(group_id=group_id)

    template_id = request.query_params.get("template_id")
    if template_id:
        qs = qs.filter(workflow_template_id=template_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(group__name__icontains=search) | Q(workflow_template__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "group": _group_ref(row.group),
            "template": {"id": row.workflow_template.id, "name": row.workflow_template.name},
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
    summary="Grant workflow template permission (group)",
    request=GrantWorkflowTemplateGroupPermissionRequestSerializer,
    responses={200: WorkflowTemplateGroupPermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_workflow_template_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantWorkflowTemplateGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_workflow_template_group_permission",
            outcome="error",
            target_type="workflow_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    template_id = serializer.validated_data["template_id"]
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
        template = WorkflowTemplate.objects.get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"}},
            status=404,
        )

    old_level = None
    old_notes = None
    with transaction.atomic():
        obj, created = WorkflowTemplateGroupPermission.objects.select_for_update().get_or_create(
            group=group,
            workflow_template=template,
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
            "template": {"id": obj.workflow_template.id, "name": obj.workflow_template.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_workflow_template_group_permission",
        outcome="success",
        target_type="workflow_template",
        target_id=str(template_id),
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
    summary="Revoke workflow template permission (group)",
    request=RevokeWorkflowTemplateGroupPermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_workflow_template_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeWorkflowTemplateGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_workflow_template_group_permission",
            outcome="error",
            target_type="workflow_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    template_id = serializer.validated_data["template_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    old_level = None
    old_notes = None
    with transaction.atomic():
        existing = WorkflowTemplateGroupPermission.objects.select_for_update().filter(group_id=group_id, workflow_template_id=template_id).first()
        if existing is not None:
            old_level = _level_code(existing.level)
            old_notes = existing.notes or ""
        deleted, _ = WorkflowTemplateGroupPermission.objects.filter(group_id=group_id, workflow_template_id=template_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_workflow_template_group_permission",
        outcome="success",
        target_type="workflow_template",
        target_id=str(template_id),
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
    summary="Bulk grant workflow template group permission",
    request=BulkGrantWorkflowTemplateGroupPermissionRequestSerializer,
    responses={200: BulkUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_grant_workflow_template_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = BulkGrantWorkflowTemplateGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.bulk_grant_workflow_template_group_permission",
            outcome="error",
            target_type="workflow_template",
            target_id="bulk",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    template_ids = _dedupe_keep_order(serializer.validated_data["template_ids"])
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

    found_ids = set(WorkflowTemplate.objects.filter(id__in=template_ids).values_list("id", flat=True))
    missing = [str(tid) for tid in template_ids if tid not in found_ids]
    if missing:
        return Response(
            {"success": False, "error": {"code": "TEMPLATE_NOT_FOUND", "message": f"Templates not found: {missing}"}},
            status=404,
        )

    with transaction.atomic():
        result = _bulk_upsert_group_permissions(
            model=WorkflowTemplateGroupPermission,
            group=group,
            object_ids=template_ids,
            object_id_field="workflow_template_id",
            level=level,
            notes=notes,
            granted_by=request.user,
        )

    log_admin_action(
        request,
        action="rbac.bulk_grant_workflow_template_group_permission",
        outcome="success",
        target_type="workflow_template",
        target_id="bulk",
        metadata={
            "reason": reason,
            "group_id": group_id,
            "level": _level_code(level),
            "notes": notes,
            **result,
            "template_ids_sample": [str(tid) for tid in template_ids[:20]],
        },
    )
    return Response(result)


@extend_schema(
    tags=["v2"],
    summary="Bulk revoke workflow template group permission",
    request=BulkRevokeWorkflowTemplateGroupPermissionRequestSerializer,
    responses={200: BulkDeleteResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_revoke_workflow_template_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = BulkRevokeWorkflowTemplateGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.bulk_revoke_workflow_template_group_permission",
            outcome="error",
            target_type="workflow_template",
            target_id="bulk",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    template_ids = _dedupe_keep_order(serializer.validated_data["template_ids"])
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "GROUP_NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    found_ids = set(WorkflowTemplate.objects.filter(id__in=template_ids).values_list("id", flat=True))
    missing = [str(tid) for tid in template_ids if tid not in found_ids]
    if missing:
        return Response(
            {"success": False, "error": {"code": "TEMPLATE_NOT_FOUND", "message": f"Templates not found: {missing}"}},
            status=404,
        )

    with transaction.atomic():
        result = _bulk_delete_group_permissions(
            model=WorkflowTemplateGroupPermission,
            group=group,
            object_ids=template_ids,
            object_id_field="workflow_template_id",
        )

    log_admin_action(
        request,
        action="rbac.bulk_revoke_workflow_template_group_permission",
        outcome="success",
        target_type="workflow_template",
        target_id="bulk",
        metadata={
            "reason": reason,
            "group_id": group_id,
            **result,
            "template_ids_sample": [str(tid) for tid in template_ids[:20]],
        },
    )
    return Response(result)

