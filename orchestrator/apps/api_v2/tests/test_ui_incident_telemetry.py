from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.monitoring.models import UiIncidentTelemetryBatch, UiIncidentTelemetryEvent
from apps.monitoring.ui_incident_telemetry import cleanup_expired_ui_incident_telemetry
from apps.tenancy.models import Tenant, TenantMember


def _load_openapi_contract() -> dict:
    contract_path = (
        Path(__file__).resolve().parents[4] / "contracts" / "orchestrator" / "openapi.yaml"
    )
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


@pytest.fixture
def tenant() -> Tenant:
    return Tenant.objects.create(
        slug=f"tenant-{uuid4().hex[:8]}",
        name=f"Tenant {uuid4().hex[:8]}",
    )


@pytest.fixture
def member_user() -> User:
    return User.objects.create_user(
        username=f"ui-telemetry-member-{uuid4().hex[:8]}",
        password="pass",
    )


@pytest.fixture
def staff_user() -> User:
    return User.objects.create_user(
        username=f"ui-telemetry-staff-{uuid4().hex[:8]}",
        password="pass",
        is_staff=True,
    )


@pytest.fixture
def member_client(member_user: User, tenant: Tenant) -> APIClient:
    TenantMember.objects.create(user=member_user, tenant=tenant, role=TenantMember.ROLE_MEMBER)
    client = APIClient()
    client.force_authenticate(user=member_user)
    return client


@pytest.fixture
def staff_client(staff_user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


def _event(
    *,
    event_id: str,
    event_type: str,
    occurred_at: str,
    session_id: str = "session-1",
    request_id: str | None = None,
    ui_action_id: str | None = None,
) -> dict:
    payload = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "route": {
            "path": "/pools/runs",
            "search": "?tab=create&token=secret-value",
            "hash": "#workflow=wf-services-r4",
            "context": {
                "tab": "create",
                "token": "secret-value",
            },
        },
        "context": {
            "pool": "pool-1",
            "password": "should-not-store",
        },
    }
    if request_id:
        payload["request_id"] = request_id
    if ui_action_id:
        payload["ui_action_id"] = ui_action_id
    if session_id:
        payload["trace_id"] = f"trace-{event_id}"
    if event_type == "ui.action":
        payload.update({
            "action_kind": "modal.submit",
            "action_name": "Create pool run",
            "ui_action_id": ui_action_id,
        })
    if event_type == "route.transition":
        payload.update({
            "ui_action_id": ui_action_id,
            "surface_id": "pool_master_data",
            "route_writer_owner": "pool_master_data_page",
            "write_reason": "zone_switch",
            "navigation_mode": "push",
            "param_diff": {"tab": {"from": "bindings", "to": "sync"}},
            "caused_by_ui_action_id": ui_action_id,
        })
    if event_type == "route.loop_warning":
        payload.update({
            "ui_action_id": ui_action_id,
            "surface_id": "pool_master_data",
            "route_path": "/pools/master-data",
            "oscillating_keys": ["tab"],
            "writer_owners": ["pool_master_data_page"],
            "transition_count": 4,
            "window_ms": 1800,
        })
    if event_type == "http.request.failure":
        payload.update({
            "request_id": request_id,
            "ui_action_id": ui_action_id,
            "method": "POST",
            "path": "/api/v2/pools/runs/",
            "status": 500,
            "error_code": "POOL_RUN_FAILED",
            "error_title": "Pool Run Failed",
        })
    if event_type == "ui.error.boundary":
        payload.update({
            "ui_action_id": ui_action_id,
            "error_name": "Error",
            "error_message": "token=super-secret",
            "component_stack": "stack:line-1",
        })
    return payload


