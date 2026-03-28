from __future__ import annotations

import json
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.intercompany_pools.models import OrganizationPool
from apps.tenancy.models import Tenant


@pytest.mark.django_db
def test_preflight_pool_factual_sync_command_emits_json_report(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = Tenant.objects.create(slug=f"factual-preflight-cmd-{uuid4().hex[:8]}", name="Factual Cmd")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Factual Preflight Command Pool",
    )

    monkeypatch.setattr(
        "apps.intercompany_pools.management.commands.preflight_pool_factual_sync.run_pool_factual_sync_preflight",
        lambda **_: {
            "decision": "go",
            "summary": {"database_count": 1, "failed_databases": 0},
            "databases": [],
        },
    )

    out = StringIO()
    call_command(
        "preflight_pool_factual_sync",
        "--pool-id",
        str(pool.id),
        "--quarter-start",
        "2026-01-01",
        "--requested-by-username",
        "pilot-user",
        "--json",
        stdout=out,
    )

    payload = json.loads(out.getvalue())
    assert payload["decision"] == "go"
    assert payload["summary"]["database_count"] == 1


@pytest.mark.django_db
def test_preflight_pool_factual_sync_command_strict_fails_on_no_go(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = Tenant.objects.create(slug=f"factual-preflight-cmd-ng-{uuid4().hex[:8]}", name="Factual Cmd NG")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Factual Preflight Command Pool NG",
    )

    monkeypatch.setattr(
        "apps.intercompany_pools.management.commands.preflight_pool_factual_sync.run_pool_factual_sync_preflight",
        lambda **_: {
            "decision": "no_go",
            "summary": {"database_count": 1, "failed_databases": 1},
            "databases": [
                {
                    "database_id": "db-1",
                    "decision": "no_go",
                }
            ],
        },
    )

    with pytest.raises(CommandError, match="decision=no_go"):
        call_command(
            "preflight_pool_factual_sync",
            "--pool-id",
            str(pool.id),
            "--quarter-start",
            "2026-01-01",
            "--requested-by-username",
            "pilot-user",
            "--strict",
        )
