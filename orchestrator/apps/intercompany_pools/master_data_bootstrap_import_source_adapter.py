from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

from apps.databases.models import Database, InfobaseUserMapping
from apps.databases.odata import ODataClient

from .master_data_sync_redaction import sanitize_master_data_sync_text, sanitize_master_data_sync_value
from .models import PoolMasterDataBootstrapImportEntityType


BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED = "BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED"
BOOTSTRAP_SOURCE_MAPPING_AMBIGUOUS = "BOOTSTRAP_SOURCE_MAPPING_AMBIGUOUS"
BOOTSTRAP_SOURCE_UNAVAILABLE = "BOOTSTRAP_SOURCE_UNAVAILABLE"
BOOTSTRAP_SOURCE_ODATA_URL_MISSING = "BOOTSTRAP_SOURCE_ODATA_URL_MISSING"
BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING = "BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING"
BOOTSTRAP_SOURCE_ENTITY_TYPE_INVALID = "BOOTSTRAP_SOURCE_ENTITY_TYPE_INVALID"

BOOTSTRAP_SOURCE_KIND_IB_ODATA = "ib_odata"


@dataclass(frozen=True)
class PoolMasterDataBootstrapSourcePreflightResult:
    ok: bool
    source_kind: str
    coverage: dict[str, bool]
    credential_strategy: str
    errors: list[dict[str, Any]]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class _ResolvedMappingCredentials:
    username: str
    password: str
    strategy: str


_BootstrapPreflightCallback = Callable[..., PoolMasterDataBootstrapSourcePreflightResult]
_BootstrapFetchRowsCallback = Callable[..., list[dict[str, Any]]]

_PREFLIGHT_CALLBACK: _BootstrapPreflightCallback | None = None
_FETCH_ROWS_CALLBACK: _BootstrapFetchRowsCallback | None = None
_PREFLIGHT_CALLBACK_KWARGS: dict[str, Any] = {}
_FETCH_ROWS_CALLBACK_KWARGS: dict[str, Any] = {}


def configure_pool_master_data_bootstrap_source_callbacks(
    *,
    preflight: _BootstrapPreflightCallback,
    fetch_rows: _BootstrapFetchRowsCallback,
    preflight_kwargs: Mapping[str, Any] | None = None,
    fetch_rows_kwargs: Mapping[str, Any] | None = None,
) -> None:
    global _PREFLIGHT_CALLBACK
    global _FETCH_ROWS_CALLBACK
    _PREFLIGHT_CALLBACK = preflight
    _FETCH_ROWS_CALLBACK = fetch_rows
    _PREFLIGHT_CALLBACK_KWARGS.clear()
    _PREFLIGHT_CALLBACK_KWARGS.update(dict(preflight_kwargs or {}))
    _FETCH_ROWS_CALLBACK_KWARGS.clear()
    _FETCH_ROWS_CALLBACK_KWARGS.update(dict(fetch_rows_kwargs or {}))


def reset_pool_master_data_bootstrap_source_callbacks() -> None:
    global _PREFLIGHT_CALLBACK
    global _FETCH_ROWS_CALLBACK
    _PREFLIGHT_CALLBACK = None
    _FETCH_ROWS_CALLBACK = None
    _PREFLIGHT_CALLBACK_KWARGS.clear()
    _FETCH_ROWS_CALLBACK_KWARGS.clear()


def run_pool_master_data_bootstrap_source_preflight(
    *,
    tenant_id: str,
    database: Database,
    entity_scope: list[str],
    actor_id: str = "",
) -> PoolMasterDataBootstrapSourcePreflightResult:
    normalized_scope = _normalize_entity_scope(entity_scope)
    callback = _PREFLIGHT_CALLBACK
    if callback is not None:
        return callback(
            tenant_id=str(tenant_id or "").strip(),
            database=database,
            entity_scope=normalized_scope,
            actor_id=str(actor_id or "").strip(),
            **dict(_PREFLIGHT_CALLBACK_KWARGS),
        )
    return _default_preflight(
        tenant_id=str(tenant_id or "").strip(),
        database=database,
        entity_scope=normalized_scope,
        actor_id=str(actor_id or "").strip(),
    )