@pytest.mark.django_db
def test_ingest_ui_incident_telemetry_stores_redacted_events_and_is_duplicate_safe(
    member_client: APIClient,
    member_user: User,
    tenant: Tenant,
) -> None:
    body = {
        "batch_id": "batch-1",
        "flush_reason": "size_threshold",
        "session_id": "session-1",
        "release": {
            "app": "commandcenter1c-frontend",
            "fingerprint": "1.0.0+build",
            "mode": "test",
            "origin": "http://localhost:15173",
        },
        "route": {
            "path": "/pools/runs",
            "search": "?tab=create&token=secret",
            "hash": "#workflow=wf-services-r4",
            "context": {
                "tab": "create",
                "token": "secret",
            },
        },
        "events": [
            _event(
                event_id="evt-0",
                event_type="route.transition",
                occurred_at="2026-04-19T11:59:58Z",
                ui_action_id="uia-1",
            ),
            _event(
                event_id="evt-1",
                event_type="ui.action",
                occurred_at="2026-04-19T12:00:00Z",
                ui_action_id="uia-1",
            ),
            _event(
                event_id="evt-2",
                event_type="http.request.failure",
                occurred_at="2026-04-19T12:00:05Z",
                request_id="req-1",
                ui_action_id="uia-1",
            ),
            _event(
                event_id="evt-3",
                event_type="ui.error.boundary",
                occurred_at="2026-04-19T12:00:06Z",
                ui_action_id="uia-1",
            ),
            _event(
                event_id="evt-4",
                event_type="route.loop_warning",
                occurred_at="2026-04-19T12:00:07Z",
                ui_action_id="uia-1",
            ),
        ],
    }

    response = member_client.post(
        "/api/v2/ui/incident-telemetry/ingest/",
        body,
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
        HTTP_X_REQUEST_ID="req-ingest-1",
        HTTP_X_UI_ACTION_ID="uia-ingest-1",
    )

    assert response.status_code == 202
    assert response.data["accepted_events"] == 5
    assert response.data["duplicate"] is False
    assert UiIncidentTelemetryBatch.objects.count() == 1
    assert UiIncidentTelemetryEvent.objects.count() == 5

    event = UiIncidentTelemetryEvent.objects.get(event_id="evt-4")
    assert event.actor_user_id == member_user.id
    assert event.actor_username == member_user.username
    assert event.route_path == "/pools/runs"
    assert event.route_context == {"tab": "create"}
    assert event.payload["surface_id"] == "pool_master_data"
    assert event.payload["writer_owners"] == ["pool_master_data_page"]
    assert "super-secret" not in str(event.payload)
    assert "should-not-store" not in str(event.payload)
    assert "secret-value" not in str(event.payload)

    duplicate_response = member_client.post(
        "/api/v2/ui/incident-telemetry/ingest/",
        body,
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert duplicate_response.status_code == 202
    assert duplicate_response.data["duplicate"] is True
    assert UiIncidentTelemetryBatch.objects.count() == 1
    assert UiIncidentTelemetryEvent.objects.count() == 5


@pytest.mark.django_db
def test_recent_ui_incident_queries_are_staff_only_and_tenant_scoped(
    member_client: APIClient,
    staff_client: APIClient,
    member_user: User,
    tenant: Tenant,
) -> None:
    occurred_at = timezone.now()
    UiIncidentTelemetryBatch.objects.create(
        tenant=tenant,
        actor_user=member_user,
        actor_username=member_user.username,
        batch_id="batch-summary",
        flush_reason="manual",
        session_id="session-summary",
        release_app="commandcenter1c-frontend",
        release_fingerprint="frontend@2026.04.19+42",
        release_mode="prod",
        release_origin="https://cc1c.example.test",
        accepted_event_count=3,
        last_occurred_at=occurred_at,
    )
    batch = UiIncidentTelemetryBatch.objects.get(batch_id="batch-summary")
    UiIncidentTelemetryEvent.objects.create(
        tenant=tenant,
        batch=batch,
        actor_user=member_user,
        actor_username=member_user.username,
        session_id="session-summary",
        event_id="evt-summary-action",
        event_type="ui.action",
        occurred_at=occurred_at - timedelta(seconds=2),
        route_path="/pools/master-data",
        ui_action_id="uia-summary",
        trace_id="trace-summary",
        payload={
            "action_kind": "route.change",
            "action_name": "Open Sync zone",
            "surface_id": "pool_master_data",
            "control_id": "zone.sync",
        },
    )
    UiIncidentTelemetryEvent.objects.create(
        tenant=tenant,
        batch=batch,
        actor_user=member_user,
        actor_username=member_user.username,
        session_id="session-summary",
        event_id="evt-summary-transition",
        event_type="route.transition",
        occurred_at=occurred_at - timedelta(seconds=1),
        route_path="/pools/master-data",
        ui_action_id="uia-summary",
        trace_id="trace-summary",
        payload={
            "surface_id": "pool_master_data",
            "route_writer_owner": "pool_master_data_page",
            "write_reason": "zone_switch",
            "navigation_mode": "push",
            "param_diff": {"tab": {"from": "bindings", "to": "sync"}},
            "caused_by_ui_action_id": "uia-summary",
        },
    )
    UiIncidentTelemetryEvent.objects.create(
        tenant=tenant,
        batch=batch,
        actor_user=member_user,
        actor_username=member_user.username,
        session_id="session-summary",
        event_id="evt-summary",
        event_type="route.loop_warning",
        occurred_at=occurred_at,
        route_path="/pools/master-data",
        ui_action_id="uia-summary",
        trace_id="trace-summary",
        payload={
            "surface_id": "pool_master_data",
            "route_writer_owner": "pool_master_data_page",
            "write_reason": "zone_switch",
            "oscillating_keys": ["tab"],
            "writer_owners": ["pool_master_data_page"],
            "transition_count": 4,
            "window_ms": 1800,
        },
    )

    forbidden = member_client.get(
        "/api/v2/ui/incident-telemetry/incidents/",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )
    assert forbidden.status_code == 403

    response = staff_client.get(
        "/api/v2/ui/incident-telemetry/incidents/",
        {
            "actor_username": member_user.username,
            "trace_id": "trace-summary",
        },
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["incidents"][0]["request_id"] is None
    assert response.data["incidents"][0]["trace_id"] == "trace-summary"
    assert response.data["incidents"][0]["actor_username"] == member_user.username
    assert response.data["incidents"][0]["release"]["fingerprint"] == "frontend@2026.04.19+42"
    assert response.data["incidents"][0]["signal_event_types"] == ["route.loop_warning"]
    assert response.data["incidents"][0]["preview"] == {
        "action_kind": "route.change",
        "action_name": "Open Sync zone",
        "caused_by_ui_action_id": "uia-summary",
        "control_id": "zone.sync",
        "navigation_mode": "push",
        "param_diff": {"tab": {"from": "bindings", "to": "sync"}},
        "surface_id": "pool_master_data",
        "route_writer_owner": "pool_master_data_page",
        "write_reason": "zone_switch",
        "oscillating_keys": ["tab"],
        "writer_owners": ["pool_master_data_page"],
        "transition_count": 4,
        "window_ms": 1800,
    }


@pytest.mark.django_db
def test_recent_ui_incident_timeline_expands_around_request_correlation(
    staff_client: APIClient,
    member_user: User,
    tenant: Tenant,
) -> None:
    started_at = timezone.now()
    batch = UiIncidentTelemetryBatch.objects.create(
        tenant=tenant,
        actor_user=member_user,
        actor_username=member_user.username,
        batch_id="batch-timeline",
        flush_reason="manual",
        session_id="session-timeline",
        release_app="commandcenter1c-frontend",
        release_fingerprint="frontend@2026.04.19+99",
        release_mode="prod",
        accepted_event_count=5,
        first_occurred_at=started_at,
        last_occurred_at=started_at + timedelta(seconds=7),
    )
    UiIncidentTelemetryEvent.objects.bulk_create([
        UiIncidentTelemetryEvent(
            tenant=tenant,
            batch=batch,
            actor_user=member_user,
            actor_username=member_user.username,
            session_id="session-timeline",
            event_id="evt-route",
            event_type="route.transition",
            occurred_at=started_at,
            route_path="/pools/runs",
            ui_action_id="uia-timeline",
            trace_id="trace-timeline",
            payload={
                "outcome": "navigated",
                "surface_id": "pool_master_data",
                "route_writer_owner": "pool_master_data_page",
                "write_reason": "zone_switch",
                "navigation_mode": "push",
                "param_diff": {"tab": {"from": "bindings", "to": "sync"}},
                "caused_by_ui_action_id": "uia-timeline",
            },
        ),
        UiIncidentTelemetryEvent(
            tenant=tenant,
            batch=batch,
            actor_user=member_user,
            actor_username=member_user.username,
            session_id="session-timeline",
            event_id="evt-action",
            event_type="ui.action",
            occurred_at=started_at + timedelta(seconds=2),
            route_path="/pools/runs",
            ui_action_id="uia-timeline",
            trace_id="trace-timeline",
            payload={"action_name": "Create pool run"},
        ),
        UiIncidentTelemetryEvent(
            tenant=tenant,
            batch=batch,
            actor_user=member_user,
            actor_username=member_user.username,
            session_id="session-timeline",
            event_id="evt-failure",
            event_type="http.request.failure",
            occurred_at=started_at + timedelta(seconds=5),
            route_path="/pools/runs",
            request_id="req-timeline",
            ui_action_id="uia-timeline",
            trace_id="trace-timeline",
            payload={"error_code": "POOL_RUN_FAILED"},
        ),
        UiIncidentTelemetryEvent(
            tenant=tenant,
            batch=batch,
            actor_user=member_user,
            actor_username=member_user.username,
            session_id="session-timeline",
            event_id="evt-error",
            event_type="ui.error.boundary",
            occurred_at=started_at + timedelta(seconds=6),
            route_path="/pools/runs",
            ui_action_id="uia-timeline",
            trace_id="trace-timeline",
            payload={"error_message": "render failed"},
        ),
        UiIncidentTelemetryEvent(
            tenant=tenant,
            batch=batch,
            actor_user=member_user,
            actor_username=member_user.username,
            session_id="session-timeline",
            event_id="evt-loop",
            event_type="route.loop_warning",
            occurred_at=started_at + timedelta(seconds=7),
            route_path="/pools/runs",
            ui_action_id="uia-timeline",
            trace_id="trace-timeline",
            payload={
                "surface_id": "pool_master_data",
                "oscillating_keys": ["tab"],
                "writer_owners": ["pool_master_data_page"],
                "transition_count": 4,
                "window_ms": 1800,
            },
        ),
    ])

    response = staff_client.get(
        "/api/v2/ui/incident-telemetry/timeline/",
        {"trace_id": "trace-timeline"},
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert response.status_code == 200
    assert [event["event_id"] for event in response.data["timeline"]] == [
        "evt-route",
        "evt-action",
        "evt-failure",
        "evt-error",
        "evt-loop",
    ]
    assert response.data["timeline"][1]["trace_id"] == "trace-timeline"
    assert response.data["timeline"][1]["release"]["fingerprint"] == "frontend@2026.04.19+99"
    assert response.data["timeline"][0]["payload"]["route_writer_owner"] == "pool_master_data_page"
    assert response.data["timeline"][4]["payload"]["oscillating_keys"] == ["tab"]


@pytest.mark.django_db
def test_cleanup_expired_ui_incident_telemetry_removes_old_batches(
    tenant: Tenant,
    member_user: User,
) -> None:
    now = timezone.now()
    old_batch = UiIncidentTelemetryBatch.objects.create(
        tenant=tenant,
        actor_user=member_user,
        actor_username=member_user.username,
        batch_id="batch-old",
        flush_reason="manual",
        session_id="session-old",
        accepted_event_count=1,
        first_occurred_at=now - timedelta(days=30),
        last_occurred_at=now - timedelta(days=30),
        created_at=now - timedelta(days=30),
    )
    UiIncidentTelemetryEvent.objects.create(
        tenant=tenant,
        batch=old_batch,
        actor_user=member_user,
        actor_username=member_user.username,
        session_id="session-old",
        event_id="evt-old",
        event_type="http.request.failure",
        occurred_at=now - timedelta(days=30),
        route_path="/pools/runs",
        payload={"error_code": "POOL_RUN_FAILED"},
    )
    fresh_batch = UiIncidentTelemetryBatch.objects.create(
        tenant=tenant,
        actor_user=member_user,
        actor_username=member_user.username,
        batch_id="batch-fresh",
        flush_reason="manual",
        session_id="session-fresh",
        accepted_event_count=1,
        first_occurred_at=now,
        last_occurred_at=now,
    )
    UiIncidentTelemetryEvent.objects.create(
        tenant=tenant,
        batch=fresh_batch,
        actor_user=member_user,
        actor_username=member_user.username,
        session_id="session-fresh",
        event_id="evt-fresh",
        event_type="http.request.failure",
        occurred_at=now,
        route_path="/pools/runs",
        payload={"error_code": "POOL_RUN_FAILED"},
    )

    cleanup_expired_ui_incident_telemetry(now=now)

    assert UiIncidentTelemetryBatch.objects.filter(batch_id="batch-old").exists() is False
    assert UiIncidentTelemetryEvent.objects.filter(event_id="evt-old").exists() is False
    assert UiIncidentTelemetryBatch.objects.filter(batch_id="batch-fresh").exists() is True


def test_generated_openapi_marks_tenant_header_required_for_ui_incident_telemetry_paths() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    for path, method in (
        ("/api/v2/ui/incident-telemetry/ingest/", "post"),
        ("/api/v2/ui/incident-telemetry/incidents/", "get"),
        ("/api/v2/ui/incident-telemetry/timeline/", "get"),
    ):
        path_item = paths.get(path)
        assert isinstance(path_item, dict), f"path not found: {path}"
        operation = path_item.get(method)
        assert isinstance(operation, dict), f"operation not found: {method} {path}"

        parameters = operation.get("parameters")
        assert isinstance(parameters, list), f"parameters missing: {method} {path}"
        tenant_headers = [
            item
            for item in parameters
            if isinstance(item, dict)
            and item.get("name") == "X-CC1C-Tenant-ID"
            and item.get("in") == "header"
        ]
        assert len(tenant_headers) == 1, f"unexpected tenant header count for {method} {path}"
        assert tenant_headers[0]["required"] is True
        assert tenant_headers[0]["description"] == (
            "Required tenant context selector for UI incident telemetry ingest and staff diagnostics queries."
        )


def test_generated_openapi_exposes_ui_incident_summary_preview_route_intent_fields() -> None:
    contract = _load_openapi_contract()
    components = contract.get("components")
    assert isinstance(components, dict)
    schemas = components.get("schemas")
    assert isinstance(schemas, dict)
    preview = schemas.get("UiIncidentSummaryPreview")
    assert isinstance(preview, dict)
    properties = preview.get("properties")
    assert isinstance(properties, dict)

    expected_properties = {
        "caused_by_ui_action_id",
        "control_id",
        "navigation_mode",
        "oscillating_keys",
        "param_diff",
        "route_writer_owner",
        "surface_id",
        "transition_count",
        "window_ms",
        "write_reason",
        "writer_owners",
    }

    missing = sorted(expected_properties.difference(properties))
    assert missing == []
