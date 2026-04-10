"""Runtime control plane API endpoints."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.core import permission_codes as perms
from apps.operations.services.runtime_control import (
    create_runtime_action_run,
    get_runtime_action_run,
    get_runtime_detail,
    get_scheduler_desired_state,
    get_runtime_action_queryset,
    list_runtime_instances,
    list_scheduler_jobs,
    serialize_runtime_action_run,
    serialize_runtime_instance,
    update_runtime_desired_state,
)
from apps.operations.models import RuntimeActionRun


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=status.HTTP_403_FORBIDDEN,
    )


def _ensure_manage_runtime_controls(request):
    user = request.user
    if getattr(user, "is_superuser", False):
        return None
    if perms.PERM_OPERATIONS_MANAGE_RUNTIME_CONTROLS in user.get_all_permissions():
        return None
    return _permission_denied("You do not have permission to manage runtime controls.")


class RuntimeObservedStateSerializer(serializers.Serializer):
    status = serializers.CharField()
    process_status = serializers.CharField()
    http_status = serializers.CharField()
    raw_probe = serializers.CharField()
    command_status = serializers.CharField(required=False)


class RuntimeProviderSerializer(serializers.Serializer):
    key = serializers.CharField()
    host = serializers.CharField()


class RuntimeActionRunSerializer(serializers.Serializer):
    id = serializers.CharField()
    provider = serializers.CharField()
    runtime_id = serializers.CharField()
    runtime_name = serializers.CharField()
    action_type = serializers.CharField()
    target_job_name = serializers.CharField()
    status = serializers.CharField()
    reason = serializers.CharField()
    requested_by_username = serializers.CharField()
    requested_at = serializers.CharField(allow_null=True)
    started_at = serializers.CharField(allow_null=True)
    finished_at = serializers.CharField(allow_null=True)
    result_excerpt = serializers.CharField()
    result_payload = serializers.JSONField()
    error_message = serializers.CharField()
    scheduler_job_run_id = serializers.IntegerField(allow_null=True)


class RuntimeInstanceSerializer(serializers.Serializer):
    runtime_id = serializers.CharField()
    runtime_name = serializers.CharField()
    display_name = serializers.CharField()
    provider = RuntimeProviderSerializer()
    observed_state = RuntimeObservedStateSerializer()
    type = serializers.CharField(allow_null=True)
    stack = serializers.CharField(allow_null=True)
    entrypoint = serializers.CharField(allow_null=True)
    health = serializers.CharField(allow_null=True)
    supported_actions = serializers.ListField(child=serializers.CharField())
    logs_available = serializers.BooleanField()
    scheduler_supported = serializers.BooleanField()
    desired_state = serializers.JSONField(required=False)
    logs_excerpt = serializers.JSONField(required=False)
    recent_actions = RuntimeActionRunSerializer(many=True, required=False)


class RuntimeControlCatalogResponseSerializer(serializers.Serializer):
    runtimes = RuntimeInstanceSerializer(many=True)


class RuntimeControlRuntimeResponseSerializer(serializers.Serializer):
    runtime = RuntimeInstanceSerializer()


class RuntimeActionListResponseSerializer(serializers.Serializer):
    actions = RuntimeActionRunSerializer(many=True)


class RuntimeActionResponseSerializer(serializers.Serializer):
    action = RuntimeActionRunSerializer()


class RuntimeActionCreateSerializer(serializers.Serializer):
    runtime_id = serializers.CharField()
    action_type = serializers.ChoiceField(
        choices=["probe", "restart", "tail_logs", "trigger_now"],
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    target_job_name = serializers.CharField(required=False, allow_blank=True, default="")


class RuntimeDesiredStateJobPatchSerializer(serializers.Serializer):
    job_name = serializers.CharField()
    enabled = serializers.BooleanField(required=False)
    schedule = serializers.CharField(required=False)


class RuntimeDesiredStatePatchSerializer(serializers.Serializer):
    scheduler_enabled = serializers.BooleanField(required=False)
    jobs = RuntimeDesiredStateJobPatchSerializer(many=True, required=False, default=list)


class RuntimeDesiredStateResponseSerializer(serializers.Serializer):
    runtime_id = serializers.CharField()
    desired_state = serializers.JSONField()


class RuntimeSchedulerJobsResponseSerializer(serializers.Serializer):
    jobs = serializers.ListField(child=serializers.DictField())
    desired_state = serializers.JSONField()


@extend_schema(
    tags=["v2"],
    summary="List runtime-control catalog",
    responses={
        200: RuntimeControlCatalogResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_runtime_control_catalog(request):
    denied = _ensure_manage_runtime_controls(request)
    if denied is not None:
        return denied
    return Response({"runtimes": [serialize_runtime_instance(item) for item in list_runtime_instances()]})


@extend_schema(
    tags=["v2"],
    summary="Get runtime-control detail",
    responses={
        200: RuntimeControlRuntimeResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_runtime_control_runtime(request, runtime_id: str):
    denied = _ensure_manage_runtime_controls(request)
    if denied is not None:
        return denied
    try:
        runtime = get_runtime_detail(runtime_id)
    except KeyError:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Runtime not found"}},
            status=status.HTTP_404_NOT_FOUND,
        )
    runtime["recent_actions"] = [serialize_runtime_action_run(item) for item in runtime.get("recent_actions", [])]
    return Response({"runtime": runtime})


@extend_schema(
    tags=["v2"],
    summary="List runtime action history",
    responses={
        200: RuntimeActionListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_runtime_control_actions(request, runtime_id: str):
    denied = _ensure_manage_runtime_controls(request)
    if denied is not None:
        return denied
    if not any(item["runtime_id"] == runtime_id for item in list_runtime_instances()):
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Runtime not found"}},
            status=status.HTTP_404_NOT_FOUND,
        )
    actions = [
        serialize_runtime_action_run(item)
        for item in get_runtime_action_queryset().filter(runtime_id=runtime_id).order_by("-requested_at")[:25]
    ]
    return Response({"actions": actions})


@extend_schema(
    tags=["v2"],
    summary="Create runtime action",
    request=RuntimeActionCreateSerializer,
    responses={
        202: RuntimeActionResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_runtime_control_action(request):
    denied = _ensure_manage_runtime_controls(request)
    if denied is not None:
        return denied
    serializer = RuntimeActionCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        action_run = create_runtime_action_run(
            runtime_id=serializer.validated_data["runtime_id"],
            action_type=serializer.validated_data["action_type"],
            actor=request.user,
            reason=serializer.validated_data.get("reason", ""),
            target_job_name=serializer.validated_data.get("target_job_name", ""),
            request_payload=dict(serializer.validated_data),
        )
    except (KeyError, ValueError) as exc:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response({"action": serialize_runtime_action_run(action_run)}, status=status.HTTP_202_ACCEPTED)


@extend_schema(
    tags=["v2"],
    summary="Get runtime action",
    responses={
        200: RuntimeActionResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_runtime_control_action(request, action_id: str):
    denied = _ensure_manage_runtime_controls(request)
    if denied is not None:
        return denied
    try:
        action_run = get_runtime_action_run(action_id)
    except RuntimeActionRun.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Action not found"}},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response({"action": serialize_runtime_action_run(action_run)})


@extend_schema(
    tags=["v2"],
    summary="Patch runtime desired state",
    request=RuntimeDesiredStatePatchSerializer,
    responses={
        200: RuntimeDesiredStateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ErrorResponseSerializer,
    },
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def patch_runtime_control_desired_state(request, runtime_id: str):
    denied = _ensure_manage_runtime_controls(request)
    if denied is not None:
        return denied
    serializer = RuntimeDesiredStatePatchSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        desired_state = update_runtime_desired_state(
            runtime_id,
            scheduler_enabled=serializer.validated_data.get("scheduler_enabled"),
            jobs=serializer.validated_data.get("jobs", []),
        )
    except (KeyError, ValueError) as exc:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response({"runtime_id": runtime_id, "desired_state": desired_state})


@extend_schema(
    tags=["v2"],
    summary="List runtime scheduler jobs",
    responses={
        200: RuntimeSchedulerJobsResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_runtime_control_scheduler_jobs(request):
    denied = _ensure_manage_runtime_controls(request)
    if denied is not None:
        return denied
    return Response({
        "jobs": list_scheduler_jobs(),
        "desired_state": get_scheduler_desired_state(),
    })
