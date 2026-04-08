from __future__ import annotations
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.api_v2 import observability


@pytest.fixture
def authenticated_client() -> APIClient:
    user = User.objects.create_user(
        username=f"request-correlation-{uuid4().hex[:8]}",
        password="pass",
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
    payload = response.json()
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
    payload = response.json()
    assert payload["code"] == "POOL_NOT_FOUND"
    assert payload["request_id"].startswith("req-")
    assert "ui_action_id" not in payload
    assert response.headers["X-Request-ID"] == payload["request_id"]


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
