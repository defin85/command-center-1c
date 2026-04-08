from __future__ import annotations
import json
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.api_v2 import observability
from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.api_v2.views import intercompany_pools
from apps.api_v2.views.clusters.common import ClusterErrorResponseSerializer
from apps.api_v2.views.databases.common import (
    DatabaseErrorResponseSerializer,
    DatabaseStreamConflictResponseSerializer,
)
from apps.api_v2.views.extensions_plan_apply import ExtensionsApplyConflictSerializer
from apps.api_v2.views.operations.schemas import OperationErrorResponseSerializer
from apps.api_v2.views.rbac.serializers_core import RbacErrorResponseSerializer
from apps.api_v2.views.service_mesh import ServiceMeshErrorResponseSerializer
from apps.api_v2.views.timeline import TimelineErrorResponseSerializer
from apps.api_v2.views.ui.common import UiErrorResponseSerializer
from apps.api_v2.views.users import UserErrorResponseSerializer
from apps.api_v2.views.workflows.common import WorkflowEnqueueFailClosedErrorResponseSerializer


@pytest.fixture
def authenticated_client() -> APIClient:
    user = User.objects.create_user(
        username=f"request-correlation-{uuid4().hex[:8]}",
        password="pass",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff_client() -> APIClient:
    user = User.objects.create_user(
        username=f"request-correlation-staff-{uuid4().hex[:8]}",
        password="pass",
        is_staff=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_shared_problem_helper_includes_request_correlation_fields(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.get(
        "/api/v2/pools/binding-profiles/",
        HTTP_X_CC1C_TENANT_ID="00000000-0000-0000-0000-000000000000",
        HTTP_X_REQUEST_ID="req-ui-1",
        HTTP_X_UI_ACTION_ID="uia-1",
    )

    assert response.status_code == 404
    payload = json.loads(response.content)
    assert payload["code"] == "TENANT_NOT_FOUND"
    assert payload["request_id"] == "req-ui-1"
    assert payload["ui_action_id"] == "uia-1"
    assert response.headers["X-Request-ID"] == "req-ui-1"
    assert response.headers["X-UI-Action-ID"] == "uia-1"


@pytest.mark.django_db
def test_local_problem_helper_includes_generated_request_id_when_header_missing(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        f"/api/v2/pools/{uuid4()}/document-policy-migrations/",
        {},
        HTTP_X_CC1C_TENANT_ID="00000000-0000-0000-0000-000000000000",
        format="json",
    )

    assert response.status_code == 404
    payload = json.loads(response.content)
    assert payload["code"] == "POOL_NOT_FOUND"
    assert payload["request_id"].startswith("req-")
    assert "ui_action_id" not in payload
    assert response.headers["X-Request-ID"] == payload["request_id"]


def test_request_correlation_middleware_enriches_legacy_json_error_payloads() -> None:
    request = RequestFactory().get(
        "/api/v2/legacy-json/",
        HTTP_X_REQUEST_ID="req-ui-legacy",
        HTTP_X_UI_ACTION_ID="uia-legacy",
    )
    middleware = observability.RequestCorrelationMiddleware(
        lambda _request: JsonResponse(
            {"success": False, "error": {"code": "LEGACY_FAILURE", "message": "boom"}},
            status=503,
        )
    )

    response = middleware(request)
    payload = json.loads(response.content)

    assert payload["error"]["code"] == "LEGACY_FAILURE"
    assert payload["request_id"] == "req-ui-legacy"
    assert payload["ui_action_id"] == "uia-legacy"
    assert response.headers["X-Request-ID"] == "req-ui-legacy"
    assert response.headers["X-UI-Action-ID"] == "uia-legacy"


def test_request_correlation_middleware_redacts_sensitive_fields_in_legacy_json_error_payloads() -> None:
    request = RequestFactory().get(
        "/api/v2/legacy-json/",
        HTTP_X_REQUEST_ID="req-ui-redacted",
        HTTP_X_UI_ACTION_ID="uia-redacted",
    )
    middleware = observability.RequestCorrelationMiddleware(
        lambda _request: JsonResponse(
            {
                "success": False,
                "error": {
                    "code": "LEGACY_FAILURE",
                    "message": "token=super-secret password=hunter2",
                },
                "detail": "Authorization=BearerSecret token=session-123",
                "details": {
                    "password": "top-secret",
                    "safe": "visible",
                    "nested": {
                        "api_key": "hidden",
                        "reason": "token=nested-secret",
                    },
                },
            },
            status=503,
        )
    )

    response = middleware(request)
    payload = json.loads(response.content)
    serialized = json.dumps(payload)

    assert payload["error"]["message"] == "token=[redacted] password=[redacted]"
    assert payload["detail"] == "Authorization=[redacted] token=[redacted]"
    assert payload["details"] == {
        "safe": "visible",
        "nested": {
            "reason": "token=[redacted]",
        },
    }
    assert payload["request_id"] == "req-ui-redacted"
    assert payload["ui_action_id"] == "uia-redacted"
    assert "super-secret" not in serialized
    assert "hunter2" not in serialized
    assert "top-secret" not in serialized
    assert "nested-secret" not in serialized


def test_intercompany_pools_problem_helper_redacts_errors_after_payload_assembly() -> None:
    request = RequestFactory().get(
        "/api/v2/pools/runs/",
        HTTP_X_REQUEST_ID="req-ui-problem",
        HTTP_X_UI_ACTION_ID="uia-problem",
    )
    correlation = observability.ensure_request_correlation(request)
    token = observability._current_request_correlation.set(correlation)

    try:
        response = intercompany_pools._problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail="token=top-level-secret",
            status_code=400,
            errors={
                "password": ["top-secret"],
                "nested": {
                    "token": "hidden",
                    "reason": "token=nested-secret",
                    "safe": "visible",
                },
            },
        )
    finally:
        observability._current_request_correlation.reset(token)

    payload = response.data
    serialized = json.dumps(payload)

    assert payload["detail"] == "token=[redacted]"
    assert payload["request_id"] == "req-ui-problem"
    assert payload["ui_action_id"] == "uia-problem"
    assert payload["errors"] == {
        "nested": {
            "reason": "token=[redacted]",
            "safe": "visible",
        },
    }
    assert "top-level-secret" not in serialized
    assert "top-secret" not in serialized
    assert "nested-secret" not in serialized


def test_workflow_failure_problem_details_redact_nested_error_details() -> None:
    payload = intercompany_pools._build_workflow_failure_problem_details(
        workflow_status="failed",
        projected_status="failed",
        workflow_failure_context={
            "error_code": "WORKFLOW_FAILED",
            "error_message": "token=super-secret",
            "error_details": {
                "password": "top-secret",
                "safe": "visible",
                "nested": {
                    "reason": "token=nested-secret",
                },
            },
        },
    )

    assert payload == {
        "type": "about:blank",
        "title": "Workflow Execution Failed",
        "status": 409,
        "detail": "token=[redacted]",
        "code": "WORKFLOW_FAILED",
        "error_details": {
            "safe": "visible",
            "nested": {
                "reason": "token=[redacted]",
            },
        },
    }


@pytest.mark.django_db
def test_runtime_settings_legacy_error_payload_includes_request_correlation_fields(
    staff_client: APIClient,
) -> None:
    response = staff_client.patch(
        "/api/v2/settings/runtime/missing-setting/",
        {"value": True},
        format="json",
        HTTP_X_REQUEST_ID="req-runtime-setting-1",
        HTTP_X_UI_ACTION_ID="uia-runtime-setting-1",
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["request_id"] == "req-runtime-setting-1"
    assert payload["ui_action_id"] == "uia-runtime-setting-1"
    assert response.headers["X-Request-ID"] == "req-runtime-setting-1"
    assert response.headers["X-UI-Action-ID"] == "uia-runtime-setting-1"


@pytest.mark.django_db
def test_dlq_legacy_error_payload_includes_request_correlation_fields(
    staff_client: APIClient,
) -> None:
    response = staff_client.get(
        "/api/v2/dlq/list/",
        {"filters": '{"unsupported":{"value":"x"}}'},
        HTTP_X_REQUEST_ID="req-dlq-1",
        HTTP_X_UI_ACTION_ID="uia-dlq-1",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNKNOWN_FILTER"
    assert payload["request_id"] == "req-dlq-1"
    assert payload["ui_action_id"] == "uia-dlq-1"
    assert response.headers["X-Request-ID"] == "req-dlq-1"
    assert response.headers["X-UI-Action-ID"] == "uia-dlq-1"


def test_log_problem_response_uses_current_request_correlation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = RequestFactory().get(
        "/api/v2/pools/binding-profiles/",
        HTTP_X_REQUEST_ID="req-ui-1",
        HTTP_X_UI_ACTION_ID="uia-1",
    )
    correlation = observability.ensure_request_correlation(request)
    token = observability._current_request_correlation.set(correlation)
    warning_calls: list[tuple[object, ...]] = []

    def record_warning(*args: object) -> None:
        warning_calls.append(args)

    monkeypatch.setattr(observability.logger, "warning", record_warning)

    try:
        observability.log_problem_response({
            "code": "TENANT_NOT_FOUND",
            "status": 404,
        })
    finally:
        observability._current_request_correlation.reset(token)

    assert len(warning_calls) == 1
    assert warning_calls[0][1:] == (
        "req-ui-1",
        "uia-1",
        "TENANT_NOT_FOUND",
        "404",
        "/api/v2/pools/binding-profiles/",
    )


def test_legacy_error_serializers_declare_request_correlation_fields() -> None:
    serializer_types = [
        ErrorResponseSerializer,
        ClusterErrorResponseSerializer,
        DatabaseErrorResponseSerializer,
        DatabaseStreamConflictResponseSerializer,
        ExtensionsApplyConflictSerializer,
        OperationErrorResponseSerializer,
        RbacErrorResponseSerializer,
        ServiceMeshErrorResponseSerializer,
        TimelineErrorResponseSerializer,
        UiErrorResponseSerializer,
        UserErrorResponseSerializer,
        WorkflowEnqueueFailClosedErrorResponseSerializer,
    ]

    for serializer_type in serializer_types:
        fields = serializer_type().fields
        assert "request_id" in fields
        assert "ui_action_id" in fields
        assert fields["request_id"].required is True
        assert fields["ui_action_id"].required is False
