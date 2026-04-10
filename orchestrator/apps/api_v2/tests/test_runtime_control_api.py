import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient

from apps.api_v2.views import runtime_control as runtime_control_view
from apps.core import permission_codes as perms
from apps.operations.models import RuntimeActionRun
from apps.operations.services import runtime_control as runtime_control_service
from apps.runtime_settings.models import RuntimeSetting


def _permission_by_code(code: str) -> Permission:
    app_label, codename = code.split(".", 1)
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def _runtime_inventory_item(runtime_name: str) -> dict[str, str]:
    return {
        "runtime": runtime_name,
        "type": "service",
        "stack": "local",
        "entrypoint": f"./debug/restart-runtime.sh {runtime_name}",
        "health": f"http://localhost/{runtime_name}/health",
    }


@pytest.fixture
def runtime_control_user() -> User:
    user = User.objects.create_user(username="runtime_control_staff", password="pass", is_staff=True)
    user.user_permissions.add(_permission_by_code(perms.PERM_OPERATIONS_MANAGE_RUNTIME_CONTROLS))
    return user


@pytest.fixture
def runtime_control_client(runtime_control_user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=runtime_control_user)
    return client


@pytest.mark.django_db
def test_runtime_control_catalog_requires_explicit_permission() -> None:
    user = User.objects.create_user(username="runtime_control_viewer", password="pass", is_staff=True)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v2/system/runtime-control/catalog/")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_runtime_control_catalog_returns_allowlisted_runtimes(
    runtime_control_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_id = runtime_control_service.build_runtime_id("worker-workflows")
    runtime_entry = {
        "runtime_id": runtime_id,
        "runtime_name": "worker-workflows",
        "display_name": "worker-workflows",
        "provider": {"key": "local_scripts", "host": "localhost"},
        "observed_state": {
            "status": "online",
            "process_status": "up(pid=123)",
            "http_status": "up(http=200)",
            "raw_probe": "worker-workflows proc=up(pid=123) http=up(http=200)",
            "command_status": "success",
        },
        "type": "service",
        "stack": "go",
        "entrypoint": "./scripts/dev/start.sh worker-workflows",
        "health": "http://localhost:8080/health",
        "supported_actions": ["probe", "restart", "tail_logs", "trigger_now"],
        "logs_available": True,
        "scheduler_supported": True,
        "desired_state": {
            "scheduler_enabled": True,
            "jobs": [
                {
                    "job_name": "pool_factual_active_sync",
                    "runtime_id": runtime_id,
                    "runtime_name": "worker-workflows",
                    "display_name": "Pool factual active sync",
                    "description": "Scans active pools.",
                    "enabled": True,
                    "schedule": "@every 120s",
                    "schedule_apply_mode": "controlled_restart",
                    "enablement_apply_mode": "live",
                    "latest_run_id": None,
                    "latest_run_status": None,
                    "latest_run_started_at": None,
                }
            ],
        },
    }
    monkeypatch.setattr(runtime_control_view, "list_runtime_instances", lambda: [runtime_entry])

    response = runtime_control_client.get("/api/v2/system/runtime-control/catalog/")

    assert response.status_code == 200
    assert response.json() == {"runtimes": [runtime_entry]}


@pytest.mark.django_db
def test_create_runtime_control_action_returns_accepted_and_persists_journal(
    runtime_control_client: APIClient,
    runtime_control_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_id = runtime_control_service.build_runtime_id("worker-workflows")
    dispatched: list[str] = []

    monkeypatch.setattr(
        runtime_control_service,
        "_runtime_inventory_by_id",
        lambda: {runtime_id: _runtime_inventory_item("worker-workflows")},
    )
    monkeypatch.setattr(
        runtime_control_service,
        "dispatch_runtime_action_run",
        lambda action_run: dispatched.append(str(action_run.id)),
    )

    response = runtime_control_client.post(
        "/api/v2/system/runtime-control/actions/",
        {
            "runtime_id": runtime_id,
            "action_type": "restart",
            "reason": "Apply scheduler runtime settings",
        },
        format="json",
    )

    assert response.status_code == 202
    payload = response.json()["action"]
    assert payload["runtime_id"] == runtime_id
    assert payload["action_type"] == "restart"
    assert payload["status"] == RuntimeActionRun.STATUS_ACCEPTED
    assert payload["requested_by_username"] == runtime_control_user.username
    assert dispatched == [payload["id"]]

    action_run = RuntimeActionRun.objects.get(id=payload["id"])
    assert action_run.reason == "Apply scheduler runtime settings"
    assert action_run.requested_by_id == runtime_control_user.id


@pytest.mark.django_db
def test_create_runtime_control_action_rejects_restart_without_reason(
    runtime_control_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_id = runtime_control_service.build_runtime_id("worker-workflows")
    monkeypatch.setattr(
        runtime_control_service,
        "_runtime_inventory_by_id",
        lambda: {runtime_id: _runtime_inventory_item("worker-workflows")},
    )

    response = runtime_control_client.post(
        "/api/v2/system/runtime-control/actions/",
        {"runtime_id": runtime_id, "action_type": "restart"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "Reason is required for restart" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_patch_runtime_control_desired_state_persists_global_scheduler_keys(
    runtime_control_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_id = runtime_control_service.build_runtime_id("worker-workflows")
    monkeypatch.setattr(
        runtime_control_service,
        "_runtime_inventory_by_id",
        lambda: {runtime_id: _runtime_inventory_item("worker-workflows")},
    )

    response = runtime_control_client.patch(
        f"/api/v2/system/runtime-control/runtimes/{runtime_id}/desired-state/",
        {
            "scheduler_enabled": False,
            "jobs": [
                {
                    "job_name": "pool_factual_active_sync",
                    "enabled": False,
                    "schedule": "0 */5 * * *",
                },
                {
                    "job_name": "pool_factual_closed_quarter_reconcile",
                    "enabled": True,
                    "schedule": "15 3 * * *",
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 200
    desired_state = response.json()["desired_state"]
    assert desired_state["scheduler_enabled"] is False
    jobs_by_name = {item["job_name"]: item for item in desired_state["jobs"]}
    assert jobs_by_name["pool_factual_active_sync"]["enabled"] is False
    assert jobs_by_name["pool_factual_active_sync"]["schedule"] == "0 */5 * * *"
    assert jobs_by_name["pool_factual_closed_quarter_reconcile"]["schedule"] == "15 3 * * *"

    assert RuntimeSetting.objects.get(key="runtime.scheduler.enabled").value is False
    assert RuntimeSetting.objects.get(key="runtime.scheduler.job.pool_factual_active_sync.enabled").value is False
    assert RuntimeSetting.objects.get(key="runtime.scheduler.job.pool_factual_active_sync.schedule").value == "0 */5 * * *"
    assert RuntimeSetting.objects.get(key="runtime.scheduler.job.pool_factual_closed_quarter_reconcile.enabled").value is True
    assert RuntimeSetting.objects.get(key="runtime.scheduler.job.pool_factual_closed_quarter_reconcile.schedule").value == "15 3 * * *"
