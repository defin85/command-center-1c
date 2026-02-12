from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from apps.templates.models import OperationExposure


class TemplateResolveError(Exception):
    """Raised when template alias cannot be resolved into runtime payload."""

    def __init__(self, *, code: str, message: str):
        super().__init__(message)
        self.code = str(code or "").strip() or "TEMPLATE_INVALID"
        self.message = str(message or "").strip() or "template resolve failed"


@dataclass(frozen=True)
class RuntimeTemplate:
    """Exposure-backed runtime template representation."""

    id: str
    name: str
    description: str
    operation_type: str
    target_entity: str
    template_data: dict[str, Any]
    is_active: bool
    exposure_id: str
    exposure_status: str
    exposure_revision: int


def _coerce_exposure_uuid(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        raise TemplateResolveError(code="TEMPLATE_NOT_FOUND", message="template_exposure_id is empty")
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as exc:
        raise TemplateResolveError(
            code="TEMPLATE_INVALID",
            message=f"template_exposure_id '{value}' is invalid",
        ) from exc


def _resolve_exposure_revision(exposure: OperationExposure) -> int:
    # TODO(update-workflow-operation-exposure-first-class): switch to model exposure_revision
    # once field is introduced in schema/migrations.
    definition_version = getattr(exposure.definition, "contract_version", None)
    try:
        parsed = int(definition_version)
    except (TypeError, ValueError):
        parsed = 1
    return parsed if parsed > 0 else 1


def _resolve_exposure(
    *,
    template_alias: str | None,
    template_exposure_id: str | None,
) -> OperationExposure:
    alias = str(template_alias or "").strip()
    exposure_id_raw = str(template_exposure_id or "").strip()

    if not alias and not exposure_id_raw:
        raise TemplateResolveError(
            code="TEMPLATE_NOT_FOUND",
            message="template_alias or template_exposure_id is required",
        )

    qs = OperationExposure.objects.select_related("definition").filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        tenant__isnull=True,
    )

    if exposure_id_raw:
        exposure_id = _coerce_exposure_uuid(exposure_id_raw)
        exposure = qs.filter(id=exposure_id).first()
        if exposure is None:
            raise TemplateResolveError(
                code="TEMPLATE_NOT_FOUND",
                message=f"template exposure '{exposure_id_raw}' not found",
            )
        if alias and exposure.alias != alias:
            raise TemplateResolveError(
                code="TEMPLATE_DRIFT",
                message=(
                    f"template alias '{alias}' does not match exposure "
                    f"'{exposure_id_raw}' (actual alias: '{exposure.alias}')"
                ),
            )
        return exposure

    exposure = qs.filter(alias=alias).first()
    if exposure is None:
        raise TemplateResolveError(code="TEMPLATE_NOT_FOUND", message=f"template alias '{alias}' not found")
    return exposure


def _template_payload_from_exposure(exposure: OperationExposure) -> tuple[str, str, dict[str, Any]]:
    payload = exposure.definition.executor_payload if isinstance(exposure.definition.executor_payload, dict) else {}
    operation_type = str(payload.get("operation_type") or exposure.definition.executor_kind or "").strip()
    target_entity = str(payload.get("target_entity") or "").strip()
    template_data = payload.get("template_data")

    if not operation_type:
        raise TemplateResolveError(code="TEMPLATE_INVALID", message=f"template alias '{exposure.alias}' has empty operation_type")
    if not isinstance(template_data, dict):
        raise TemplateResolveError(code="TEMPLATE_INVALID", message=f"template alias '{exposure.alias}' has invalid template_data")

    return operation_type, target_entity, template_data


def resolve_runtime_template(
    *,
    template_alias: str | None = None,
    template_exposure_id: str | None = None,
    expected_exposure_revision: int | None = None,
    require_active: bool = True,
    require_published: bool = True,
) -> RuntimeTemplate:
    exposure = _resolve_exposure(
        template_alias=template_alias,
        template_exposure_id=template_exposure_id,
    )
    exposure_alias = str(exposure.alias or "")
    exposure_revision = _resolve_exposure_revision(exposure)

    if expected_exposure_revision is not None:
        try:
            expected_revision = int(expected_exposure_revision)
        except (TypeError, ValueError) as exc:
            raise TemplateResolveError(
                code="TEMPLATE_INVALID",
                message=f"expected_exposure_revision '{expected_exposure_revision}' is invalid",
            ) from exc
        if expected_revision < 1:
            raise TemplateResolveError(
                code="TEMPLATE_INVALID",
                message="expected_exposure_revision must be >= 1",
            )
        if exposure_revision != expected_revision:
            raise TemplateResolveError(
                code="TEMPLATE_DRIFT",
                message=(
                    f"template exposure '{exposure.id}' revision mismatch: "
                    f"expected {expected_revision}, actual {exposure_revision}"
                ),
            )

    if require_active and not bool(exposure.is_active):
        raise TemplateResolveError(
            code="TEMPLATE_NOT_PUBLISHED",
            message=f"template alias '{exposure_alias}' is inactive",
        )

    if require_published and exposure.status != OperationExposure.STATUS_PUBLISHED:
        raise TemplateResolveError(
            code="TEMPLATE_NOT_PUBLISHED",
            message=f"template alias '{exposure_alias}' is not published",
        )

    operation_type, target_entity, template_data = _template_payload_from_exposure(exposure)
    return RuntimeTemplate(
        id=exposure_alias,
        name=str(exposure.label or exposure_alias),
        description=str(exposure.description or ""),
        operation_type=operation_type,
        target_entity=target_entity,
        template_data=template_data,
        is_active=bool(exposure.is_active),
        exposure_id=str(exposure.id),
        exposure_status=str(exposure.status or ""),
        exposure_revision=exposure_revision,
    )
