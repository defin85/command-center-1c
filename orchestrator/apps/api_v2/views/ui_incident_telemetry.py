from __future__ import annotations

from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from apps.api_v2.observability import (
    apply_correlation_headers,
    log_problem_response,
    with_problem_correlation,
)
from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
from apps.monitoring.ui_incident_telemetry import (
    get_ui_incident_timeline,
    ingest_ui_incident_telemetry_batch,
    list_ui_incident_summaries,
)
from apps.tenancy.authentication import TENANT_HEADER
from apps.tenancy.models import Tenant


def _resolve_request_tenant_id(request) -> str | None:
    tenant_id = str(getattr(request, "tenant_id", "") or "").strip()
    if tenant_id:
        return tenant_id
    raw = request.META.get(TENANT_HEADER)
    if raw is None and getattr(request, "_request", None) is not None:
        raw = request._request.META.get(TENANT_HEADER)
    raw_value = str(raw or "").strip()
    return raw_value or None


def _problem(*, code: str, title: str, detail: str, status_code: int) -> Response:
    payload = with_problem_correlation(
        {
            "type": "about:blank",
            "title": title,
            "status": status_code,
            "code": code,
            "detail": detail,
        }
    )
    log_problem_response(payload)
    response = Response(
        payload,
        status=status_code,
        content_type="application/problem+json",
    )
    return apply_correlation_headers(response)


class UiIncidentTelemetryIngestRequestSerializer(serializers.Serializer):
    batch_id = serializers.CharField(max_length=160)
    flush_reason = serializers.ChoiceField(
        choices=["size_threshold", "time_threshold", "pagehide", "shutdown", "manual"],
    )
    session_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    tenant_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    actor = serializers.JSONField(required=False)
    release = serializers.JSONField(required=False)
    route = serializers.JSONField(required=False)
    dropped_events_count = serializers.IntegerField(required=False, min_value=0, default=0)
    events = serializers.ListField(child=serializers.JSONField(), allow_empty=False)


class UiIncidentTelemetryIngestResponseSerializer(serializers.Serializer):
    batch_id = serializers.CharField()
    accepted_events = serializers.IntegerField()
    duplicate_events = serializers.IntegerField()
    dropped_events = serializers.IntegerField()
    duplicate = serializers.BooleanField()
    retention_cutoff = serializers.DateTimeField()


class UiIncidentSummaryPreviewSerializer(serializers.Serializer):
    action_kind = serializers.CharField(required=False, allow_null=True)
    action_name = serializers.CharField(required=False, allow_null=True)
    error_code = serializers.CharField(required=False, allow_null=True)
    error_title = serializers.CharField(required=False, allow_null=True)
    error_name = serializers.CharField(required=False, allow_null=True)
    error_message = serializers.CharField(required=False, allow_null=True)
    outcome = serializers.CharField(required=False, allow_null=True)
    status = serializers.IntegerField(required=False, allow_null=True)
    latency_ms = serializers.IntegerField(required=False, allow_null=True)
    method = serializers.CharField(required=False, allow_null=True)
    path = serializers.CharField(required=False, allow_null=True)
    owner = serializers.CharField(required=False, allow_null=True)
    reuse_key = serializers.CharField(required=False, allow_null=True)


class UiIncidentSummarySerializer(serializers.Serializer):
    incident_id = serializers.CharField()
    actor_username = serializers.CharField(required=False, allow_null=True)
    user_id = serializers.IntegerField(required=False, allow_null=True)
    session_id = serializers.CharField(required=False, allow_null=True)
    request_id = serializers.CharField(required=False, allow_null=True)
    ui_action_id = serializers.CharField(required=False, allow_null=True)
    route_path = serializers.CharField(required=False, allow_null=True)
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField()
    signal_event_types = serializers.ListField(child=serializers.CharField())
    signal_count = serializers.IntegerField()
    last_event_type = serializers.CharField()
    preview = UiIncidentSummaryPreviewSerializer()


class UiIncidentSummaryListResponseSerializer(serializers.Serializer):
    incidents = UiIncidentSummarySerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class UiIncidentTimelineEventSerializer(serializers.Serializer):
    batch_id = serializers.CharField()
    event_id = serializers.CharField()
    event_type = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    actor_username = serializers.CharField(required=False, allow_null=True)
    user_id = serializers.IntegerField(required=False, allow_null=True)
    session_id = serializers.CharField(required=False, allow_null=True)
    request_id = serializers.CharField(required=False, allow_null=True)
    ui_action_id = serializers.CharField(required=False, allow_null=True)
    trace_id = serializers.CharField(required=False, allow_null=True)
    route = serializers.JSONField()
    payload = serializers.JSONField()


