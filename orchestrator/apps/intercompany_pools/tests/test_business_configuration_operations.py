from __future__ import annotations

from uuid import uuid4

import pytest

from apps.api_v2.tests import _execute_ibcmd_cli_support as support
from apps.databases.models import Database
from apps.intercompany_pools.business_configuration_operations import (
    ensure_business_configuration_profile_runtime,
)
from apps.operations.models import BatchOperation
from apps.operations.services.operations_service import OperationsService
from apps.operations.services.operations_service.types import EnqueueResult
from apps.tenancy.models import Tenant


def _seed_ibcmd_business_configuration_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "driver_schema": {},
        "commands_by_id": {
            "infobase.config.generation-id": {
                "label": "config generation-id",
                "description": "Get config generation id",
                "argv": ["infobase", "config", "generation-id"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
            "infobase.config.export.objects": {
                "label": "config export objects",
                "description": "Export selected config objects",
                "argv": ["infobase", "config", "export", "objects"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {
                    "arg1": {
                        "kind": "positional",
                        "position": 1,
                        "required": False,
                        "expects_value": True,
                        "label": "Object1 ... ObjectN",
                    },
                    "archive": {
                        "kind": "flag",
                        "flag": "--archive",
                        "required": False,
                        "expects_value": False,
                        "label": "--archive",
                    },
                    "out": {
                        "kind": "flag",
                        "flag": "--out",
                        "required": False,
                        "expects_value": True,
                        "label": "--out",
                    },
                },
            },
        },
    }
    support._seed_ibcmd_catalog(
        monkeypatch,
        base_catalog=base_catalog,
        overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}},
    )


def _create_database(*, with_profile: bool) -> Database:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    database = Database.objects.create(
        tenant=tenant,
        name=f"business-config-db-{uuid4().hex[:8]}",
        host="localhost",
        port=80,
        base_name="ignored-infobase-name",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    if with_profile:
        database.metadata = {
            "business_configuration_profile": {
                "config_name": "Бухгалтерия предприятия, редакция 3.0",
                "config_root_name": "БухгалтерияПредприятия",
                "config_version": "3.0.193.19",
                "config_vendor": 'Фирма "1С"',
                "config_generation_id": "old-generation-id",
                "config_name_source": "synonym_ru",
                "verification_status": "verified",
                "verified_at": "2026-03-12T00:00:00+00:00",
            }
        }
        database.save(update_fields=["metadata", "updated_at"])
    return database


def _fake_enqueue(op_id: str) -> EnqueueResult:
    BatchOperation.objects.filter(id=op_id).update(status=BatchOperation.STATUS_QUEUED)
    return EnqueueResult(success=True, operation_id=op_id, status="queued")


@pytest.mark.django_db
def test_ensure_business_configuration_profile_runtime_enqueues_verification_when_profile_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_ibcmd_business_configuration_catalog(monkeypatch)
    monkeypatch.setattr(OperationsService, "enqueue_operation", _fake_enqueue)
    database = _create_database(with_profile=False)

    profile = ensure_business_configuration_profile_runtime(database=database)

    assert profile is None
    operation = BatchOperation.objects.get()
    assert operation.status == BatchOperation.STATUS_QUEUED
    assert (operation.metadata or {}).get("command_id") == "infobase.config.export.objects"
    assert (operation.metadata or {}).get("business_configuration_job_kind") == "verification"
    assert (operation.metadata or {}).get("snapshot_kinds") == ["business_configuration_profile"]
    argv = ((operation.payload or {}).get("data") or {}).get("argv") or []
    assert argv[:4] == ["infobase", "config", "export", "objects"]
    assert "Configuration" in argv
    assert "--archive" in argv
    assert any(token == "--out" or str(token).startswith("--out=") for token in argv)


@pytest.mark.django_db
def test_ensure_business_configuration_profile_runtime_enqueues_generation_probe_for_existing_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_ibcmd_business_configuration_catalog(monkeypatch)
    monkeypatch.setattr(OperationsService, "enqueue_operation", _fake_enqueue)
    database = _create_database(with_profile=True)

    profile = ensure_business_configuration_profile_runtime(database=database)

    assert profile is not None
    operation = BatchOperation.objects.get()
    assert operation.status == BatchOperation.STATUS_QUEUED
    assert (operation.metadata or {}).get("command_id") == "infobase.config.generation-id"
    assert (operation.metadata or {}).get("business_configuration_job_kind") == "generation_probe"
    database.refresh_from_db()
    persisted_profile = (database.metadata or {}).get("business_configuration_profile") or {}
    assert persisted_profile.get("generation_probe_operation_id") == operation.id
    argv = ((operation.payload or {}).get("data") or {}).get("argv") or []
    assert argv[:3] == ["infobase", "config", "generation-id"]
