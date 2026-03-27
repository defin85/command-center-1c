from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .factual_source_profile import (
    REQUIRED_FACTUAL_ACCOUNTING_FUNCTIONS,
    REQUIRED_FACTUAL_ACCOUNTING_REGISTER,
    REQUIRED_FACTUAL_DOCUMENTS,
    REQUIRED_FACTUAL_INFORMATION_REGISTER,
    validate_factual_sync_source_profile,
)


ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID = "POOL_FACTUAL_READ_BOUNDARY_INVALID"

BOUNDARY_KIND_ODATA = "odata"
BOUNDARY_KIND_HTTP_SERVICE = "http_service"


@dataclass(frozen=True)
class FactualPublishedReadBoundary:
    boundary_kind: str
    direct_db_access: bool
    entity_allowlist: tuple[str, ...]
    function_allowlist: tuple[str, ...]
    service_name: str = ""
    endpoint_path: str = ""
    operation_name: str = ""

    def as_contract(self) -> dict[str, str]:
        payload = {
            "read_boundary_kind": self.boundary_kind,
            "direct_db_access": "1" if self.direct_db_access else "0",
            "read_boundary_entity_allowlist": ",".join(self.entity_allowlist),
            "read_boundary_function_allowlist": ",".join(self.function_allowlist),
            "read_boundary_service_name": self.service_name,
            "read_boundary_endpoint_path": self.endpoint_path,
            "read_boundary_operation_name": self.operation_name,
        }
        return payload


def build_default_factual_odata_read_boundary() -> FactualPublishedReadBoundary:
    entity_allowlist = tuple(
        sorted(
            (
                REQUIRED_FACTUAL_ACCOUNTING_REGISTER,
                REQUIRED_FACTUAL_INFORMATION_REGISTER,
                *REQUIRED_FACTUAL_DOCUMENTS,
            )
        )
    )
    function_allowlist = tuple(sorted(REQUIRED_FACTUAL_ACCOUNTING_FUNCTIONS))
    validate_factual_read_boundary(
        boundary_kind=BOUNDARY_KIND_ODATA,
        direct_db_access=False,
        entity_allowlist=entity_allowlist,
        function_allowlist=function_allowlist,
    )
    return FactualPublishedReadBoundary(
        boundary_kind=BOUNDARY_KIND_ODATA,
        direct_db_access=False,
        entity_allowlist=entity_allowlist,
        function_allowlist=function_allowlist,
    )


def build_factual_odata_read_boundary(*, payload: Mapping[str, Any]) -> FactualPublishedReadBoundary:
    errors = validate_factual_sync_source_profile(payload=payload)
    if errors:
        first_error = errors[0]
        raise ValueError(
            f"{ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID}: "
            f"{first_error.get('path') or 'published_metadata'} - {first_error.get('detail') or 'invalid factual source profile'}"
        )
    return build_default_factual_odata_read_boundary()


def build_factual_http_service_read_boundary(
    *,
    service_name: str,
    endpoint_path: str,
    operation_name: str,
) -> FactualPublishedReadBoundary:
    boundary = FactualPublishedReadBoundary(
        boundary_kind=BOUNDARY_KIND_HTTP_SERVICE,
        direct_db_access=False,
        entity_allowlist=(),
        function_allowlist=(),
        service_name=str(service_name or "").strip(),
        endpoint_path=str(endpoint_path or "").strip(),
        operation_name=str(operation_name or "").strip(),
    )
    validate_factual_read_boundary(
        boundary_kind=boundary.boundary_kind,
        direct_db_access=boundary.direct_db_access,
        entity_allowlist=boundary.entity_allowlist,
        function_allowlist=boundary.function_allowlist,
        service_name=boundary.service_name,
        endpoint_path=boundary.endpoint_path,
        operation_name=boundary.operation_name,
    )
    return boundary


def validate_factual_read_boundary(
    *,
    boundary_kind: str,
    direct_db_access: bool,
    entity_allowlist: tuple[str, ...],
    function_allowlist: tuple[str, ...],
    service_name: str = "",
    endpoint_path: str = "",
    operation_name: str = "",
) -> None:
    normalized_kind = str(boundary_kind or "").strip().lower()
    if direct_db_access:
        raise ValueError(
            f"{ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID}: direct DB access is not allowed as primary factual read path"
        )
    if normalized_kind == BOUNDARY_KIND_ODATA:
        if not entity_allowlist:
            raise ValueError(
                f"{ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID}: entity_allowlist must not be empty for OData boundary"
            )
        if not function_allowlist:
            raise ValueError(
                f"{ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID}: function_allowlist must not be empty for OData boundary"
            )
        return
    if normalized_kind == BOUNDARY_KIND_HTTP_SERVICE:
        if not str(service_name or "").strip():
            raise ValueError(
                f"{ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID}: service_name is required for HTTP service boundary"
            )
        if not str(endpoint_path or "").strip():
            raise ValueError(
                f"{ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID}: endpoint_path is required for HTTP service boundary"
            )
        if not str(operation_name or "").strip():
            raise ValueError(
                f"{ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID}: operation_name is required for HTTP service boundary"
            )
        return
    raise ValueError(
        f"{ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID}: unsupported boundary_kind '{normalized_kind}'"
    )


__all__ = [
    "BOUNDARY_KIND_HTTP_SERVICE",
    "BOUNDARY_KIND_ODATA",
    "ERROR_CODE_POOL_FACTUAL_READ_BOUNDARY_INVALID",
    "FactualPublishedReadBoundary",
    "build_default_factual_odata_read_boundary",
    "build_factual_http_service_read_boundary",
    "build_factual_odata_read_boundary",
    "validate_factual_read_boundary",
]
