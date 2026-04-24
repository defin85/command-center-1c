from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

from apps.databases.models import Database, InfobaseUserMapping
from apps.databases.odata import ODataClient

from .master_data_registry import normalize_pool_master_data_bootstrap_entity_type
from .master_data_sync_redaction import sanitize_master_data_sync_text, sanitize_master_data_sync_value
from .models import PoolMasterDataBootstrapImportEntityType


BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED = "BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED"
BOOTSTRAP_SOURCE_MAPPING_AMBIGUOUS = "BOOTSTRAP_SOURCE_MAPPING_AMBIGUOUS"
BOOTSTRAP_SOURCE_UNAVAILABLE = "BOOTSTRAP_SOURCE_UNAVAILABLE"
BOOTSTRAP_SOURCE_ODATA_URL_MISSING = "BOOTSTRAP_SOURCE_ODATA_URL_MISSING"
BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING = "BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING"
BOOTSTRAP_SOURCE_ENTITY_TYPE_INVALID = "BOOTSTRAP_SOURCE_ENTITY_TYPE_INVALID"
BOOTSTRAP_SOURCE_MAPPING_INVALID = "BOOTSTRAP_SOURCE_MAPPING_INVALID"
BOOTSTRAP_SOURCE_FETCH_FAILED = "BOOTSTRAP_SOURCE_FETCH_FAILED"
CHART_ROW_SOURCE_NOT_READY = "CHART_ROW_SOURCE_NOT_READY"
CHART_ROW_SOURCE_PROBE_FAILED = "CHART_ROW_SOURCE_PROBE_FAILED"
CHART_ROW_SOURCE_MAPPING_INCOMPLETE = "CHART_ROW_SOURCE_MAPPING_INCOMPLETE"

BOOTSTRAP_SOURCE_KIND_IB_ODATA = "ib_odata"
BOOTSTRAP_SOURCE_MODE_ODATA = "odata"
BOOTSTRAP_SOURCE_MODE_METADATA_ROWS = "metadata_rows"
CHART_ROW_SOURCE_STATUS_READY = "ready"
CHART_ROW_SOURCE_STATUS_NEEDS_PROBE = "needs_probe"
CHART_ROW_SOURCE_STATUS_NEEDS_MAPPING = "needs_mapping"
CHART_ROW_SOURCE_STATUS_UNAVAILABLE = "unavailable"
CHART_ROW_SOURCE_KIND_METADATA_ROWS = "metadata_rows"
STANDARD_CHART_ROW_SOURCE_FIELD_MAPPING = {
    "canonical_id": "Ref_Key",
    "source_ref": "Ref_Key",
    "code": "Code",
    "name": "Description",
}
STANDARD_CHART_ROW_SOURCE_SELECT_FIELDS = ["Ref_Key", "Code", "Description"]
STANDARD_CHART_ROW_SOURCE_ORDER_BY = ["Ref_Key", "Code"]


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


@dataclass(frozen=True)
class _BootstrapSourceEntityConfig:
    entity_type: str
    entity_name: str
    chart_identity: str
    chart_identity_source: str
    field_mapping: dict[str, str]
    select_fields: list[str]
    filter_query: str
    page_size: int
    order_by: list[str]


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


def is_pool_master_data_bootstrap_source_callback_configured() -> bool:
    return _PREFLIGHT_CALLBACK is not None or _FETCH_ROWS_CALLBACK is not None


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
        actor_id=str(actor_id or "").strip(),
    )


def build_standard_chart_odata_row_source(
    *,
    chart_identity: str,
    status: str = CHART_ROW_SOURCE_STATUS_NEEDS_PROBE,
    diagnostics: list[dict[str, Any]] | None = None,
    credential_strategy: str = "",
) -> dict[str, Any]:
    entity_name = str(chart_identity or "").strip()
    return sanitize_master_data_sync_value(
        {
            "row_source_status": str(status or CHART_ROW_SOURCE_STATUS_NEEDS_PROBE).strip(),
            "row_source_kind": BOOTSTRAP_SOURCE_KIND_IB_ODATA,
            "row_source_entity_name": entity_name,
            "row_source_field_mapping": dict(STANDARD_CHART_ROW_SOURCE_FIELD_MAPPING),
            "row_source_select_fields": list(STANDARD_CHART_ROW_SOURCE_SELECT_FIELDS),
            "row_source_order_by": list(STANDARD_CHART_ROW_SOURCE_ORDER_BY),
            "row_source_page_size": 500,
            "row_source_derivation_method": "standard_chartofaccounts_odata_entity",
            "row_source_credential_strategy": str(credential_strategy or "").strip(),
            "row_source_diagnostics": list(diagnostics or []),
        }
    )


