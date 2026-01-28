# ruff: noqa: F811
import uuid

import pytest
from rest_framework.test import APIClient

from apps.operations.redis_client import redis_client

from . import _execute_ibcmd_cli_support as support
from ._execute_ibcmd_cli_support import auth_db, client, staff_client, staff_user, target_dbs, user  # noqa: F401


@pytest.mark.django_db
def test_execute_ibcmd_cli_requires_authentication():
    anon = APIClient()
    resp = anon.post("/api/v2/operations/execute-ibcmd-cli/", {}, format="json")
    assert resp.status_code in [401, 403]


@pytest.mark.django_db
def test_execute_ibcmd_cli_unknown_command_returns_400(client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {},
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {"command_id": "unknown.command", "database_ids": []},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNKNOWN_COMMAND"


@pytest.mark.django_db
def test_execute_ibcmd_cli_safe_requires_capability(client, user, auth_db, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "description": "Init server config",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
                "params_by_name": {
                    "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
                },
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._allow_operate(user, auth_db)
    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "server.config.init",
            "database_ids": [],
            "auth_database_id": auth_db.id,
            "connection": {"remote": "http://host:1545"},
        },
        format="json",
    )
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_dangerous_requires_confirm(staff_client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.drop": {
                "label": "drop config",
                "description": "dangerous",
                "argv": ["server", "config", "drop"],
                "scope": "global",
                "risk_level": "dangerous",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    resp = staff_client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {"command_id": "server.config.drop", "auth_database_id": str(uuid.uuid4())},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "DANGEROUS_CONFIRM_REQUIRED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_dangerous_hidden_for_non_staff(client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.drop": {
                "label": "drop config",
                "description": "dangerous",
                "argv": ["server", "config", "drop"],
                "scope": "global",
                "risk_level": "dangerous",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {"command_id": "server.config.drop", "auth_database_id": str(uuid.uuid4()), "confirm_dangerous": True},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNKNOWN_COMMAND"
