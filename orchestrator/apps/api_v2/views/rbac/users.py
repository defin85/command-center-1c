"""RBAC endpoints: users and user+roles lists."""

from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.db.models import Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .common import _ensure_manage_rbac
from .serializers_core import RbacUserRefSerializer
from .serializers_permissions import (
    RbacUserListResponseSerializer,
    RbacUserWithRolesListResponseSerializer,
)

@extend_schema(
    tags=["v2"],
    summary="List users",
    description="List users for RBAC selection (staff only).",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False, description="Search by username or name"),
        OpenApiParameter(name="limit", type=int, required=False, description="Maximum results (default: 100, max: 1000)"),
        OpenApiParameter(name="offset", type=int, required=False, description="Pagination offset (default: 0)"),
    ],
    responses={
        200: RbacUserListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_users(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    try:
        limit = int(request.query_params.get("limit", 100))
        limit = max(1, min(limit, 1000))
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = int(request.query_params.get("offset", 0))
        offset = max(0, offset)
    except (TypeError, ValueError):
        offset = 0

    qs = User.objects.all()
    if search:
        qs = qs.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )

    total = qs.count()
    qs = qs.order_by("username")[offset:offset + limit]
    data = RbacUserRefSerializer(qs, many=True).data

    return Response({
        "users": data,
        "count": len(data),
        "total": total,
    })


@extend_schema(
    tags=["v2"],
    summary="List users with roles",
    description="List users with their RBAC roles (Django groups). Requires manage_rbac.",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False, description="Search by username or name"),
        OpenApiParameter(name="role_id", type=int, required=False, description="Filter users by role (group id)"),
        OpenApiParameter(name="limit", type=int, required=False, description="Maximum results (default: 100, max: 1000)"),
        OpenApiParameter(name="offset", type=int, required=False, description="Pagination offset (default: 0)"),
    ],
    responses={
        200: RbacUserWithRolesListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_users_with_roles(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    role_id = request.query_params.get("role_id")

    try:
        limit = int(request.query_params.get("limit", 100))
        limit = max(1, min(limit, 1000))
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = int(request.query_params.get("offset", 0))
        offset = max(0, offset)
    except (TypeError, ValueError):
        offset = 0

    qs = User.objects.all()
    if search:
        qs = qs.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )

    if role_id:
        try:
            qs = qs.filter(groups__id=int(role_id))
        except (TypeError, ValueError):
            pass

    qs = qs.distinct()
    total = qs.count()

    groups_qs = Group.objects.only("id", "name").order_by("name")
    qs = qs.order_by("username").prefetch_related(Prefetch("groups", queryset=groups_qs))[offset:offset + limit]

    data = [
        {
            "id": user.id,
            "username": user.username,
            "roles": [{"id": group.id, "name": group.name} for group in user.groups.all()],
        }
        for user in qs
    ]

    return Response({
        "users": data,
        "count": len(data),
        "total": total,
    })


