"""RBAC endpoints: roles and capabilities."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission, User
from django.db import transaction
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.artifacts.models import ArtifactGroupPermission
from apps.core import permission_codes as perms
from apps.databases.models import ClusterGroupPermission, DatabaseGroupPermission
from apps.operations.services.admin_action_audit import log_admin_action
from apps.templates.models import (
    OperationExposure,
    OperationExposureGroupPermission,
    WorkflowTemplateGroupPermission,
)

from .common import _ensure_manage_rbac, _group_ref, _parse_pagination
from .serializers_core import (
    CapabilityListResponseSerializer,
    RbacErrorResponseSerializer,
    RbacGroupRefSerializer,
    RoleCapabilitiesUpdateRequestSerializer,
    RoleCapabilitiesUpdateResponseSerializer,
    RoleCreateRequestSerializer,
    RoleDeleteRequestSerializer,
    RoleListResponseSerializer,
    RoleUpdateRequestSerializer,
)
from .serializers_permissions import RevokePermissionResponseSerializer

def _get_curated_permission_codes() -> list[str]:
    codes: set[str] = set()
    for name in dir(perms):
        if not name.startswith("PERM_"):
            continue
        value = getattr(perms, name)
        if isinstance(value, str) and "." in value:
            codes.add(value)
    return sorted(codes)


def _split_permission_code(code: str) -> tuple[str, str] | None:
    value = str(code or "").strip()
    if not value or "." not in value:
        return None
    app_label, codename = value.split(".", 1)
    app_label = app_label.strip()
    codename = codename.strip()
    if not app_label or not codename:
        return None
    return app_label, codename


def _get_permission_by_code(code: str) -> Permission | None:
    split = _split_permission_code(code)
    if split is None:
        return None
    app_label, codename = split
    try:
        return Permission.objects.select_related("content_type").get(
            content_type__app_label=app_label,
            codename=codename,
        )
    except Permission.DoesNotExist:
        return None


def _get_manage_rbac_permission() -> Permission | None:
    return _get_permission_by_code(perms.PERM_DATABASES_MANAGE_RBAC)


@extend_schema(
    tags=["v2"],
    summary="List roles (Django groups)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={
        200: RoleListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_roles(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=100, max_limit=500)

    qs = Group.objects.all()
    if search:
        qs = qs.filter(name__icontains=search)

    total = qs.count()
    rows = list(
        qs.annotate(
            users_count=Count("user", distinct=True),
            permissions_count=Count("permissions", distinct=True),
        )
        .prefetch_related("permissions__content_type")
        .order_by("name")[pagination.offset: pagination.offset + pagination.limit]
    )

    data = []
    for group in rows:
        permission_codes = sorted({
            f"{p.content_type.app_label}.{p.codename}"
            for p in group.permissions.all()
        })
        data.append(
            {
                "id": group.id,
                "name": group.name,
                "users_count": int(getattr(group, "users_count", 0) or 0),
                "permissions_count": int(getattr(group, "permissions_count", 0) or 0),
                "permission_codes": permission_codes,
            }
        )

    return Response({"roles": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="Create role (Django group)",
    request=RoleCreateRequestSerializer,
    responses={
        200: RbacGroupRefSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        409: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_role(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RoleCreateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.create_role",
            outcome="error",
            target_type="group",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    name = str(serializer.validated_data.get("name") or "").strip()
    reason = str(serializer.validated_data.get("reason") or "").strip()
    if not name:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "name is required"}},
            status=400,
        )

    if Group.objects.filter(name=name).exists():
        return Response(
            {"success": False, "error": {"code": "DUPLICATE", "message": "Role already exists"}},
            status=409,
        )

    group = Group.objects.create(name=name)
    log_admin_action(
        request,
        action="rbac.create_role",
        outcome="success",
        target_type="group",
        target_id=str(group.id),
        metadata={"reason": reason, "name": name},
    )
    return Response({"id": group.id, "name": group.name})


@extend_schema(
    tags=["v2"],
    summary="Update role (rename Django group)",
    request=RoleUpdateRequestSerializer,
    responses={
        200: RbacGroupRefSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
        409: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_role(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RoleUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.update_role",
            outcome="error",
            target_type="group",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    name = str(serializer.validated_data.get("name") or "").strip()
    reason = str(serializer.validated_data.get("reason") or "").strip()
    if not name:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "name is required"}},
            status=400,
        )

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    if Group.objects.exclude(id=group_id).filter(name=name).exists():
        return Response(
            {"success": False, "error": {"code": "DUPLICATE", "message": "Role name already exists"}},
            status=409,
        )

    old_name = group.name
    group.name = name
    group.save(update_fields=["name"])
    log_admin_action(
        request,
        action="rbac.update_role",
        outcome="success",
        target_type="group",
        target_id=str(group.id),
        metadata={"reason": reason, "old_name": old_name, "name": name},
    )
    return Response({"id": group.id, "name": group.name})


@extend_schema(
    tags=["v2"],
    summary="Delete role (safe delete)",
    request=RoleDeleteRequestSerializer,
    responses={
        200: RevokePermissionResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
        409: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_role(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RoleDeleteRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.delete_role",
            outcome="error",
            target_type="group",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    has_members = group.user_set.exists()
    has_capabilities = group.permissions.exists()
    has_bindings = (
        ClusterGroupPermission.objects.filter(group=group).exists()
        or DatabaseGroupPermission.objects.filter(group=group).exists()
        or OperationExposureGroupPermission.objects.filter(
            group=group,
            exposure__surface=OperationExposure.SURFACE_TEMPLATE,
            exposure__tenant__isnull=True,
        ).exists()
        or WorkflowTemplateGroupPermission.objects.filter(group=group).exists()
        or ArtifactGroupPermission.objects.filter(group=group).exists()
    )

    if has_members or has_capabilities or has_bindings:
        return Response(
            {
                "success": False,
                "error": {
                    "code": "ROLE_NOT_EMPTY",
                    "message": "Role has members/capabilities/bindings and cannot be deleted",
                },
            },
            status=409,
        )

    group.delete()
    log_admin_action(
        request,
        action="rbac.delete_role",
        outcome="success",
        target_type="group",
        target_id=str(group_id),
        metadata={"reason": reason},
    )
    return Response({"deleted": True})


@extend_schema(
    tags=["v2"],
    summary="List supported capability permissions (curated)",
    responses={
        200: CapabilityListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_capabilities(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    codes = _get_curated_permission_codes()
    pairs = [_split_permission_code(code) for code in codes]
    pairs = [p for p in pairs if p is not None]
    app_labels = sorted({p[0] for p in pairs})
    codenames = sorted({p[1] for p in pairs})

    perm_map: dict[tuple[str, str], Permission] = {}
    if pairs:
        qs = Permission.objects.select_related("content_type").filter(
            content_type__app_label__in=app_labels,
            codename__in=codenames,
        )
        perm_map = {(p.content_type.app_label, p.codename): p for p in qs}

    items = []
    for code in codes:
        split = _split_permission_code(code)
        if split is None:
            continue
        app_label, codename = split
        perm = perm_map.get((app_label, codename))
        items.append(
            {
                "code": code,
                "name": perm.name if perm else "",
                "app_label": app_label,
                "codename": codename,
                "exists": bool(perm),
            }
        )

    return Response({"capabilities": items, "count": len(items)})


@extend_schema(
    tags=["v2"],
    summary="Update role capabilities (group permissions)",
    request=RoleCapabilitiesUpdateRequestSerializer,
    responses={
        200: RoleCapabilitiesUpdateResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
        409: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_role_capabilities(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RoleCapabilitiesUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.set_role_capabilities",
            outcome="error",
            target_type="group",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    permission_codes = serializer.validated_data["permission_codes"]
    mode = serializer.validated_data.get("mode") or "replace"
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    old_permission_codes = sorted(
        {f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.select_related("content_type").all()}
    )

    parsed: list[tuple[str, str, str]] = []
    for code in permission_codes:
        split = _split_permission_code(code)
        if split is None:
            return Response(
                {"success": False, "error": {"code": "INVALID_PERMISSION", "message": f"Invalid code: {code}"}},
                status=400,
            )
        app_label, codename = split
        parsed.append((code, app_label, codename))

    app_labels = sorted({app_label for _, app_label, _ in parsed})
    codenames = sorted({codename for _, _, codename in parsed})
    perm_map: dict[tuple[str, str], Permission] = {}
    if parsed:
        qs = Permission.objects.select_related("content_type").filter(
            content_type__app_label__in=app_labels,
            codename__in=codenames,
        )
        perm_map = {(p.content_type.app_label, p.codename): p for p in qs}

    missing = [code for code, app_label, codename in parsed if (app_label, codename) not in perm_map]
    if missing:
        return Response(
            {
                "success": False,
                "error": {"code": "UNKNOWN_PERMISSION", "message": f"Unknown permission codes: {missing}"},
            },
            status=400,
        )

    resolved = [perm_map[(app_label, codename)] for _, app_label, codename in parsed]

    manage_perm = _get_manage_rbac_permission()
    if manage_perm is not None and not request.user.is_superuser:
        existing_has_manage = group.permissions.filter(id=manage_perm.id).exists()
        resolved_ids = {p.id for p in resolved}

        will_have_manage = existing_has_manage
        if mode == "replace":
            will_have_manage = manage_perm.id in resolved_ids
        elif mode == "add":
            will_have_manage = existing_has_manage or manage_perm.id in resolved_ids
        elif mode == "remove":
            will_have_manage = existing_has_manage and manage_perm.id not in resolved_ids

        if existing_has_manage and not will_have_manage:
            manage_group_ids = set(Group.objects.filter(permissions=manage_perm).values_list("id", flat=True))
            manage_group_ids.discard(group.id)
            remaining_admin_exists = User.objects.filter(is_superuser=False).filter(
                Q(user_permissions=manage_perm) | Q(groups__id__in=list(manage_group_ids))
            ).distinct().exists()
            if not remaining_admin_exists:
                log_admin_action(
                    request,
                    action="rbac.set_role_capabilities",
                    outcome="error",
                    target_type="group",
                    target_id=str(group.id),
                    metadata={
                        "reason": reason,
                        "mode": mode,
                        "permission_codes": permission_codes,
                        "error": "LAST_RBAC_ADMIN",
                    },
                    error_message="LAST_RBAC_ADMIN",
                )
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "LAST_RBAC_ADMIN",
                            "message": "Refusing to remove the last non-superuser RBAC admin (databases.manage_rbac)",
                        },
                    },
                    status=409,
                )

    if mode == "replace":
        group.permissions.set(resolved)
    elif mode == "add":
        group.permissions.add(*resolved)
    elif mode == "remove":
        group.permissions.remove(*resolved)
    else:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Invalid mode"}},
            status=400,
        )

    updated_codes = sorted({f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.select_related("content_type").all()})
    log_admin_action(
        request,
        action="rbac.set_role_capabilities",
        outcome="success",
        target_type="group",
        target_id=str(group.id),
        metadata={
            "reason": reason,
            "mode": mode,
            "permission_codes": permission_codes,
            "old_permission_codes": old_permission_codes,
        },
    )
    return Response({"group": _group_ref(group), "permission_codes": updated_codes})