def run_pool_master_data_chart_row_source_preflight(
    *,
    tenant_id: str,
    database: Database,
    row_source: Mapping[str, Any],
    actor_id: str = "",
) -> PoolMasterDataBootstrapSourcePreflightResult:
    if _PREFLIGHT_CALLBACK is not None:
        return run_pool_master_data_bootstrap_source_preflight(
            tenant_id=tenant_id,
            database=database,
            entity_scope=[PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT],
            actor_id=actor_id,
        )
    return _default_chart_row_source_preflight(
        tenant_id=str(tenant_id or "").strip(),
        database=database,
        row_source=row_source,
        actor_id=str(actor_id or "").strip(),
    )


def fetch_pool_master_data_chart_row_source_rows(
    *,
    tenant_id: str,
    database: Database,
    row_source: Mapping[str, Any],
    actor_id: str = "",
) -> list[dict[str, Any]]:
    if _FETCH_ROWS_CALLBACK is not None:
        return fetch_pool_master_data_bootstrap_source_rows(
            tenant_id=tenant_id,
            database=database,
            entity_type=PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT,
            actor_id=actor_id,
        )

    source_mode = _resolve_source_mode(database=database)
    if source_mode == BOOTSTRAP_SOURCE_MODE_METADATA_ROWS:
        return _default_fetch_rows(
            tenant_id=tenant_id,
            database=database,
            entity_type=PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT,
            actor_id=actor_id,
        )

    config = _resolve_chart_row_source_entity_config(row_source=row_source)
    mapping_error = _validate_source_mapping_config(config=config)
    if mapping_error is not None:
        raise ValueError(f"{CHART_ROW_SOURCE_MAPPING_INCOMPLETE}: {mapping_error}")

    credentials = _resolve_mapping_credentials(database=database, actor_id=actor_id)
    if credentials is None:
        raise ValueError(
            f"{CHART_ROW_SOURCE_NOT_READY}: Infobase mapping is not configured for chart row source."
        )
    if credentials.strategy == "ambiguous":
        raise ValueError(
            f"{CHART_ROW_SOURCE_NOT_READY}: Multiple infobase mappings found for chart row source."
        )
    if not credentials.username or not credentials.password:
        raise ValueError(
            f"{CHART_ROW_SOURCE_NOT_READY}: Infobase mapping requires non-empty username and password."
        )

    client: ODataClient | None = None
    try:
        client = ODataClient(
            base_url=str(database.odata_url or ""),
            username=credentials.username,
            password=credentials.password,
        )
        return _fetch_all_source_rows_from_odata(client=client, config=config)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"{BOOTSTRAP_SOURCE_FETCH_FAILED}: failed to fetch chart row source '{config.entity_name}': {exc}"
        ) from exc
    finally:
        if client is not None:
            client.close()


