"""
User management endpoints for API v2 (staff-only).
"""

from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.operations.services.admin_action_audit import log_admin_action

User = get_user_model()


class UserErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField(required=False)


class UserErrorResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    error = UserErrorDetailSerializer()
    request_id = serializers.CharField()
    ui_action_id = serializers.CharField(required=False)


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.CharField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    is_staff = serializers.BooleanField()
    is_active = serializers.BooleanField()
    last_login = serializers.DateTimeField(allow_null=True)
    date_joined = serializers.DateTimeField()


class UserListResponseSerializer(serializers.Serializer):
    users = UserSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class UserCreateRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    email = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    is_staff = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


class UserUpdateRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField(required=False)
    email = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    is_staff = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


class UserPasswordRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    password = serializers.CharField(write_only=True)


def _parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


@extend_schema(
    tags=["v2"],
    summary="List users",
    description="List users for admin UI (staff only).",
    parameters=[
        OpenApiParameter(name="id", type=int, required=False, description="Filter by user id"),
        OpenApiParameter(name="search", type=str, required=False, description="Search by username or name"),
        OpenApiParameter(name="username", type=str, required=False, description="Filter by username"),
        OpenApiParameter(name="email", type=str, required=False, description="Filter by email"),
        OpenApiParameter(name="is_staff", type=bool, required=False, description="Filter by staff flag"),
        OpenApiParameter(name="is_active", type=bool, required=False, description="Filter by active flag"),
        OpenApiParameter(name="limit", type=int, required=False, description="Maximum results (default: 100, max: 1000)"),
        OpenApiParameter(name="offset", type=int, required=False, description="Pagination offset (default: 0)"),
    ],
    responses={
        200: UserListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_users(request):
    raw_user_id = (request.query_params.get("id") or "").strip()
    search = (request.query_params.get("search") or "").strip()
    username = (request.query_params.get("username") or "").strip()
    email = (request.query_params.get("email") or "").strip()
    is_staff = _parse_bool(request.query_params.get("is_staff"))
    is_active = _parse_bool(request.query_params.get("is_active"))

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
    if raw_user_id:
        try:
            qs = qs.filter(id=int(raw_user_id))
        except (TypeError, ValueError):
            qs = qs.none()
    if search:
        qs = qs.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
        )
    if username:
        qs = qs.filter(username__icontains=username)
    if email:
        qs = qs.filter(email__icontains=email)
    if is_staff is not None:
        qs = qs.filter(is_staff=is_staff)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)

    total = qs.count()
    qs = qs.order_by("username")[offset:offset + limit]
    data = UserSerializer(qs, many=True).data

    return Response({
        "users": data,
        "count": len(data),
        "total": total,
    })


@extend_schema(
    tags=["v2"],
    summary="Create user",
    request=UserCreateRequestSerializer,
    responses={
        201: UserSerializer,
        400: UserErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        409: OpenApiResponse(description="Duplicate username"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def create_user(request):
    serializer = UserCreateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Invalid payload", "details": serializer.errors}},
            status=400,
        )

    data = serializer.validated_data
    username = data["username"].strip()
    if User.objects.filter(username=username).exists():
        return Response(
            {"success": False, "error": {"code": "DUPLICATE_USER", "message": "Username already exists"}},
            status=409,
        )

    user = User.objects.create_user(
        username=username,
        password=data["password"],
        email=data.get("email", "").strip(),
        first_name=data.get("first_name", "").strip(),
        last_name=data.get("last_name", "").strip(),
    )
    user.is_staff = bool(data.get("is_staff", False))
    user.is_active = bool(data.get("is_active", True))
    user.save(update_fields=["is_staff", "is_active"])

    log_admin_action(
        request,
        action="users.create",
        outcome="success",
        target_type="user",
        target_id=str(user.id),
        metadata={
            "username": user.username,
            "is_staff": user.is_staff,
            "is_active": user.is_active,
        },
    )

    return Response(UserSerializer(user).data, status=201)


@extend_schema(
    tags=["v2"],
    summary="Update user",
    request=UserUpdateRequestSerializer,
    responses={
        200: UserSerializer,
        400: UserErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: UserErrorResponseSerializer,
        409: OpenApiResponse(description="Duplicate username"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def update_user(request):
    serializer = UserUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Invalid payload", "details": serializer.errors}},
            status=400,
        )

    data = serializer.validated_data
    try:
        user = User.objects.get(id=data["id"])
    except User.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    if "username" in data:
        username = data["username"].strip()
        if username and username != user.username and User.objects.filter(username=username).exists():
            return Response(
                {"success": False, "error": {"code": "DUPLICATE_USER", "message": "Username already exists"}},
                status=409,
            )
        user.username = username
    if "email" in data:
        user.email = data.get("email", "").strip()
    if "first_name" in data:
        user.first_name = data.get("first_name", "").strip()
    if "last_name" in data:
        user.last_name = data.get("last_name", "").strip()
    if "is_staff" in data:
        user.is_staff = bool(data.get("is_staff"))
    if "is_active" in data:
        user.is_active = bool(data.get("is_active"))

    user.save()

    log_admin_action(
        request,
        action="users.update",
        outcome="success",
        target_type="user",
        target_id=str(user.id),
        metadata={
            "username": user.username,
            "is_staff": user.is_staff,
            "is_active": user.is_active,
        },
    )

    return Response(UserSerializer(user).data)


@extend_schema(
    tags=["v2"],
    summary="Set user password",
    request=UserPasswordRequestSerializer,
    responses={
        200: UserSerializer,
        400: UserErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: UserErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def set_user_password(request):
    serializer = UserPasswordRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Invalid payload", "details": serializer.errors}},
            status=400,
        )

    data = serializer.validated_data
    try:
        user = User.objects.get(id=data["id"])
    except User.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    user.set_password(data["password"])
    user.save(update_fields=["password"])

    log_admin_action(
        request,
        action="users.set_password",
        outcome="success",
        target_type="user",
        target_id=str(user.id),
        metadata={"username": user.username},
    )

    return Response(UserSerializer(user).data)