def fetch_pool_master_data_bootstrap_source_rows(
    *,
    tenant_id: str,
    database: Database,
    entity_type: str,
    actor_id: str = "",
) -> list[dict[str, Any]]:
    normalized_entity_type = _normalize_entity_type(entity_type)
    callback = _FETCH_ROWS_CALLBACK
    if callback is not None:
        rows = callback(
            tenant_id=str(tenant_id or "").strip(),
            database=database,
            entity_type=normalized_entity_type,
            actor_id=str(actor_id or "").strip(),
            **dict(_FETCH_ROWS_CALLBACK_KWARGS),
        )
        return _normalize_rows(rows)
    return _default_fetch_rows(
        tenant_id=str(tenant_id or "").strip(),
        database=database,
        entity_type=normalized_entity_type,
    )


def _default_preflight(
    *,
    tenant_id: str,
    database: Database,
    entity_scope: list[str],
    actor_id: str,
) -> PoolMasterDataBootstrapSourcePreflightResult:
    errors: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "database_id": str(database.id),
        "odata_url": sanitize_master_data_sync_text(str(database.odata_url or "")),
    }
    credential_strategy = "none"

    if not str(database.odata_url or "").strip():
        errors.append(
            _error(
                code=BOOTSTRAP_SOURCE_ODATA_URL_MISSING,
                detail="Database OData URL is missing.",
                path="database.odata_url",
            )
        )

    credentials = _resolve_mapping_credentials(database=database, actor_id=actor_id)
    if credentials is None:
        errors.append(
            _error(
                code=BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED,
                detail="Infobase mapping is not configured for bootstrap source.",
                path="infobase_user_mapping",
            )
        )
    elif credentials.strategy == "ambiguous":
        errors.append(
            _error(
                code=BOOTSTRAP_SOURCE_MAPPING_AMBIGUOUS,
                detail="Multiple infobase mappings found for bootstrap source.",
                path="infobase_user_mapping",
            )
        )
    else:
        credential_strategy = credentials.strategy
        if not credentials.username or not credentials.password:
            errors.append(
                _error(
                    code=BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED,
                    detail="Infobase mapping requires non-empty username and password.",
                    path="infobase_user_mapping.credentials",
                )
            )

    coverage = _resolve_source_coverage(database=database, entity_scope=entity_scope)
    for entity_type, is_covered in coverage.items():
        if not is_covered:
            errors.append(
                _error(
                    code=BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING,
                    detail=f"Selected entity '{entity_type}' is not covered by source mapping.",
                    path=f"entity_scope.{entity_type}",
                )
            )

    if not errors and credentials is not None:
        try:
            client = ODataClient(
                base_url=str(database.odata_url or ""),
                username=credentials.username,
                password=credentials.password,
            )
            healthy = bool(client.health_check())
            client.close()
            if not healthy:
                errors.append(
                    _error(
                        code=BOOTSTRAP_SOURCE_UNAVAILABLE,
                        detail="Bootstrap source OData endpoint is unavailable.",
                        path="source.health_check",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                _error(
                    code=BOOTSTRAP_SOURCE_UNAVAILABLE,
                    detail=str(exc) or "Bootstrap source OData endpoint is unavailable.",
                    path="source.health_check",
                )
            )

    diagnostics["coverage"] = dict(coverage)
    diagnostics["error_count"] = len(errors)
    return PoolMasterDataBootstrapSourcePreflightResult(
        ok=not errors,
        source_kind=BOOTSTRAP_SOURCE_KIND_IB_ODATA,
        coverage=coverage,
        credential_strategy=credential_strategy,
        errors=errors,
        diagnostics=sanitize_master_data_sync_value(diagnostics),
    )


def _default_fetch_rows(
    *,
    tenant_id: str,
    database: Database,
    entity_type: str,
) -> list[dict[str, Any]]:
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    rows_by_entity = metadata.get("bootstrap_import_rows")
    if not isinstance(rows_by_entity, Mapping):
        return []
    raw_rows = rows_by_entity.get(entity_type)
    if not isinstance(raw_rows, list):
        return []
    return _normalize_rows(raw_rows)


def _normalize_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            normalized.append(sanitize_master_data_sync_value(dict(row)))
    return normalized


def _resolve_mapping_credentials(
    *,
    database: Database,
    actor_id: str,
) -> _ResolvedMappingCredentials | None:
    service_rows = list(
        InfobaseUserMapping.objects.filter(
            database_id=database.id,
            is_service=True,
            user__isnull=True,
        )
        .only("ib_username", "ib_password")
        .order_by("id")[:2]
    )
    if len(service_rows) > 1:
        return _ResolvedMappingCredentials(
            username="",
            password="",
            strategy="ambiguous",
        )
    if len(service_rows) == 1:
        row = service_rows[0]
        return _ResolvedMappingCredentials(
            username=str(row.ib_username or "").strip(),
            password=str(row.ib_password or "").strip(),
            strategy="service",
        )

    if actor_id:
        actor_row = (
            InfobaseUserMapping.objects.filter(
                database_id=database.id,
                user_id=actor_id,
            )
            .only("ib_username", "ib_password")
            .order_by("id")
            .first()
        )
        if actor_row is not None:
            return _ResolvedMappingCredentials(
                username=str(actor_row.ib_username or "").strip(),
                password=str(actor_row.ib_password or "").strip(),
                strategy="actor",
            )

    return None


def _resolve_source_coverage(*, database: Database, entity_scope: list[str]) -> dict[str, bool]:
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    source = metadata.get("bootstrap_import_coverage")
    if isinstance(source, Mapping):
        return {entity: bool(source.get(entity, False)) for entity in entity_scope}
    if isinstance(source, list):
        coverage_set = {str(value or "").strip().lower() for value in source}
        return {entity: entity in coverage_set for entity in entity_scope}
    return {entity: True for entity in entity_scope}


def _normalize_entity_scope(entity_scope: list[str]) -> list[str]:
    return [_normalize_entity_type(value) for value in entity_scope]


def _normalize_entity_type(entity_type: str) -> str:
    normalized = str(entity_type or "").strip().lower()
    if normalized not in set(PoolMasterDataBootstrapImportEntityType.values):
        raise ValueError(
            f"{BOOTSTRAP_SOURCE_ENTITY_TYPE_INVALID}: unsupported bootstrap entity_type '{entity_type}'"
        )
    return normalized


def _error(*, code: str, detail: str, path: str) -> dict[str, Any]:
    return {
        "code": str(code or "").strip().upper(),
        "detail": sanitize_master_data_sync_text(detail),
        "path": str(path or "").strip(),
    }


__all__ = [
    "BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING",
    "BOOTSTRAP_SOURCE_ENTITY_TYPE_INVALID",
    "BOOTSTRAP_SOURCE_KIND_IB_ODATA",
    "BOOTSTRAP_SOURCE_MAPPING_AMBIGUOUS",
    "BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED",
    "BOOTSTRAP_SOURCE_ODATA_URL_MISSING",
    "BOOTSTRAP_SOURCE_UNAVAILABLE",
    "PoolMasterDataBootstrapSourcePreflightResult",
    "configure_pool_master_data_bootstrap_source_callbacks",
    "fetch_pool_master_data_bootstrap_source_rows",
    "reset_pool_master_data_bootstrap_source_callbacks",
    "run_pool_master_data_bootstrap_source_preflight",
]
