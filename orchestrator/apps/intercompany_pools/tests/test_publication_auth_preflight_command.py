from __future__ import annotations

import json
from datetime import date
from io import StringIO
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.models import Organization, OrganizationPool, PoolNodeVersion
from apps.tenancy.models import Tenant


User = get_user_model()


def _create_pool_with_single_target() -> tuple[Tenant, OrganizationPool, Database]:
    tenant = Tenant.objects.create(
        slug=f"pub-auth-preflight-{uuid4().hex[:8]}",
        name="Publication Auth Preflight",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Publication Auth Pool",
    )
    database = Database.objects.create(
        tenant=tenant,
        name=f"db-{uuid4().hex[:8]}",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
    )
    organization = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Org {uuid4().hex[:6]}",
        inn=f"73{uuid4().hex[:10]}",
        status="active",
    )
    PoolNodeVersion.objects.create(
        pool=pool,
        organization=organization,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    return tenant, pool, database


@pytest.mark.django_db
def test_preflight_pool_publication_auth_mapping_reports_no_go_for_missing_actor_mapping() -> None:
    _, pool, _ = _create_pool_with_single_target()
    actor = User.objects.create_user(
        username=f"pool-preflight-actor-{uuid4().hex[:8]}",
        email=f"pool-preflight-actor-{uuid4().hex[:8]}@example.test",
    )

    out = StringIO()
    call_command(
        "preflight_pool_publication_auth_mapping",
        "--pool-id",
        str(pool.id),
        "--period-date",
        "2026-01-15",
        "--strategy",
        "actor",
        "--actor-username",
        actor.username,
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["decision"] == "no_go"
    assert checks["actor_mapping_missing"]["mismatches"] == 1
    assert checks["actor_mapping_missing"]["status"] == "fail"

    with pytest.raises(CommandError):
        call_command(
            "preflight_pool_publication_auth_mapping",
            "--pool-id",
            str(pool.id),
            "--period-date",
            "2026-01-15",
            "--strategy",
            "actor",
            "--actor-username",
            actor.username,
            "--strict",
        )


@pytest.mark.django_db
def test_preflight_pool_publication_auth_mapping_reports_go_when_actor_and_service_mapping_exist() -> None:
    _, pool, database = _create_pool_with_single_target()
    actor = User.objects.create_user(
        username=f"pool-preflight-go-{uuid4().hex[:8]}",
        email=f"pool-preflight-go-{uuid4().hex[:8]}@example.test",
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=actor,
        ib_username="odata_actor_user",
        ib_password="odata_actor_pwd",
        is_service=False,
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="odata_service_user",
        ib_password="odata_service_pwd",
        is_service=True,
    )

    out = StringIO()
    call_command(
        "preflight_pool_publication_auth_mapping",
        "--pool-id",
        str(pool.id),
        "--period-date",
        "2026-01-15",
        "--strategy",
        "both",
        "--actor-username",
        actor.username,
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["decision"] == "go"
    assert checks["actor_mapping_missing"]["mismatches"] == 0
    assert checks["actor_mapping_ambiguous"]["mismatches"] == 0
    assert checks["service_mapping_missing"]["mismatches"] == 0
    assert checks["service_mapping_ambiguous"]["mismatches"] == 0