def discover_pool_master_data_bootstrap_source_chart_candidates(
    *,
    database: Database,
    config_name: str,
    config_version: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_mode = _resolve_source_mode(database=database)
    diagnostics: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    if source_mode == BOOTSTRAP_SOURCE_MODE_METADATA_ROWS:
        metadata = database.metadata if isinstance(database.metadata, dict) else {}
        rows_by_entity = metadata.get("bootstrap_import_rows")
        raw_rows = rows_by_entity.get("gl_account") if isinstance(rows_by_entity, Mapping) else None
        if not isinstance(raw_rows, list):
            diagnostics.append(
                _error(
                    code="CHART_DISCOVERY_METADATA_ROWS_MISSING",
                    detail="Metadata rows do not contain GLAccount rows.",
                    path="metadata.bootstrap_import_rows.gl_account",
                )
            )
            return candidates, diagnostics

        identities = sorted(
            {
                str(row.get("chart_identity") or "").strip()
                for row in raw_rows
                if isinstance(row, Mapping) and str(row.get("chart_identity") or "").strip()
            }
        )
        if not identities:
            diagnostics.append(
                _error(
                    code="CHART_DISCOVERY_CHART_IDENTITY_MISSING",
                    detail="Metadata GLAccount rows do not contain chart_identity.",
                    path="metadata.bootstrap_import_rows.gl_account[].chart_identity",
                )
            )
            candidates.append(
                _build_bootstrap_chart_candidate(
                    database=database,
                    chart_identity="",
                    config_name=config_name,
                    config_version=config_version,
                    source_kind="metadata_rows",
                    derivation_method="metadata_rows",
                    confidence="blocked",
                    evidence={"mode": source_mode, "row_count": len(raw_rows), "missing": "chart_identity"},
                    diagnostics=diagnostics,
                )
            )
            return candidates, diagnostics

        for identity in identities:
            candidates.append(
                _build_bootstrap_chart_candidate(
                    database=database,
                    chart_identity=identity,
                    config_name=config_name,
                    config_version=config_version,
                    source_kind="metadata_rows",
                    derivation_method="metadata_rows",
                    confidence="medium",
                    evidence={"mode": source_mode, "row_count": len(raw_rows), "chart_identity": identity},
                    diagnostics=[],
                )
            )
        return candidates, diagnostics

    entity_configs = _resolve_odata_source_entity_configs(database=database)
    config = entity_configs.get(PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT)
    if config is None:
        diagnostics.append(
            _error(
                code=BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING,
                detail="Bootstrap source mapping does not cover GLAccount.",
                path="metadata.bootstrap_import_source.entities.gl_account",
            )
        )
        return candidates, diagnostics

    if config.chart_identity:
        candidates.append(
            _build_bootstrap_chart_candidate(
                database=database,
                chart_identity=config.chart_identity,
                config_name=config_name,
                config_version=config_version,
                source_kind="bootstrap_source_config",
                derivation_method=config.chart_identity_source or "bootstrap_source_config",
                confidence="high",
                evidence={
                    "mode": source_mode,
                    "entity_name": config.entity_name,
                    "chart_identity": config.chart_identity,
                    "chart_identity_source": config.chart_identity_source,
                    "field_mapping": config.field_mapping,
                    "select_fields": config.select_fields,
                    "filter_query": config.filter_query,
                    "order_by": config.order_by,
                },
                diagnostics=[],
            )
        )
        return candidates, diagnostics

    mapping_error = _validate_source_mapping_config(config=config)
    diagnostics.append(
        _error(
            code="CHART_DISCOVERY_CHART_IDENTITY_MISSING",
            detail=mapping_error
            or "GLAccount bootstrap source mapping does not provide a stable chart_identity.",
            path="metadata.bootstrap_import_source.entities.gl_account",
        )
    )
    candidates.append(
        _build_bootstrap_chart_candidate(
            database=database,
            chart_identity="",
            config_name=config_name,
            config_version=config_version,
            source_kind="bootstrap_source_config",
            derivation_method="bootstrap_source_config",
            confidence="blocked",
            evidence={
                "mode": source_mode,
                "entity_name": config.entity_name,
                "field_mapping": config.field_mapping,
                "missing": "chart_identity",
            },
            diagnostics=diagnostics,
        )
    )
    return candidates, diagnostics


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

    source_mode = _resolve_source_mode(database=database)
    diagnostics["source_mode"] = source_mode

    if source_mode == BOOTSTRAP_SOURCE_MODE_METADATA_ROWS:
        coverage = _resolve_metadata_source_coverage(database=database, entity_scope=entity_scope)
        for entity_type, is_covered in coverage.items():
            if not is_covered:
                errors.append(
                    _error(
                        code=BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING,
                        detail=f"Selected entity '{entity_type}' is not covered by source mapping.",
                        path=f"entity_scope.{entity_type}",
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

    entity_configs = _resolve_odata_source_entity_configs(database=database)
    coverage = {entity: entity in entity_configs for entity in entity_scope}
    for entity_type, is_covered in coverage.items():
        if not is_covered:
            errors.append(
                _error(
                    code=BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING,
                    detail=f"Selected entity '{entity_type}' is not covered by source mapping.",
                    path=f"entity_scope.{entity_type}",
                )
            )
            continue
        config_error = _validate_source_mapping_config(config=entity_configs[entity_type])
        if config_error is not None:
            errors.append(
                _error(
                    code=BOOTSTRAP_SOURCE_MAPPING_INVALID,
                    detail=config_error,
                    path=f"bootstrap_import_source.entities.{entity_type}.field_mapping",
                )
            )

    if not errors and credentials is not None:
        client: ODataClient | None = None
        try:
            client = ODataClient(
                base_url=str(database.odata_url or ""),
                username=credentials.username,
                password=credentials.password,
            )
            healthy = bool(client.health_check())
            if not healthy:
                errors.append(
                    _error(
                        code=BOOTSTRAP_SOURCE_UNAVAILABLE,
                        detail="Bootstrap source OData endpoint is unavailable.",
                        path="source.health_check",
                    )
                )
            else:
                for entity_type in entity_scope:
                    config = entity_configs.get(entity_type)
                    if config is None:
                        continue
                    _check_source_entity_availability(
                        client=client,
                        config=config,
                    )
        except ValueError as exc:
            errors.append(
                _error(
                    code=BOOTSTRAP_SOURCE_UNAVAILABLE,
                    detail=str(exc),
                    path="source.entity_probe",
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
        finally:
            if client is not None:
                client.close()

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
    actor_id: str,
) -> list[dict[str, Any]]:
    source_mode = _resolve_source_mode(database=database)
    if source_mode == BOOTSTRAP_SOURCE_MODE_METADATA_ROWS:
        metadata = database.metadata if isinstance(database.metadata, dict) else {}
        rows_by_entity = metadata.get("bootstrap_import_rows")
        if not isinstance(rows_by_entity, Mapping):
            return []
        raw_rows = rows_by_entity.get(entity_type)
        if not isinstance(raw_rows, list):
            return []
        return _normalize_rows(raw_rows)

    entity_configs = _resolve_odata_source_entity_configs(database=database)
    config = entity_configs.get(entity_type)
    if config is None:
        raise ValueError(
            f"{BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING}: "
            f"Selected entity '{entity_type}' is not covered by source mapping."
        )
    mapping_error = _validate_source_mapping_config(config=config)
    if mapping_error is not None:
        raise ValueError(f"{BOOTSTRAP_SOURCE_MAPPING_INVALID}: {mapping_error}")

    credentials = _resolve_mapping_credentials(database=database, actor_id=actor_id)
    if credentials is None:
        raise ValueError(
            f"{BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED}: "
            "Infobase mapping is not configured for bootstrap source."
        )
    if credentials.strategy == "ambiguous":
        raise ValueError(
            f"{BOOTSTRAP_SOURCE_MAPPING_AMBIGUOUS}: Multiple infobase mappings found for bootstrap source."
        )
    if not credentials.username or not credentials.password:
        raise ValueError(
            f"{BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED}: "
            "Infobase mapping requires non-empty username and password."
        )

    client: ODataClient | None = None
    try:
        client = ODataClient(
            base_url=str(database.odata_url or ""),
            username=credentials.username,
            password=credentials.password,
        )
        return _fetch_all_source_rows_from_odata(
            client=client,
            config=config,
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"{BOOTSTRAP_SOURCE_FETCH_FAILED}: failed to fetch bootstrap rows for '{entity_type}': {exc}"
        ) from exc
    finally:
        if client is not None:
            client.close()


def _fetch_all_source_rows_from_odata(
    *,
    client: ODataClient,
    config: _BootstrapSourceEntityConfig,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skip = 0
    page_size = int(config.page_size)
    while True:
        request_kwargs = {
            "filter_query": config.filter_query or None,
            "select_fields": config.select_fields or None,
            "top": page_size,
            "skip": skip,
        }
        if config.order_by:
            request_kwargs["order_by"] = config.order_by
        batch = client.get_entities(config.entity_name, **request_kwargs)
        normalized_batch = _map_source_rows(
            rows=batch,
            config=config,
        )
        rows.extend(normalized_batch)
        if len(batch) < page_size:
            break
        skip += len(batch)
    return rows


def _map_source_rows(
    *,
    rows: list[dict[str, Any]],
    config: _BootstrapSourceEntityConfig,
) -> list[dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            continue
        payload: dict[str, Any] = {}
        for target_key, source_key in config.field_mapping.items():
            payload[target_key] = raw_row.get(source_key)
        if (
            config.entity_type == PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT
            and config.chart_identity
            and not str(payload.get("chart_identity") or "").strip()
        ):
            payload["chart_identity"] = config.chart_identity
        normalized_rows.append(sanitize_master_data_sync_value(payload))
    return normalized_rows


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


def _resolve_source_mode(*, database: Database) -> str:
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    raw_mode = str(metadata.get("bootstrap_import_source_mode") or "").strip().lower()
    if raw_mode == BOOTSTRAP_SOURCE_MODE_METADATA_ROWS:
        return BOOTSTRAP_SOURCE_MODE_METADATA_ROWS
    return BOOTSTRAP_SOURCE_MODE_ODATA


def _resolve_metadata_source_coverage(*, database: Database, entity_scope: list[str]) -> dict[str, bool]:
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    source = metadata.get("bootstrap_import_coverage")
    if isinstance(source, Mapping):
        return {entity: bool(source.get(entity, False)) for entity in entity_scope}
    if isinstance(source, list):
        coverage_set = {str(value or "").strip().lower() for value in source}
        return {entity: entity in coverage_set for entity in entity_scope}
    rows_by_entity = metadata.get("bootstrap_import_rows")
    if isinstance(rows_by_entity, Mapping):
        return {entity: entity in rows_by_entity for entity in entity_scope}
    return {entity: False for entity in entity_scope}


def _resolve_odata_source_entity_configs(*, database: Database) -> dict[str, _BootstrapSourceEntityConfig]:
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    source = metadata.get("bootstrap_import_source")
    if not isinstance(source, Mapping):
        return {}
    entities = source.get("entities")
    if not isinstance(entities, Mapping):
        return {}

    default_page_size = _safe_page_size(source.get("page_size"), default=500)
    resolved: dict[str, _BootstrapSourceEntityConfig] = {}
    for raw_entity_type, raw_config in entities.items():
        try:
            entity_type = _normalize_entity_type(str(raw_entity_type or ""))
        except ValueError:
            continue
        if not isinstance(raw_config, Mapping):
            continue
        entity_name = str(raw_config.get("entity_name") or "").strip()
        if not entity_name:
            continue
        explicit_chart_identity = _normalize_chart_identity_config(raw_config.get("chart_identity"))
        derived_chart_identity = _derive_chart_identity_from_source_entity_name(entity_name)
        chart_identity = explicit_chart_identity or derived_chart_identity
        chart_identity_source = ""
        if explicit_chart_identity:
            chart_identity_source = "explicit_source_mapping_metadata"
        elif derived_chart_identity:
            chart_identity_source = "odata_entity_name"
        field_mapping = _normalize_field_mapping(raw_config.get("field_mapping"))
        select_fields = _normalize_select_fields(raw_config.get("select_fields"))
        if not select_fields:
            select_fields = sorted({value for value in field_mapping.values() if value})
        order_by = _normalize_select_fields(raw_config.get("order_by"))
        if not order_by and entity_type == PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT:
            order_by = _default_chart_row_source_order_by(entity_name=entity_name, field_mapping=field_mapping)
        resolved[entity_type] = _BootstrapSourceEntityConfig(
            entity_type=entity_type,
            entity_name=entity_name,
            chart_identity=chart_identity,
            chart_identity_source=chart_identity_source,
            field_mapping=field_mapping,
            select_fields=select_fields,
            filter_query=str(raw_config.get("filter_query") or "").strip(),
            page_size=_safe_page_size(raw_config.get("page_size"), default=default_page_size),
            order_by=order_by,
        )
    return resolved


def _default_chart_row_source_preflight(
    *,
    tenant_id: str,
    database: Database,
    row_source: Mapping[str, Any],
    actor_id: str,
) -> PoolMasterDataBootstrapSourcePreflightResult:
    errors: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "database_id": str(database.id),
        "source_mode": BOOTSTRAP_SOURCE_MODE_ODATA,
        "row_source": _serialize_row_source_for_diagnostics(row_source=row_source),
        "odata_url": sanitize_master_data_sync_text(str(database.odata_url or "")),
    }
    credential_strategy = "none"

    if not str(database.odata_url or "").strip():
        errors.append(
            _error(
                code=CHART_ROW_SOURCE_PROBE_FAILED,
                detail="Database OData URL is missing for chart row source probe.",
                path="database.odata_url",
            )
        )

    config: _BootstrapSourceEntityConfig | None = None
    try:
        config = _resolve_chart_row_source_entity_config(row_source=row_source)
    except ValueError as exc:
        errors.append(
            _error(
                code=CHART_ROW_SOURCE_MAPPING_INCOMPLETE,
                detail=str(exc),
                path="row_source",
            )
        )

    credentials = _resolve_mapping_credentials(database=database, actor_id=actor_id)
    if credentials is None:
        errors.append(
            _error(
                code=CHART_ROW_SOURCE_NOT_READY,
                detail="Infobase mapping is not configured for chart row source.",
                path="infobase_user_mapping",
            )
        )
    elif credentials.strategy == "ambiguous":
        errors.append(
            _error(
                code=CHART_ROW_SOURCE_NOT_READY,
                detail="Multiple infobase mappings found for chart row source.",
                path="infobase_user_mapping",
            )
        )
    else:
        credential_strategy = credentials.strategy
        if not credentials.username or not credentials.password:
            errors.append(
                _error(
                    code=CHART_ROW_SOURCE_NOT_READY,
                    detail="Infobase mapping requires non-empty username and password for chart row source.",
                    path="infobase_user_mapping.credentials",
                )
            )

    if config is not None:
        mapping_error = _validate_source_mapping_config(config=config)
        if mapping_error is not None:
            errors.append(
                _error(
                    code=CHART_ROW_SOURCE_MAPPING_INCOMPLETE,
                    detail=mapping_error,
                    path="row_source.field_mapping",
                )
            )

    if not errors and credentials is not None and config is not None:
        client: ODataClient | None = None
        try:
            client = ODataClient(
                base_url=str(database.odata_url or ""),
                username=credentials.username,
                password=credentials.password,
            )
            healthy = bool(client.health_check())
            if not healthy:
                errors.append(
                    _error(
                        code=CHART_ROW_SOURCE_PROBE_FAILED,
                        detail="Chart row source OData endpoint is unavailable.",
                        path="row_source.health_check",
                    )
                )
            else:
                _check_source_entity_availability(client=client, config=config)
        except ValueError as exc:
            errors.append(
                _error(
                    code=CHART_ROW_SOURCE_PROBE_FAILED,
                    detail=str(exc),
                    path="row_source.entity_probe",
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                _error(
                    code=CHART_ROW_SOURCE_PROBE_FAILED,
                    detail=str(exc) or "Chart row source OData endpoint is unavailable.",
                    path="row_source.entity_probe",
                )
            )
        finally:
            if client is not None:
                client.close()

    diagnostics["coverage"] = {PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT: not errors}
    diagnostics["credential_strategy"] = credential_strategy
    diagnostics["error_count"] = len(errors)
    return PoolMasterDataBootstrapSourcePreflightResult(
        ok=not errors,
        source_kind=BOOTSTRAP_SOURCE_KIND_IB_ODATA,
        coverage={PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT: not errors},
        credential_strategy=credential_strategy,
        errors=errors,
        diagnostics=sanitize_master_data_sync_value(diagnostics),
    )


def _resolve_chart_row_source_entity_config(*, row_source: Mapping[str, Any]) -> _BootstrapSourceEntityConfig:
    if not isinstance(row_source, Mapping):
        raise ValueError("Chart row source metadata is required.")
    kind = str(row_source.get("row_source_kind") or row_source.get("kind") or "").strip()
    if kind and kind != BOOTSTRAP_SOURCE_KIND_IB_ODATA:
        raise ValueError(f"Unsupported chart row source kind '{kind}'.")
    entity_name = str(
        row_source.get("row_source_entity_name")
        or row_source.get("entity_name")
        or ""
    ).strip()
    if not entity_name:
        raise ValueError("Chart row source entity name is required.")
    field_mapping = _normalize_field_mapping(
        row_source.get("row_source_field_mapping")
        or row_source.get("field_mapping")
        or {}
    )
    if not field_mapping:
        field_mapping = dict(STANDARD_CHART_ROW_SOURCE_FIELD_MAPPING)
    select_fields = _normalize_select_fields(
        row_source.get("row_source_select_fields")
        or row_source.get("select_fields")
        or []
    )
    if not select_fields:
        select_fields = sorted({value for value in field_mapping.values() if value})
    chart_identity = str(row_source.get("chart_identity") or "").strip() or _derive_chart_identity_from_source_entity_name(entity_name)
    return _BootstrapSourceEntityConfig(
        entity_type=PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT,
        entity_name=entity_name,
        chart_identity=chart_identity,
        chart_identity_source="row_source_metadata" if str(row_source.get("chart_identity") or "").strip() else "odata_entity_name",
        field_mapping=field_mapping,
        select_fields=select_fields,
        filter_query=str(row_source.get("row_source_filter_query") or row_source.get("filter_query") or "").strip(),
        page_size=_safe_page_size(row_source.get("row_source_page_size") or row_source.get("page_size"), default=500),
        order_by=_normalize_select_fields(
            row_source.get("row_source_order_by")
            or row_source.get("order_by")
            or []
        )
        or _default_chart_row_source_order_by(entity_name=entity_name, field_mapping=field_mapping),
    )


def _serialize_row_source_for_diagnostics(*, row_source: Mapping[str, Any]) -> dict[str, Any]:
    return sanitize_master_data_sync_value(
        {
            "row_source_kind": str(row_source.get("row_source_kind") or row_source.get("kind") or "").strip(),
            "row_source_entity_name": str(
                row_source.get("row_source_entity_name")
                or row_source.get("entity_name")
                or ""
            ).strip(),
            "row_source_field_mapping": _normalize_field_mapping(
                row_source.get("row_source_field_mapping")
                or row_source.get("field_mapping")
                or {}
            ),
            "row_source_select_fields": _normalize_select_fields(
                row_source.get("row_source_select_fields")
                or row_source.get("select_fields")
                or []
            ),
        }
    )


def _normalize_field_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, str] = {}
    for raw_target, raw_source in value.items():
        target_key = str(raw_target or "").strip()
        source_key = str(raw_source or "").strip()
        if not target_key or not source_key:
            continue
        normalized[target_key] = source_key
    return normalized


def _normalize_select_fields(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        token = str(item or "").strip()
        if token:
            normalized.append(token)
    return normalized


def _required_source_fields_for_entity(*, entity_type: str) -> set[str]:
    if entity_type == PoolMasterDataBootstrapImportEntityType.PARTY:
        return {"canonical_id", "name"}
    if entity_type == PoolMasterDataBootstrapImportEntityType.ITEM:
        return {"canonical_id", "name"}
    if entity_type == PoolMasterDataBootstrapImportEntityType.TAX_PROFILE:
        return {"canonical_id", "vat_code"}
    if entity_type == PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT:
        return {"canonical_id", "code", "name", "chart_identity"}
    if entity_type == PoolMasterDataBootstrapImportEntityType.CONTRACT:
        return {"canonical_id", "name", "owner_counterparty_canonical_id"}
    if entity_type == PoolMasterDataBootstrapImportEntityType.BINDING:
        return {"entity_type", "canonical_id", "ib_ref_key"}
    return {"canonical_id"}


def _validate_source_mapping_config(*, config: _BootstrapSourceEntityConfig) -> str | None:
    required_fields = _required_source_fields_for_entity(entity_type=config.entity_type)
    if config.entity_type == PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT and config.chart_identity:
        required_fields = set(required_fields)
        required_fields.discard("chart_identity")
    missing = sorted(field for field in required_fields if field not in config.field_mapping)
    if missing:
        return (
            f"Bootstrap source mapping for '{config.entity_type}' is incomplete: "
            f"missing required field(s): {', '.join(missing)}."
        )
    return None


def _check_source_entity_availability(
    *,
    client: ODataClient,
    config: _BootstrapSourceEntityConfig,
) -> None:
    request_kwargs = {
        "filter_query": config.filter_query or None,
        "select_fields": config.select_fields or None,
        "top": 1,
        "skip": 0,
    }
    if config.order_by:
        request_kwargs["order_by"] = config.order_by
    probe = client.get_entities(config.entity_name, **request_kwargs)
    if not isinstance(probe, list):
        raise ValueError(
            f"Bootstrap source probe for '{config.entity_name}' returned invalid payload."
        )
    if probe:
        first_row = probe[0]
        if isinstance(first_row, Mapping):
            missing_fields = sorted(
                source_field
                for source_field in set(config.field_mapping.values())
                if source_field and source_field not in first_row
            )
            if missing_fields:
                raise ValueError(
                    f"Bootstrap source probe for '{config.entity_name}' missed required field(s): "
                    f"{', '.join(missing_fields)}."
                )


def _safe_page_size(value: Any, *, default: int) -> int:
    try:
        page_size = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(1, min(page_size, 1000))


def _normalize_chart_identity_config(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    return _derive_chart_identity_from_source_entity_name(token) or token


def _derive_chart_identity_from_source_entity_name(entity_name: str) -> str:
    token = str(entity_name or "").strip()
    if not token:
        return ""
    if token.endswith(")"):
        token = token.rstrip(")")
    if "(" in token:
        token = token.rsplit("(", 1)[-1]
    token = token.split("/")[-1].split(".")[-1]
    if token.startswith("ChartOfAccounts_"):
        return token
    return ""


def _default_chart_row_source_order_by(*, entity_name: str, field_mapping: Mapping[str, str]) -> list[str]:
    if not _derive_chart_identity_from_source_entity_name(entity_name):
        return []
    order_by: list[str] = []
    for target_key in ("canonical_id", "code"):
        source_key = str(field_mapping.get(target_key) or "").strip()
        if source_key and source_key not in order_by:
            order_by.append(source_key)
    return order_by or list(STANDARD_CHART_ROW_SOURCE_ORDER_BY)


def _build_bootstrap_chart_candidate(
    *,
    database: Database,
    chart_identity: str,
    config_name: str,
    config_version: str,
    source_kind: str,
    derivation_method: str,
    confidence: str,
    evidence: Mapping[str, Any],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_identity = str(chart_identity or "").strip()
    evidence_payload = sanitize_master_data_sync_value(
        {
            "source": source_kind,
            "database_id": str(database.id),
            "chart_identity": normalized_identity,
            "config_name": str(config_name or "").strip(),
            "config_version": str(config_version or "").strip(),
            "evidence": dict(evidence or {}),
        }
    )
    serialized = json.dumps(evidence_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    row_source_payload: dict[str, Any] = {}
    if source_kind == "bootstrap_source_config":
        entity_name = str(evidence.get("entity_name") or "").strip()
        field_mapping = _normalize_field_mapping(evidence.get("field_mapping"))
        select_fields = _normalize_select_fields(evidence.get("select_fields"))
        if entity_name and field_mapping:
            row_source_payload = {
                "row_source_status": CHART_ROW_SOURCE_STATUS_NEEDS_PROBE,
                "row_source_kind": BOOTSTRAP_SOURCE_KIND_IB_ODATA,
                "row_source_entity_name": entity_name,
                "row_source_field_mapping": field_mapping,
                "row_source_select_fields": select_fields or sorted({value for value in field_mapping.values() if value}),
                "row_source_order_by": _normalize_select_fields(evidence.get("order_by"))
                or _default_chart_row_source_order_by(entity_name=entity_name, field_mapping=field_mapping),
                "row_source_page_size": 500,
                "row_source_derivation_method": "bootstrap_source_config",
                "row_source_credential_strategy": "",
                "row_source_diagnostics": [],
            }
    return sanitize_master_data_sync_value(
        {
            "chart_identity": normalized_identity,
            "name": normalized_identity or "GLAccount source mapping",
            "config_name": str(config_name or "").strip(),
            "config_version": str(config_version or "").strip(),
            "source_database_id": str(database.id),
            "source_database_name": str(database.name or ""),
            "source_kind": source_kind,
            "derivation_method": derivation_method,
            "confidence": confidence,
            "metadata_hash": "",
            "catalog_version": "",
            "source_evidence_fingerprint": fingerprint,
            "diagnostics": list(diagnostics or []),
            "warnings": [],
            "is_complete": bool(normalized_identity and config_name and config_version),
            **row_source_payload,
        }
    )


def _normalize_entity_scope(entity_scope: list[str]) -> list[str]:
    return [_normalize_entity_type(value) for value in entity_scope]


def _normalize_entity_type(entity_type: str) -> str:
    try:
        return normalize_pool_master_data_bootstrap_entity_type(entity_type)
    except ValueError as exc:
        raise ValueError(
            f"{BOOTSTRAP_SOURCE_ENTITY_TYPE_INVALID}: unsupported bootstrap entity_type '{entity_type}'"
        ) from exc


def _error(*, code: str, detail: str, path: str) -> dict[str, Any]:
    return {
        "code": str(code or "").strip().upper(),
        "detail": sanitize_master_data_sync_text(detail),
        "path": str(path or "").strip(),
    }


__all__ = [
    "BOOTSTRAP_SOURCE_ENTITY_COVERAGE_MISSING",
    "BOOTSTRAP_SOURCE_ENTITY_TYPE_INVALID",
    "BOOTSTRAP_SOURCE_FETCH_FAILED",
    "BOOTSTRAP_SOURCE_KIND_IB_ODATA",
    "BOOTSTRAP_SOURCE_MODE_METADATA_ROWS",
    "BOOTSTRAP_SOURCE_MAPPING_AMBIGUOUS",
    "BOOTSTRAP_SOURCE_MAPPING_INVALID",
    "BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED",
    "BOOTSTRAP_SOURCE_ODATA_URL_MISSING",
    "BOOTSTRAP_SOURCE_UNAVAILABLE",
    "CHART_ROW_SOURCE_MAPPING_INCOMPLETE",
    "CHART_ROW_SOURCE_NOT_READY",
    "CHART_ROW_SOURCE_PROBE_FAILED",
    "CHART_ROW_SOURCE_STATUS_NEEDS_MAPPING",
    "CHART_ROW_SOURCE_STATUS_NEEDS_PROBE",
    "CHART_ROW_SOURCE_STATUS_READY",
    "CHART_ROW_SOURCE_STATUS_UNAVAILABLE",
    "STANDARD_CHART_ROW_SOURCE_FIELD_MAPPING",
    "STANDARD_CHART_ROW_SOURCE_ORDER_BY",
    "STANDARD_CHART_ROW_SOURCE_SELECT_FIELDS",
    "PoolMasterDataBootstrapSourcePreflightResult",
    "build_standard_chart_odata_row_source",
    "configure_pool_master_data_bootstrap_source_callbacks",
    "discover_pool_master_data_bootstrap_source_chart_candidates",
    "fetch_pool_master_data_chart_row_source_rows",
    "fetch_pool_master_data_bootstrap_source_rows",
    "is_pool_master_data_bootstrap_source_callback_configured",
    "reset_pool_master_data_bootstrap_source_callbacks",
    "run_pool_master_data_chart_row_source_preflight",
    "run_pool_master_data_bootstrap_source_preflight",
]
