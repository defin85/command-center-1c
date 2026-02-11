from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    template_alias: str,
    require_active: bool = True,
    require_published: bool = True,
) -> RuntimeTemplate:
    alias = str(template_alias or "").strip()
    if not alias:
        raise TemplateResolveError(code="TEMPLATE_NOT_FOUND", message="template alias is empty")

    exposure = (
        OperationExposure.objects.select_related("definition")
        .filter(
            surface=OperationExposure.SURFACE_TEMPLATE,
            tenant__isnull=True,
            alias=alias,
        )
        .first()
    )
    if exposure is None:
        raise TemplateResolveError(code="TEMPLATE_NOT_FOUND", message=f"template alias '{alias}' not found")

    if require_active and not bool(exposure.is_active):
        raise TemplateResolveError(code="TEMPLATE_NOT_PUBLISHED", message=f"template alias '{alias}' is inactive")

    if require_published and exposure.status != OperationExposure.STATUS_PUBLISHED:
        raise TemplateResolveError(code="TEMPLATE_NOT_PUBLISHED", message=f"template alias '{alias}' is not published")

    operation_type, target_entity, template_data = _template_payload_from_exposure(exposure)
    return RuntimeTemplate(
        id=str(exposure.alias),
        name=str(exposure.label or exposure.alias),
        description=str(exposure.description or ""),
        operation_type=operation_type,
        target_entity=target_entity,
        template_data=template_data,
        is_active=bool(exposure.is_active),
        exposure_id=str(exposure.id),
        exposure_status=str(exposure.status or ""),
    )

