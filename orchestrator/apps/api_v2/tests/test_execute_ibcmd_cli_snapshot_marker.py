# ruff: noqa: F811
import pytest
from rest_framework.test import APIClient

from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from apps.databases.models import Database
from apps.operations.models import BatchOperation
from apps.operations.redis_client import redis_client
from apps.operations.services import EnqueueResult, OperationsService
from apps.tenancy.models import Tenant, TenantMember

from . import _execute_ibcmd_cli_support as support


@pytest.mark.django_db
def test_execute_ibcmd_cli_does_not_set_snapshot_marker_from_action_catalog_runtime(monkeypatch):
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
                "params_by_name": {
                    "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
                },
            },
        },
    }
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}})

    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    user = User.objects.create_user(username="snap_marker_user", password="pass", is_staff=True)
    TenantMember.objects.get_or_create(tenant=tenant, user=user, defaults={"role": TenantMember.ROLE_ADMIN})

    db = Database.objects.create(
        tenant=tenant,
        name="db",
        host="localhost",
        port=80,
        base_name="db",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )

    client = APIClient()
    ct = ContentType.objects.get(app_label="operations", model="batchoperation")
    perm = Permission.objects.get(content_type=ct, codename="execute_safe_operation")
    user.user_permissions.add(perm)
    support._allow_operate(user, db)

    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    token_resp = client.post("/api/token/", {"username": user.username, "password": "pass"}, format="json")
    assert token_resp.status_code == 200
    access = token_resp.json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {"command_id": "infobase.extension.list", "database_ids": [db.id], "connection": {"remote": "http://host:1545"}},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 202
    op_id = resp.json()["operation_id"]
    op = BatchOperation.objects.get(id=op_id)
    assert (op.metadata or {}).get("snapshot_kinds") is None
    assert (op.metadata or {}).get("snapshot_source") is None