class UiIncidentTimelineResponseSerializer(serializers.Serializer):
    timeline = UiIncidentTimelineEventSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class UiIncidentQuerySerializer(serializers.Serializer):
    actor_username = serializers.CharField(required=False, allow_blank=True)
    user_id = serializers.IntegerField(required=False)
    session_id = serializers.CharField(required=False, allow_blank=True)
    request_id = serializers.CharField(required=False, allow_blank=True)
    ui_action_id = serializers.CharField(required=False, allow_blank=True)
    route_path = serializers.CharField(required=False, allow_blank=True)
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=500, default=100)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)


@extend_schema(
    tags=["v2"],
    operation_id="v2_ui_incident_telemetry_ingest",
    summary="Ingest redacted UI incident telemetry batch",
    request=UiIncidentTelemetryIngestRequestSerializer,
    responses={
        202: UiIncidentTelemetryIngestResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ingest_ui_incident_telemetry(request):
    serializer = UiIncidentTelemetryIngestRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=400,
        )

    tenant_id = _resolve_request_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=400,
        )

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=404,
        )

    result = ingest_ui_incident_telemetry_batch(
        tenant=tenant,
        actor_user=request.user,
        envelope=dict(serializer.validated_data),
    )
    return Response(result, status=202)


@extend_schema(
    tags=["v2"],
    operation_id="v2_ui_incident_telemetry_incidents",
    summary="List recent UI incident summaries",
    parameters=[
        OpenApiParameter("actor_username", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("user_id", int, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("session_id", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("request_id", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("ui_action_id", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("route_path", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("start", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("end", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("offset", int, OpenApiParameter.QUERY, required=False),
    ],
    responses={
        200: UiIncidentSummaryListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_recent_ui_incident_summaries(request):
    if not request.user.is_staff:
        return _problem(
            code="FORBIDDEN",
            title="Forbidden",
            detail="Staff only.",
            status_code=403,
        )

    tenant_id = _resolve_request_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=400,
        )

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=404,
        )

    serializer = UiIncidentQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=400,
        )

    payload = list_ui_incident_summaries(
        tenant=tenant,
        actor_username=serializer.validated_data.get("actor_username", ""),
        user_id=serializer.validated_data.get("user_id"),
        session_id=serializer.validated_data.get("session_id", ""),
        request_id=serializer.validated_data.get("request_id", ""),
        ui_action_id=serializer.validated_data.get("ui_action_id", ""),
        route_path=serializer.validated_data.get("route_path", ""),
        started_at=serializer.validated_data.get("start"),
        ended_at=serializer.validated_data.get("end"),
        limit=serializer.validated_data.get("limit", 100),
        offset=serializer.validated_data.get("offset", 0),
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    operation_id="v2_ui_incident_telemetry_timeline",
    summary="Get ordered UI incident timeline",
    parameters=[
        OpenApiParameter("actor_username", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("user_id", int, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("session_id", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("request_id", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("ui_action_id", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("route_path", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("start", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("end", str, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("offset", int, OpenApiParameter.QUERY, required=False),
    ],
    responses={
        200: UiIncidentTimelineResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_recent_ui_incident_timeline(request):
    if not request.user.is_staff:
        return _problem(
            code="FORBIDDEN",
            title="Forbidden",
            detail="Staff only.",
            status_code=403,
        )

    tenant_id = _resolve_request_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=400,
        )

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=404,
        )

    serializer = UiIncidentQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=400,
        )

    payload = get_ui_incident_timeline(
        tenant=tenant,
        actor_username=serializer.validated_data.get("actor_username", ""),
        user_id=serializer.validated_data.get("user_id"),
        session_id=serializer.validated_data.get("session_id", ""),
        request_id=serializer.validated_data.get("request_id", ""),
        ui_action_id=serializer.validated_data.get("ui_action_id", ""),
        route_path=serializer.validated_data.get("route_path", ""),
        started_at=serializer.validated_data.get("start"),
        ended_at=serializer.validated_data.get("end"),
        limit=serializer.validated_data.get("limit", 100),
        offset=serializer.validated_data.get("offset", 0),
    )
    return Response(payload)
