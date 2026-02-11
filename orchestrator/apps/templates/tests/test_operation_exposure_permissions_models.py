from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.db import transaction

from apps.templates.models import (
    OperationDefinition,
    OperationExposure,
    OperationExposureGroupPermission,
    OperationExposurePermission,
)


def _create_template_exposure(*, alias: str) -> OperationExposure:
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_DESIGNER_CLI,
        executor_payload={
            "operation_type": "designer_cli",
            "target_entity": "infobase",
            "template_data": {},
        },
        contract_version=1,
        fingerprint=f"fp-{alias}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    return OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=alias,
        tenant=None,
        label=alias,
        description="",
        is_active=True,
        capability="",
        contexts=[],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
    )


@pytest.mark.django_db
def test_operation_exposure_permissions_unique_constraints(django_user_model):
    exposure = _create_template_exposure(alias="tpl-oep-1")
    user = django_user_model.objects.create_user(username="oep_user", password="pass")
    group = Group.objects.create(name="oep_group")

    OperationExposurePermission.objects.create(user=user, exposure=exposure, level=10, notes="")
    OperationExposureGroupPermission.objects.create(group=group, exposure=exposure, level=10, notes="")

    with pytest.raises(IntegrityError), transaction.atomic():
        OperationExposurePermission.objects.create(user=user, exposure=exposure, level=20, notes="")

    with pytest.raises(IntegrityError), transaction.atomic():
        OperationExposureGroupPermission.objects.create(group=group, exposure=exposure, level=20, notes="")


@pytest.mark.django_db
def test_operation_exposure_permissions_string_representation(django_user_model):
    exposure = _create_template_exposure(alias="tpl-oep-2")
    user = django_user_model.objects.create_user(username="oep_user_2", password="pass")
    group = Group.objects.create(name="oep_group_2")

    user_perm = OperationExposurePermission.objects.create(
        user=user,
        exposure=exposure,
        level=10,
        notes="",
    )
    group_perm = OperationExposureGroupPermission.objects.create(
        group=group,
        exposure=exposure,
        level=10,
        notes="",
    )

    assert "tpl-oep-2" in str(user_perm)
    assert "tpl-oep-2" in str(group_perm)
