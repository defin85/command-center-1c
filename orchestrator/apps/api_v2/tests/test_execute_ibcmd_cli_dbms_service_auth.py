import pytest

from apps.operations.models import BatchOperation
from apps.operations.services import EnqueueResult, OperationsService

from . import _execute_ibcmd_cli_support as support
from ._execute_ibcmd_cli_support import client, staff_client, staff_user, target_dbs, user  # noqa: F401


@pytest.mark.django_db
def test_execute_ibcmd_cli_dbms_service_requires_permission(client, user, target_dbs, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.extension.list": {
                "label": "list extensions",
                "description": "List extensions",
                "argv": ["infobase", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    support._allow_operate(user, target_db)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "dbms_auth": {"strategy": "service"},
        },
        format="json",
    )
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_dbms_service_allowed_for_staff_on_allowlist(staff_client, staff_user, target_dbs, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.extension.list": {
                "label": "list extensions",
                "description": "List extensions",
                "argv": ["infobase", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(staff_client, staff_user, "execute_safe_operation")
    target_db = target_dbs[0]
    support._allow_operate(staff_user, target_db)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = staff_client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "dbms_auth": {"strategy": "service"},
        },
        format="json",
    )
    assert resp.status_code == 202
    op = BatchOperation.objects.get(id=resp.json()["operation_id"])
    assert op.payload["data"]["dbms_auth"]["strategy"] == "service"


@pytest.mark.django_db
def test_execute_ibcmd_cli_dbms_service_rejected_for_non_allowlist(staff_client, staff_user, target_dbs, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.dump": {
                "label": "dump",
                "description": "Dump",
                "argv": ["infobase", "dump"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(staff_client, staff_user, "execute_safe_operation")
    target_db = target_dbs[0]
    support._allow_operate(staff_user, target_db)

    resp = staff_client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.dump",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "dbms_auth": {"strategy": "service"},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "DBMS_AUTH_SERVICE_NOT_ALLOWED"
