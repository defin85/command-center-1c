from __future__ import annotations

import pytest

from apps.templates.models import OperationDefinition, OperationExposure
from apps.templates.template_runtime import TemplateResolveError, resolve_runtime_template


def _create_template_exposure(
    *,
    template_id: str,
    operation_type: str = "query",
    target_entity: str = "db",
    template_data: object = None,
    contract_version: int = 1,
    is_active: bool = True,
    status_value: str = OperationExposure.STATUS_PUBLISHED,
) -> OperationExposure:
    if template_data is None:
        template_data = {}
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_DESIGNER_CLI,
        executor_payload={
            "operation_type": operation_type,
            "target_entity": target_entity,
            "template_data": template_data,
        },
        contract_version=contract_version,
        fingerprint=f"fp-{template_id}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    return OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant=None,
        label=f"Template {template_id}",
        description="",
        is_active=is_active,
        capability="",
        contexts=[],
        display_order=0,
        capability_config={},
        status=status_value,
    )


@pytest.mark.django_db
def test_resolve_runtime_template_fail_closed_not_found():
    with pytest.raises(TemplateResolveError) as exc:
        resolve_runtime_template(template_alias="missing-template")

    assert exc.value.code == "TEMPLATE_NOT_FOUND"
    assert "not found" in exc.value.message


@pytest.mark.django_db
def test_resolve_runtime_template_fail_closed_not_published_by_status():
    _create_template_exposure(
        template_id="tpl-draft",
        status_value=OperationExposure.STATUS_DRAFT,
    )

    with pytest.raises(TemplateResolveError) as exc:
        resolve_runtime_template(template_alias="tpl-draft")

    assert exc.value.code == "TEMPLATE_NOT_PUBLISHED"


@pytest.mark.django_db
def test_resolve_runtime_template_fail_closed_not_published_by_is_active():
    _create_template_exposure(
        template_id="tpl-inactive",
        is_active=False,
        status_value=OperationExposure.STATUS_PUBLISHED,
    )

    with pytest.raises(TemplateResolveError) as exc:
        resolve_runtime_template(template_alias="tpl-inactive")

    assert exc.value.code == "TEMPLATE_NOT_PUBLISHED"


@pytest.mark.django_db
def test_resolve_runtime_template_fail_closed_invalid_payload():
    _create_template_exposure(
        template_id="tpl-invalid",
        template_data="invalid-string",
    )

    with pytest.raises(TemplateResolveError) as exc:
        resolve_runtime_template(template_alias="tpl-invalid")

    assert exc.value.code == "TEMPLATE_INVALID"


@pytest.mark.django_db
def test_resolve_runtime_template_success():
    exposure = _create_template_exposure(
        template_id="tpl-ok",
        operation_type="designer_cli",
        target_entity="Infobase",
        template_data={"command": "list"},
    )

    runtime = resolve_runtime_template(template_alias="tpl-ok")

    assert runtime.id == "tpl-ok"
    assert runtime.operation_type == "designer_cli"
    assert runtime.target_entity == "Infobase"
    assert runtime.template_data == {"command": "list"}
    assert runtime.exposure_id == str(exposure.id)
    assert runtime.exposure_status == OperationExposure.STATUS_PUBLISHED
    assert runtime.exposure_revision == 1


@pytest.mark.django_db
def test_resolve_runtime_template_success_by_exposure_id():
    exposure = _create_template_exposure(
        template_id="tpl-by-id",
        operation_type="designer_cli",
        target_entity="Infobase",
        template_data={"command": "info"},
        contract_version=3,
    )

    runtime = resolve_runtime_template(template_exposure_id=str(exposure.id))

    assert runtime.id == "tpl-by-id"
    assert runtime.exposure_id == str(exposure.id)
    assert runtime.exposure_revision == 3


@pytest.mark.django_db
def test_resolve_runtime_template_fail_closed_drift_revision_mismatch():
    exposure = _create_template_exposure(
        template_id="tpl-drift",
        contract_version=5,
    )

    with pytest.raises(TemplateResolveError) as exc:
        resolve_runtime_template(
            template_exposure_id=str(exposure.id),
            expected_exposure_revision=4,
        )

    assert exc.value.code == "TEMPLATE_DRIFT"


@pytest.mark.django_db
def test_resolve_runtime_template_fail_closed_alias_exposure_mismatch():
    exposure = _create_template_exposure(
        template_id="tpl-match",
        contract_version=2,
    )

    with pytest.raises(TemplateResolveError) as exc:
        resolve_runtime_template(
            template_alias="tpl-other",
            template_exposure_id=str(exposure.id),
        )

    assert exc.value.code == "TEMPLATE_DRIFT"
