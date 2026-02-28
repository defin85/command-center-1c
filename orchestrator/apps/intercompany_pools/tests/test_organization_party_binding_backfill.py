from __future__ import annotations

import io
import json
from uuid import uuid4

import pytest
from django.core.management import call_command

from apps.intercompany_pools.models import Organization, PoolMasterParty
from apps.intercompany_pools.organization_party_binding_backfill import (
    REMEDIATION_REASON_AMBIGUOUS_MATCH,
    REMEDIATION_REASON_CANDIDATE_ALREADY_BOUND,
    REMEDIATION_REASON_NO_MATCH,
    run_organization_party_binding_backfill,
)
from apps.tenancy.models import Tenant


def _create_tenant(*, slug_prefix: str) -> Tenant:
    return Tenant.objects.create(
        slug=f"{slug_prefix}-{uuid4().hex[:8]}",
        name=f"{slug_prefix} tenant",
    )


@pytest.mark.django_db
def test_backfill_binds_only_unique_candidate_with_kpp_filter() -> None:
    tenant = _create_tenant(slug_prefix="org-party-kpp")
    organization = Organization.objects.create(
        tenant=tenant,
        name="Org A",
        inn="770100000001",
        kpp="770101001",
    )
    matching_party = PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-org-a",
        name="Party Org A",
        inn="770100000001",
        kpp="770101001",
        is_our_organization=True,
    )
    PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-org-a-wrong-kpp",
        name="Party Org A Wrong KPP",
        inn="770100000001",
        kpp="770101999",
        is_our_organization=True,
    )

    stats = run_organization_party_binding_backfill()

    organization.refresh_from_db(fields=["master_party_id"])
    assert organization.master_party_id == matching_party.id
    assert stats.organizations_bound == 1
    assert stats.organizations_unresolved_no_match == 0
    assert stats.organizations_unresolved_ambiguous == 0
    assert stats.organizations_unresolved_candidate_already_bound == 0


@pytest.mark.django_db
def test_backfill_collects_remediation_for_no_match_and_ambiguous_candidates() -> None:
    tenant = _create_tenant(slug_prefix="org-party-remediation")
    no_match_org = Organization.objects.create(
        tenant=tenant,
        name="No Match Org",
        inn="770200000001",
    )
    ambiguous_org = Organization.objects.create(
        tenant=tenant,
        name="Ambiguous Org",
        inn="770200000002",
    )
    PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-ambiguous-1",
        name="Ambiguous Party 1",
        inn="770200000002",
        is_our_organization=True,
    )
    PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-ambiguous-2",
        name="Ambiguous Party 2",
        inn="770200000002",
        is_our_organization=True,
    )

    stats = run_organization_party_binding_backfill()
    no_match_org.refresh_from_db(fields=["master_party_id"])
    ambiguous_org.refresh_from_db(fields=["master_party_id"])

    assert no_match_org.master_party_id is None
    assert ambiguous_org.master_party_id is None
    assert stats.organizations_bound == 0
    assert stats.organizations_unresolved_no_match == 1
    assert stats.organizations_unresolved_ambiguous == 1

    reasons_by_org_id = {
        item.organization_id: item.reason
        for item in stats.remediation_list
    }
    assert reasons_by_org_id[str(no_match_org.id)] == REMEDIATION_REASON_NO_MATCH
    assert reasons_by_org_id[str(ambiguous_org.id)] == REMEDIATION_REASON_AMBIGUOUS_MATCH


@pytest.mark.django_db
def test_backfill_does_not_rebind_party_already_linked_to_another_organization() -> None:
    tenant = _create_tenant(slug_prefix="org-party-bound")
    already_bound_party = PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-org-shared",
        name="Party Org Shared",
        inn="770300000001",
        is_our_organization=True,
    )
    Organization.objects.create(
        tenant=tenant,
        name="Bound Org",
        inn="770300000099",
        master_party=already_bound_party,
    )
    unresolved_org = Organization.objects.create(
        tenant=tenant,
        name="Unresolved Org",
        inn="770300000001",
    )

    stats = run_organization_party_binding_backfill()
    unresolved_org.refresh_from_db(fields=["master_party_id"])

    assert unresolved_org.master_party_id is None
    assert stats.organizations_already_bound == 1
    assert stats.organizations_unresolved_candidate_already_bound == 1
    remediation = next(
        item
        for item in stats.remediation_list
        if item.organization_id == str(unresolved_org.id)
    )
    assert remediation.reason == REMEDIATION_REASON_CANDIDATE_ALREADY_BOUND
    assert list(remediation.candidate_party_ids) == [str(already_bound_party.id)]


@pytest.mark.django_db
def test_backfill_management_command_supports_dry_run_and_json_output() -> None:
    tenant = _create_tenant(slug_prefix="org-party-cmd")
    organization = Organization.objects.create(
        tenant=tenant,
        name="Command Org",
        inn="770400000001",
    )
    PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-command",
        name="Party Command",
        inn="770400000001",
        is_our_organization=True,
    )

    out_dry_run = io.StringIO()
    call_command("backfill_organization_master_party_bindings", "--dry-run", "--json", stdout=out_dry_run)
    payload = json.loads(out_dry_run.getvalue())
    assert payload["dry_run"] is True
    assert payload["organizations_bound"] == 1
    organization.refresh_from_db(fields=["master_party_id"])
    assert organization.master_party_id is None

    out_apply = io.StringIO()
    call_command("backfill_organization_master_party_bindings", "--json", stdout=out_apply)
    payload_apply = json.loads(out_apply.getvalue())
    assert payload_apply["dry_run"] is False
    assert payload_apply["organizations_bound"] == 1
    organization.refresh_from_db(fields=["master_party_id"])
    assert organization.master_party_id is not None
