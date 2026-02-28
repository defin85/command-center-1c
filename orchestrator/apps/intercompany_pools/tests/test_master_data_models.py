from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.intercompany_pools.models import (
    Organization,
    PoolMasterContract,
    PoolMasterParty,
    PoolMasterTaxProfile,
)
from apps.tenancy.models import Tenant


@pytest.mark.django_db
def test_pool_master_party_requires_at_least_one_role() -> None:
    tenant = Tenant.objects.create(slug="mdm-party-roles", name="MDM Party Roles")

    with pytest.raises(ValidationError):
        PoolMasterParty.objects.create(
            tenant=tenant,
            canonical_id="party-001",
            name="No Roles",
            is_our_organization=False,
            is_counterparty=False,
        )


@pytest.mark.django_db
def test_pool_master_contract_owner_must_have_counterparty_role() -> None:
    tenant = Tenant.objects.create(slug="mdm-contract-owner-role", name="MDM Contract Owner Role")
    owner_without_counterparty_role = PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-org-only",
        name="Org Only",
        is_our_organization=True,
        is_counterparty=False,
    )

    with pytest.raises(ValidationError):
        PoolMasterContract.objects.create(
            tenant=tenant,
            canonical_id="contract-001",
            name="Contract",
            owner_counterparty=owner_without_counterparty_role,
        )


@pytest.mark.django_db
def test_pool_master_contract_owner_must_belong_to_same_tenant() -> None:
    tenant_a = Tenant.objects.create(slug="mdm-contract-tenant-a", name="MDM Contract Tenant A")
    tenant_b = Tenant.objects.create(slug="mdm-contract-tenant-b", name="MDM Contract Tenant B")
    owner = PoolMasterParty.objects.create(
        tenant=tenant_a,
        canonical_id="party-tenant-a",
        name="Party A",
        is_counterparty=True,
    )

    with pytest.raises(ValidationError):
        PoolMasterContract.objects.create(
            tenant=tenant_b,
            canonical_id="contract-cross-tenant",
            name="Cross Tenant Contract",
            owner_counterparty=owner,
        )


@pytest.mark.django_db
def test_pool_master_contract_is_owner_scoped_by_counterparty() -> None:
    tenant = Tenant.objects.create(slug="mdm-contract-owner-scope", name="MDM Contract Owner Scope")
    owner_a = PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-counterparty-a",
        name="Counterparty A",
        is_counterparty=True,
    )
    owner_b = PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-counterparty-b",
        name="Counterparty B",
        is_counterparty=True,
    )

    first = PoolMasterContract.objects.create(
        tenant=tenant,
        canonical_id="contract-001",
        name="Contract A",
        owner_counterparty=owner_a,
    )
    assert first.owner_counterparty_id == owner_a.id

    same_canonical_other_owner = PoolMasterContract.objects.create(
        tenant=tenant,
        canonical_id="contract-001",
        name="Contract B",
        owner_counterparty=owner_b,
    )
    assert same_canonical_other_owner.owner_counterparty_id == owner_b.id

    with pytest.raises(ValidationError):
        PoolMasterContract.objects.create(
            tenant=tenant,
            canonical_id="contract-001",
            name="Contract Duplicate Owner",
            owner_counterparty=owner_a,
        )


@pytest.mark.django_db
def test_pool_master_tax_profile_validates_vat_rate_range() -> None:
    tenant = Tenant.objects.create(slug="mdm-tax-profile", name="MDM Tax Profile")

    profile = PoolMasterTaxProfile.objects.create(
        tenant=tenant,
        canonical_id="tax-001",
        vat_rate="20.00",
        vat_included=True,
        vat_code="VAT20",
    )
    assert str(profile.vat_rate) == "20.00"

    with pytest.raises(ValidationError):
        PoolMasterTaxProfile.objects.create(
            tenant=tenant,
            canonical_id="tax-002",
            vat_rate="120.00",
            vat_included=False,
            vat_code="VAT120",
        )


@pytest.mark.django_db
def test_organization_master_party_binding_requires_same_tenant() -> None:
    tenant_a = Tenant.objects.create(slug="mdm-org-binding-a", name="MDM Org Binding A")
    tenant_b = Tenant.objects.create(slug="mdm-org-binding-b", name="MDM Org Binding B")
    foreign_party = PoolMasterParty.objects.create(
        tenant=tenant_b,
        canonical_id="party-foreign-org",
        name="Foreign Org Party",
        is_our_organization=True,
    )
    organization = Organization(
        tenant=tenant_a,
        name="Org A",
        inn="781000000001",
        master_party=foreign_party,
    )

    with pytest.raises(ValidationError):
        organization.full_clean()


@pytest.mark.django_db
def test_organization_master_party_binding_requires_organization_role() -> None:
    tenant = Tenant.objects.create(slug="mdm-org-binding-role", name="MDM Org Binding Role")
    counterparty_only = PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-counterparty-only",
        name="Counterparty Only",
        is_our_organization=False,
        is_counterparty=True,
    )
    organization = Organization(
        tenant=tenant,
        name="Org Role Check",
        inn="781000000002",
        master_party=counterparty_only,
    )

    with pytest.raises(ValidationError):
        organization.full_clean()
