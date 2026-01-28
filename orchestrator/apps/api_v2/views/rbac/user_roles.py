"""RBAC endpoints: user role bindings."""

from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.operations.services.admin_action_audit import log_admin_action

from .common import _ensure_manage_rbac, _group_ref, _user_ref
from .roles import _get_manage_rbac_permission
from .serializers_core import RbacErrorResponseSerializer, UserRolesGetResponseSerializer, UserRolesUpdateRequestSerializer

@extend_schema(
    tags=["v2"],
    summary="Get user roles (groups)",
    parameters=[OpenApiParameter(name="user_id", type=int, required=False)],
    responses={
        200: UserRolesGetResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_roles(request):
    requested_user_id = request.query_params.get("user_id")
    if requested_user_id and int(requested_user_id) != request.user.id:
        denied = _ensure_manage_rbac(request)
        if denied:
            return denied

    target_user = request.user
    if requested_user_id:
        try:
            target_user = User.objects.get(id=requested_user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
                status=404,
            )

    roles = list(target_user.groups.all().order_by("name"))
    return Response({"user": _user_ref(target_user), "roles": [_group_ref(g) for g in roles]})


@extend_schema(
    tags=["v2"],
    summary="Update user roles (group membership)",
    request=UserRolesUpdateRequestSerializer,
    responses={
        200: UserRolesGetResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
        409: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_user_roles(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = UserRolesUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.set_user_roles",
            outcome="error",
            target_type="user",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    group_ids = serializer.validated_data["group_ids"]
    mode = serializer.validated_data.get("mode") or "replace"
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    old_group_ids = sorted(list(target_user.groups.values_list("id", flat=True)))

    groups = list(Group.objects.filter(id__in=group_ids))
    if len(groups) != len(set(group_ids)):
        return Response(
            {"success": False, "error": {"code": "GROUP_NOT_FOUND", "message": "One or more roles not found"}},
            status=404,
        )

    manage_perm = _get_manage_rbac_permission()
    if manage_perm is not None and not request.user.is_superuser and not target_user.is_superuser:
        manage_group_ids = set(Group.objects.filter(permissions=manage_perm).values_list("id", flat=True))

        current_group_ids = set(target_user.groups.values_list("id", flat=True))
        requested_group_ids = set(group_ids)

        new_group_ids = set(current_group_ids)
        if mode == "replace":
            new_group_ids = set(requested_group_ids)
        elif mode == "add":
            new_group_ids = set(current_group_ids).union(requested_group_ids)
        elif mode == "remove":
            new_group_ids = set(current_group_ids).difference(requested_group_ids)

        has_direct_manage_perm = target_user.user_permissions.filter(id=manage_perm.id).exists()
        currently_has_manage = has_direct_manage_perm or bool(current_group_ids.intersection(manage_group_ids))
        will_have_manage = has_direct_manage_perm or bool(new_group_ids.intersection(manage_group_ids))

        if currently_has_manage and not will_have_manage:
            remaining_admin_exists = User.objects.exclude(id=target_user.id).filter(is_superuser=False).filter(
                Q(user_permissions=manage_perm) | Q(groups__id__in=list(manage_group_ids))
            ).distinct().exists()
            if not remaining_admin_exists:
                log_admin_action(
                    request,
                    action="rbac.set_user_roles",
                    outcome="error",
                    target_type="user",
                    target_id=str(target_user.id),
                    metadata={"reason": reason, "mode": mode, "group_ids": group_ids, "error": "LAST_RBAC_ADMIN"},
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
        target_user.groups.set(groups)
    elif mode == "add":
        target_user.groups.add(*groups)
    elif mode == "remove":
        target_user.groups.remove(*groups)
    else:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Invalid mode"}},
            status=400,
        )

    roles = list(target_user.groups.all().order_by("name"))
    log_admin_action(
        request,
        action="rbac.set_user_roles",
        outcome="success",
        target_type="user",
        target_id=str(target_user.id),
        metadata={"reason": reason, "mode": mode, "group_ids": group_ids, "old_group_ids": old_group_ids},
    )
    return Response({"user": _user_ref(target_user), "roles": [_group_ref(g) for g in roles]})
