from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from django.utils import timezone

from .master_data_artifact_contract import (
    MASTER_DATA_BINDING_ARTIFACT_VERSION,
    MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
    POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_REF_CONTEXT_KEY,
    POOL_RUNTIME_MASTER_DATA_SNAPSHOT_REF_CONTEXT_KEY,
    validate_master_data_binding_artifact_v1,
)
from .master_data_bindings import upsert_pool_master_data_binding
from .master_data_dedupe import MasterDataDedupeReviewRequiredError, require_pool_master_data_dedupe_resolved
from .master_data_errors import (
    MASTER_DATA_BINDING_AMBIGUOUS,
    MASTER_DATA_BINDING_CONFLICT,
    MASTER_DATA_ENTITY_NOT_FOUND,
    MasterDataResolveError,
)
from .master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
    POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_IB_CATALOG_KIND,
    POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_NONE,
    POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_OWNER_COUNTERPARTY_CANONICAL_ID,
    get_pool_master_data_registry_entry,
    supports_pool_master_data_capability,
)
from .models import (
    PoolMasterBindingSyncStatus,
    PoolMasterContract,
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterGLAccount,
    PoolMasterItem,
    PoolMasterParty,
    PoolMasterTaxProfile,
    PoolRun,
)


MASTER_DATA_TOKEN_PREFIX = "master_data."
MASTER_DATA_TOKEN_SUFFIX = ".ref"


@dataclass(frozen=True)
class MasterDataTokenRequirement:
    token: str
    entity_type: str
    canonical_id: str
    database_id: str
    mapping_path: str = ""
    ib_catalog_kind: str = ""
    owner_counterparty_canonical_id: str = ""
    chart_identity: str = ""


def execute_master_data_resolve_upsert_gate(
    *,
    run: PoolRun,
    execution_context: Mapping[str, Any],
) -> dict[str, Any]:
    publication_payload = _resolve_publication_payload(execution_context=execution_context)
    snapshot_ref = str(
        execution_context.get(POOL_RUNTIME_MASTER_DATA_SNAPSHOT_REF_CONTEXT_KEY) or ""
    ).strip()
    binding_artifact_ref = str(
        execution_context.get(POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_REF_CONTEXT_KEY) or ""
    ).strip()
    if not snapshot_ref or not binding_artifact_ref:
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail="Missing immutable master-data snapshot/binding references in execution context.",
            entity_type="",
            canonical_id="",
            target_database_id="",
        )

    pool_runtime_payload = dict(publication_payload.get("pool_runtime") or {})
    chains_by_database_raw = pool_runtime_payload.get("document_chains_by_database")
    if not isinstance(chains_by_database_raw, Mapping):
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail="Publication payload must contain pool_runtime.document_chains_by_database object.",
            entity_type="",
            canonical_id="",
            target_database_id="",
        )

    chains_by_database = {
        str(database_id): list(chains)
        for database_id, chains in chains_by_database_raw.items()
        if str(database_id).strip() and isinstance(chains, list)
    }
    bindings_rows: list[dict[str, Any]] = []
    bindings_count_by_database: dict[str, int] = {}

    for database_id, chains in chains_by_database.items():
        for chain_raw in chains:
            if not isinstance(chain_raw, dict):
                continue
            documents_raw = chain_raw.get("documents")
            if not isinstance(documents_raw, list):
                continue
            for document_raw in documents_raw:
                if not isinstance(document_raw, dict):
                    continue
                resolved_master_data_refs = (
                    dict(document_raw.get("resolved_master_data_refs"))
                    if isinstance(document_raw.get("resolved_master_data_refs"), dict)
                    else {}
                )
                resolved_master_data_refs_by_path = (
                    dict(document_raw.get("resolved_master_data_refs_by_path"))
                    if isinstance(document_raw.get("resolved_master_data_refs_by_path"), dict)
                    else {}
                )
                requirements = _extract_requirements_from_document(
                    document=document_raw,
                    database_id=database_id,
                )
                token_conflicts: set[str] = set()
                for requirement in requirements:
                    ib_ref_key = _resolve_requirement_ib_ref_key(
                        run=run,
                        requirement=requirement,
                    )
                    if requirement.mapping_path:
                        resolved_master_data_refs_by_path[requirement.mapping_path] = ib_ref_key
                    if requirement.token not in token_conflicts:
                        existing_ref = str(resolved_master_data_refs.get(requirement.token) or "").strip()
                        if not existing_ref:
                            resolved_master_data_refs[requirement.token] = ib_ref_key
                        elif existing_ref != ib_ref_key:
                            token_conflicts.add(requirement.token)
                            resolved_master_data_refs.pop(requirement.token, None)
                    bindings_rows.append(
                        {
                            "database_id": database_id,
                            "token": requirement.token,
                            "mapping_path": requirement.mapping_path,
                            "entity_type": requirement.entity_type,
                            "canonical_id": requirement.canonical_id,
                            "ib_catalog_kind": requirement.ib_catalog_kind,
                            "owner_counterparty_canonical_id": requirement.owner_counterparty_canonical_id,
                            "chart_identity": requirement.chart_identity,
                            "ib_ref_key": ib_ref_key,
                        }
                    )
                if resolved_master_data_refs:
                    document_raw["resolved_master_data_refs"] = resolved_master_data_refs
                if resolved_master_data_refs_by_path:
                    document_raw["resolved_master_data_refs_by_path"] = resolved_master_data_refs_by_path

        bindings_count_by_database[database_id] = sum(
            1
            for row in bindings_rows
            if str(row.get("database_id") or "").strip() == database_id
        )

    targets = [
        {
            "database_id": database_id,
            "bindings_count": int(bindings_count_by_database.get(database_id) or 0),
        }
        for database_id in sorted(chains_by_database.keys())
    ]
    bindings_rows = sorted(
        bindings_rows,
        key=lambda item: (
            str(item.get("database_id") or ""),
            str(item.get("mapping_path") or ""),
            str(item.get("token") or ""),
        ),
    )

    pool_runtime_payload["document_chains_by_database"] = chains_by_database
    pool_runtime_payload["master_data_gate_mode"] = MASTER_DATA_GATE_MODE_RESOLVE_UPSERT
    pool_runtime_payload["master_data_snapshot_ref"] = snapshot_ref
    pool_runtime_payload["master_data_binding_artifact_ref"] = binding_artifact_ref

    artifact = validate_master_data_binding_artifact_v1(
        artifact={
            "version": MASTER_DATA_BINDING_ARTIFACT_VERSION,
            "run_id": str(run.id),
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "snapshot_ref": snapshot_ref,
            "binding_artifact_ref": binding_artifact_ref,
            "targets": targets,
            "bindings": bindings_rows,
            "diagnostics": [],
            "generated_at": timezone.now().isoformat(),
        }
    )
    return {
        "publication_payload": {"pool_runtime": pool_runtime_payload},
        "binding_artifact": artifact,
        "summary": {
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "bindings_count": len(bindings_rows),
            "targets_count": len(targets),
        },
    }


def publication_payload_requires_master_data_resolution(
    *,
    execution_context: Mapping[str, Any],
) -> bool:
    try:
        publication_payload = _resolve_publication_payload(execution_context=execution_context)
    except MasterDataResolveError:
        return False

    pool_runtime_payload = publication_payload.get("pool_runtime")
    if not isinstance(pool_runtime_payload, Mapping):
        return False

    chains_by_database_raw = pool_runtime_payload.get("document_chains_by_database")
    if not isinstance(chains_by_database_raw, Mapping):
        return False

    for database_id_raw, chains_raw in chains_by_database_raw.items():
        database_id = str(database_id_raw or "").strip()
        if not database_id or not isinstance(chains_raw, list):
            continue
        for chain_raw in chains_raw:
            if not isinstance(chain_raw, Mapping):
                continue
            documents_raw = chain_raw.get("documents")
            if not isinstance(documents_raw, list):
                continue
            for document_raw in documents_raw:
                if not isinstance(document_raw, Mapping):
                    continue
                if _extract_requirements_from_document(
                    document=document_raw,
                    database_id=database_id,
                ):
                    return True
    return False


def collect_master_data_resolution_readiness_blockers(
    *,
    run: PoolRun,
    execution_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    try:
        publication_payload = _resolve_publication_payload(execution_context=execution_context)
    except MasterDataResolveError:
        return []

    pool_runtime_payload = dict(publication_payload.get("pool_runtime") or {})
    chains_by_database_raw = pool_runtime_payload.get("document_chains_by_database")
    if not isinstance(chains_by_database_raw, Mapping):
        return []

    blockers: list[dict[str, Any]] = []
    seen_requirements: set[tuple[str, str]] = set()
    for database_id_raw, chains_raw in sorted(
        chains_by_database_raw.items(),
        key=lambda item: str(item[0] or ""),
    ):
        database_id = str(database_id_raw or "").strip()
        if not database_id or not isinstance(chains_raw, list):
            continue
        for chain_raw in chains_raw:
            if not isinstance(chain_raw, Mapping):
                continue
            documents_raw = chain_raw.get("documents")
            if not isinstance(documents_raw, list):
                continue
            for document_raw in documents_raw:
                if not isinstance(document_raw, Mapping):
                    continue
                try:
                    requirements = _extract_requirements_from_document(
                        document=document_raw,
                        database_id=database_id,
                    )
                except MasterDataResolveError as exc:
                    blockers.append(
                        _build_readiness_blocker_from_master_data_error(
                            exc,
                            kind="token_requirement_invalid",
                        )
                    )
                    continue
                for requirement in requirements:
                    requirement_key = (
                        requirement.database_id,
                        requirement.mapping_path or requirement.token,
                        requirement.chart_identity,
                    )
                    if requirement_key in seen_requirements:
                        continue
                    seen_requirements.add(requirement_key)
                    blocker = _collect_requirement_readiness_blocker(
                        run=run,
                        requirement=requirement,
                    )
                    if blocker is not None:
                        blockers.append(blocker)
    return _sort_readiness_blockers(blockers)


def _resolve_publication_payload(*, execution_context: Mapping[str, Any]) -> dict[str, Any]:
    payload = execution_context.get("pool_runtime_publication_payload")
    if not isinstance(payload, Mapping):
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail="Missing pool_runtime_publication_payload in execution context.",
            entity_type="",
            canonical_id="",
            target_database_id="",
        )
    pool_runtime_payload = payload.get("pool_runtime")
    if not isinstance(pool_runtime_payload, Mapping):
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail="pool_runtime_publication_payload.pool_runtime must be an object.",
            entity_type="",
            canonical_id="",
            target_database_id="",
        )
    return {"pool_runtime": dict(pool_runtime_payload)}


def _extract_requirements_from_document(
    *,
    document: Mapping[str, Any],
    database_id: str,
) -> list[MasterDataTokenRequirement]:
    requirements: list[MasterDataTokenRequirement] = []
    seen_tokens: set[tuple[str, str]] = set()
    token_context = (
        dict(document.get("master_data_token_context"))
        if isinstance(document.get("master_data_token_context"), Mapping)
        else {}
    )

    def _collect(value: Any, path: str) -> None:
        if isinstance(value, str):
            token = value.strip()
            if (
                token
                and token.startswith(MASTER_DATA_TOKEN_PREFIX)
                and token.endswith(MASTER_DATA_TOKEN_SUFFIX)
                and (path, token) not in seen_tokens
            ):
                requirement = _parse_master_data_token(token=token, database_id=database_id)
                context_entry = token_context.get(path)
                if requirement.entity_type == PoolMasterDataEntityType.GL_ACCOUNT:
                    if not isinstance(context_entry, Mapping):
                        raise MasterDataResolveError(
                            code=MASTER_DATA_BINDING_CONFLICT,
                            detail=(
                                f"GLAccount token '{token}' requires typed metadata context for mapping path '{path}'."
                            ),
                            entity_type=requirement.entity_type,
                            canonical_id=requirement.canonical_id,
                            target_database_id=database_id,
                        )
                    context_token = str(context_entry.get("token") or "").strip()
                    chart_identity = str(context_entry.get("chart_identity") or "").strip()
                    if context_token != token or not chart_identity:
                        raise MasterDataResolveError(
                            code=MASTER_DATA_BINDING_CONFLICT,
                            detail=(
                                f"GLAccount token '{token}' requires chart_identity metadata for mapping path '{path}'."
                            ),
                            entity_type=requirement.entity_type,
                            canonical_id=requirement.canonical_id,
                            target_database_id=database_id,
                        )
                    requirement = MasterDataTokenRequirement(
                        token=requirement.token,
                        entity_type=requirement.entity_type,
                        canonical_id=requirement.canonical_id,
                        database_id=requirement.database_id,
                        mapping_path=path,
                        chart_identity=chart_identity,
                    )
                else:
                    requirement = MasterDataTokenRequirement(
                        token=requirement.token,
                        entity_type=requirement.entity_type,
                        canonical_id=requirement.canonical_id,
                        database_id=requirement.database_id,
                        mapping_path=path,
                        ib_catalog_kind=requirement.ib_catalog_kind,
                        owner_counterparty_canonical_id=requirement.owner_counterparty_canonical_id,
                    )
                requirements.append(requirement)
                seen_tokens.add((path, token))
            return
        if isinstance(value, Mapping):
            for key, nested in value.items():
                key_token = str(key or "").strip()
                if not key_token:
                    continue
                nested_path = f"{path}.{key_token}" if path else key_token
                _collect(nested, nested_path)
            return
        if isinstance(value, list):
            for index, nested in enumerate(value):
                nested_path = f"{path}[{index}]"
                _collect(nested, nested_path)

    _collect(document.get("field_mapping"), "field_mapping")
    _collect(document.get("table_parts_mapping"), "table_parts_mapping")
    return requirements


def _parse_master_data_token(*, token: str, database_id: str) -> MasterDataTokenRequirement:
    body = token.removeprefix(MASTER_DATA_TOKEN_PREFIX).removesuffix(MASTER_DATA_TOKEN_SUFFIX)
    separator_index = body.find(".")
    if separator_index <= 0 or separator_index == len(body) - 1:
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail=f"Invalid master-data token '{token}': expected master_data.<entity>.<canonical>.<...>.ref",
            entity_type="",
            canonical_id="",
            target_database_id=database_id,
        )

    entity_type = body[:separator_index].strip()
    remainder = body[separator_index + 1 :].strip()
    if not entity_type or not remainder:
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail=f"Invalid master-data token '{token}': expected master_data.<entity>.<canonical>.<...>.ref",
            entity_type="",
            canonical_id="",
            target_database_id=database_id,
        )

    entry = get_pool_master_data_registry_entry(entity_type)
    canonical_id = remainder
    qualifier = ""
    if entry is None or not supports_pool_master_data_capability(
        entity_type=entity_type,
        capability=POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
    ):
        raise MasterDataResolveError(
            code=MASTER_DATA_ENTITY_NOT_FOUND,
            detail=f"Unsupported master-data token entity_type '{entity_type}' in token '{token}'.",
            entity_type=entity_type,
            canonical_id=canonical_id,
            target_database_id=database_id,
        )

    qualifier_kind = entry.token_contract.qualifier_kind
    qualifier_options = tuple(
        str(value or "").strip()
        for value in entry.token_contract.qualifier_options
        if str(value or "").strip()
    )
    if qualifier_kind == POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_NONE:
        return MasterDataTokenRequirement(
            token=token,
            entity_type=entity_type,
            canonical_id=canonical_id,
            database_id=database_id,
        )

    if qualifier_options:
        matched_qualifier = next(
            (
                option
                for option in sorted(qualifier_options, key=len, reverse=True)
                if remainder.endswith(f".{option}")
            ),
            "",
        )
        if matched_qualifier:
            canonical_id = remainder[: -(len(matched_qualifier) + 1)].strip()
            qualifier = matched_qualifier
        elif entry.token_contract.qualifier_required:
            raise MasterDataResolveError(
                code=MASTER_DATA_BINDING_CONFLICT,
                detail=(
                    f"Token '{token}' must use one of registry qualifier options: "
                    f"{'|'.join(qualifier_options)}."
                ),
                entity_type=entity_type,
                canonical_id=remainder,
                target_database_id=database_id,
            )
        if not canonical_id:
            raise MasterDataResolveError(
                code=MASTER_DATA_BINDING_CONFLICT,
                detail=f"Token '{token}' must include canonical id for entity_type '{entity_type}'.",
                entity_type=entity_type,
                canonical_id="",
                target_database_id=database_id,
            )
    elif qualifier_kind != POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_NONE:
        if entry.token_contract.qualifier_required:
            qualifier_separator_index = remainder.rfind(".")
            if (
                qualifier_separator_index <= 0
                or qualifier_separator_index == len(remainder) - 1
            ):
                raise MasterDataResolveError(
                    code=MASTER_DATA_BINDING_CONFLICT,
                    detail=(
                        f"Token '{token}' must include qualifier for entity_type '{entity_type}'."
                    ),
                    entity_type=entity_type,
                    canonical_id=remainder,
                    target_database_id=database_id,
                )
            canonical_id = remainder[:qualifier_separator_index].strip()
            qualifier = remainder[qualifier_separator_index + 1 :].strip()
            if not canonical_id or not qualifier:
                raise MasterDataResolveError(
                    code=MASTER_DATA_BINDING_CONFLICT,
                    detail=(
                        f"Token '{token}' must include qualifier for entity_type '{entity_type}'."
                    ),
                    entity_type=entity_type,
                    canonical_id=remainder,
                    target_database_id=database_id,
                )

    if qualifier_kind == POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_IB_CATALOG_KIND:
        if entry.token_contract.qualifier_required and not qualifier:
            raise MasterDataResolveError(
                code=MASTER_DATA_BINDING_CONFLICT,
                detail=(
                    f"Token '{token}' must include qualifier for entity_type '{entity_type}'."
                ),
                entity_type=entity_type,
                canonical_id=canonical_id,
                target_database_id=database_id,
            )
        if qualifier_options and qualifier and qualifier not in qualifier_options:
            raise MasterDataResolveError(
                code=MASTER_DATA_BINDING_CONFLICT,
                detail=(
                    f"Token '{token}' must use one of registry qualifier options: "
                    f"{'|'.join(qualifier_options)}."
                ),
                entity_type=entity_type,
                canonical_id=canonical_id,
                target_database_id=database_id,
            )
        return MasterDataTokenRequirement(
            token=token,
            entity_type=entity_type,
            canonical_id=canonical_id,
            database_id=database_id,
            ib_catalog_kind=qualifier,
        )

    if qualifier_kind == POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_OWNER_COUNTERPARTY_CANONICAL_ID:
        if entry.token_contract.qualifier_required and not qualifier:
            raise MasterDataResolveError(
                code=MASTER_DATA_BINDING_CONFLICT,
                detail=f"Contract token '{token}' must include owner counterparty canonical id.",
                entity_type=entity_type,
                canonical_id=canonical_id,
                target_database_id=database_id,
            )
        return MasterDataTokenRequirement(
            token=token,
            entity_type=entity_type,
            canonical_id=canonical_id,
            database_id=database_id,
            owner_counterparty_canonical_id=qualifier,
        )

    if qualifier_kind != POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_NONE:
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail=f"Unsupported token qualifier kind '{qualifier_kind}' for entity_type '{entity_type}'.",
            entity_type=entity_type,
            canonical_id=canonical_id,
            target_database_id=database_id,
        )


def _resolve_requirement_ib_ref_key(
    *,
    run: PoolRun,
    requirement: MasterDataTokenRequirement,
) -> str:
    database = run.tenant.databases.filter(id=requirement.database_id).first()
    if database is None:
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail=f"Target database '{requirement.database_id}' is not available for pool run tenant.",
            entity_type=requirement.entity_type,
            canonical_id=requirement.canonical_id,
            target_database_id=requirement.database_id,
        )

    existing_qs = PoolMasterDataBinding.objects.filter(
        tenant=run.tenant,
        entity_type=requirement.entity_type,
        canonical_id=requirement.canonical_id,
        database=database,
        ib_catalog_kind=requirement.ib_catalog_kind,
        owner_counterparty_canonical_id=requirement.owner_counterparty_canonical_id,
        chart_identity=requirement.chart_identity,
    ).order_by("created_at", "id")
    existing = list(existing_qs[:2])
    if len(existing) > 1:
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_AMBIGUOUS,
            detail="Ambiguous binding scope: multiple bindings match token requirement.",
            entity_type=requirement.entity_type,
            canonical_id=requirement.canonical_id,
            target_database_id=requirement.database_id,
            errors=[{"binding_id": str(item.id)} for item in existing],
        )
    if existing:
        return str(existing[0].ib_ref_key)

    ib_ref_key = _resolve_ib_ref_key_from_canonical_entity(
        run=run,
        requirement=requirement,
        database_id=requirement.database_id,
    )
    upsert_result = upsert_pool_master_data_binding(
        tenant=run.tenant,
        entity_type=requirement.entity_type,
        canonical_id=requirement.canonical_id,
        database=database,
        ib_ref_key=ib_ref_key,
        ib_catalog_kind=requirement.ib_catalog_kind,
        owner_counterparty_canonical_id=requirement.owner_counterparty_canonical_id,
        chart_identity=requirement.chart_identity,
        sync_status=PoolMasterBindingSyncStatus.UPSERTED,
    )
    return str(upsert_result.binding.ib_ref_key)


def _collect_requirement_readiness_blocker(
    *,
    run: PoolRun,
    requirement: MasterDataTokenRequirement,
) -> dict[str, Any] | None:
    database = run.tenant.databases.filter(id=requirement.database_id).only("id").first()
    if database is None:
        return _build_requirement_readiness_blocker(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail="Target database is not available for the pool run tenant.",
            kind="target_database_missing",
            requirement=requirement,
        )

    existing_qs = PoolMasterDataBinding.objects.filter(
        tenant=run.tenant,
        entity_type=requirement.entity_type,
        canonical_id=requirement.canonical_id,
        database=database,
        ib_catalog_kind=requirement.ib_catalog_kind,
        owner_counterparty_canonical_id=requirement.owner_counterparty_canonical_id,
        chart_identity=requirement.chart_identity,
    ).order_by("created_at", "id")
    existing = list(existing_qs[:2])
    if len(existing) > 1:
        return _build_requirement_readiness_blocker(
            code=MASTER_DATA_BINDING_AMBIGUOUS,
            detail="Ambiguous binding scope: multiple bindings match token requirement.",
            kind="binding_ambiguous",
            requirement=requirement,
            diagnostic_extra={
                "binding_ids": [str(item.id) for item in existing],
            },
        )
    if existing:
        return None

    try:
        entity = _load_canonical_entity(run=run, requirement=requirement)
    except MasterDataResolveError as exc:
        if exc.code != MASTER_DATA_ENTITY_NOT_FOUND:
            return _build_readiness_blocker_from_master_data_error(exc)
        return _build_requirement_readiness_blocker(
            code=exc.code,
            detail="Canonical master-data entity is missing for the publication target binding scope.",
            kind="canonical_entity_missing",
            requirement=requirement,
        )

    metadata = entity.metadata if isinstance(getattr(entity, "metadata", None), Mapping) else {}
    ib_ref_key = _read_ib_ref_key_from_metadata(
        metadata=metadata,
        entity_type=requirement.entity_type,
        database_id=requirement.database_id,
        party_catalog_kind=requirement.ib_catalog_kind,
        owner_counterparty_canonical_id=requirement.owner_counterparty_canonical_id,
        chart_identity=requirement.chart_identity,
    )
    if ib_ref_key:
        return None

    return _build_requirement_readiness_blocker(
        code=MASTER_DATA_BINDING_CONFLICT,
        detail="Canonical master-data entity does not provide ib_ref_key for the target database binding scope.",
        kind="binding_source_missing",
        requirement=requirement,
    )


def _resolve_ib_ref_key_from_canonical_entity(
    *,
    run: PoolRun,
    requirement: MasterDataTokenRequirement,
    database_id: str,
) -> str:
    entity = _load_canonical_entity(run=run, requirement=requirement)
    metadata = entity.metadata if isinstance(getattr(entity, "metadata", None), Mapping) else {}
    ib_ref_key = _read_ib_ref_key_from_metadata(
        metadata=metadata,
        entity_type=requirement.entity_type,
        database_id=database_id,
        party_catalog_kind=requirement.ib_catalog_kind,
        owner_counterparty_canonical_id=requirement.owner_counterparty_canonical_id,
        chart_identity=requirement.chart_identity,
    )
    if not ib_ref_key:
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail=(
                "Cannot resolve ib_ref_key from canonical metadata. "
                "Expected metadata.ib_ref_keys[database_id] for entity scope."
            ),
            entity_type=requirement.entity_type,
            canonical_id=requirement.canonical_id,
            target_database_id=database_id,
        )
    return ib_ref_key


def _load_canonical_entity(
    *,
    run: PoolRun,
    requirement: MasterDataTokenRequirement,
) -> Any:
    entity = None
    if requirement.entity_type == PoolMasterDataEntityType.PARTY:
        entity = PoolMasterParty.objects.filter(
            tenant=run.tenant,
            canonical_id=requirement.canonical_id,
        ).first()
    elif requirement.entity_type == PoolMasterDataEntityType.ITEM:
        entity = PoolMasterItem.objects.filter(
            tenant=run.tenant,
            canonical_id=requirement.canonical_id,
        ).first()
    elif requirement.entity_type == PoolMasterDataEntityType.TAX_PROFILE:
        entity = PoolMasterTaxProfile.objects.filter(
            tenant=run.tenant,
            canonical_id=requirement.canonical_id,
        ).first()
    elif requirement.entity_type == PoolMasterDataEntityType.CONTRACT:
        entity = PoolMasterContract.objects.filter(
            tenant=run.tenant,
            canonical_id=requirement.canonical_id,
            owner_counterparty__canonical_id=requirement.owner_counterparty_canonical_id,
        ).select_related("owner_counterparty").first()
    elif requirement.entity_type == PoolMasterDataEntityType.GL_ACCOUNT:
        entity = PoolMasterGLAccount.objects.filter(
            tenant=run.tenant,
            canonical_id=requirement.canonical_id,
            chart_identity=requirement.chart_identity,
        ).first()

    if entity is None:
        raise MasterDataResolveError(
            code=MASTER_DATA_ENTITY_NOT_FOUND,
            detail="Canonical master-data entity is not found for gate requirement.",
            entity_type=requirement.entity_type,
            canonical_id=requirement.canonical_id,
            target_database_id=requirement.database_id,
        )
    try:
        require_pool_master_data_dedupe_resolved(
            tenant_id=str(run.tenant_id),
            entity_type=requirement.entity_type,
            canonical_id=requirement.canonical_id,
        )
    except MasterDataDedupeReviewRequiredError as exc:
        raise MasterDataResolveError(
            code=exc.code,
            detail=exc.detail,
            entity_type=requirement.entity_type,
            canonical_id=requirement.canonical_id,
            target_database_id=requirement.database_id,
            errors=[exc.to_diagnostic()],
        ) from exc
    return entity


def _read_ib_ref_key_from_metadata(
    *,
    metadata: Mapping[str, Any],
    entity_type: str,
    database_id: str,
    party_catalog_kind: str,
    owner_counterparty_canonical_id: str,
    chart_identity: str,
) -> str:
    ib_ref_keys = metadata.get("ib_ref_keys")
    if not isinstance(ib_ref_keys, Mapping):
        return ""
    database_entry = ib_ref_keys.get(database_id)
    if database_entry is None:
        return ""

    if entity_type == PoolMasterDataEntityType.PARTY:
        if isinstance(database_entry, Mapping):
            return str(database_entry.get(party_catalog_kind) or "").strip()
        return ""

    if entity_type == PoolMasterDataEntityType.CONTRACT:
        if not isinstance(database_entry, Mapping):
            return ""
        return str(database_entry.get(owner_counterparty_canonical_id) or "").strip()

    if entity_type == PoolMasterDataEntityType.GL_ACCOUNT:
        if not isinstance(database_entry, Mapping):
            return ""
        return str(database_entry.get(chart_identity) or database_entry.get("ref") or "").strip()

    if isinstance(database_entry, str):
        return database_entry.strip()
    if isinstance(database_entry, Mapping):
        return str(database_entry.get("ref") or database_entry.get("value") or "").strip()
    return ""


def _build_requirement_readiness_blocker(
    *,
    code: str,
    detail: str,
    kind: str,
    requirement: MasterDataTokenRequirement,
    diagnostic_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blocker: dict[str, Any] = {
        "code": code,
        "detail": detail,
        "kind": kind,
        "entity_name": requirement.entity_type,
        "field_or_table_path": requirement.mapping_path or requirement.canonical_id,
        "database_id": requirement.database_id,
    }
    diagnostic = _build_requirement_readiness_diagnostic(
        requirement=requirement,
        diagnostic_extra=diagnostic_extra,
    )
    if diagnostic:
        blocker["diagnostic"] = diagnostic
    return blocker


def _build_requirement_readiness_diagnostic(
    *,
    requirement: MasterDataTokenRequirement,
    diagnostic_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "canonical_id": requirement.canonical_id,
        "token": requirement.token,
    }
    scope_hint = _resolve_requirement_scope_hint(requirement=requirement)
    if scope_hint:
        diagnostic["scope_hint"] = scope_hint
    if requirement.owner_counterparty_canonical_id:
        diagnostic["owner_counterparty_canonical_id"] = requirement.owner_counterparty_canonical_id
    if requirement.chart_identity:
        diagnostic["chart_identity"] = requirement.chart_identity
    if requirement.mapping_path:
        diagnostic["mapping_path"] = requirement.mapping_path
    if diagnostic_extra:
        diagnostic.update(dict(diagnostic_extra))
    return diagnostic


def _build_readiness_blocker_from_master_data_error(
    exc: MasterDataResolveError,
    *,
    kind: str | None = None,
) -> dict[str, Any]:
    blocker: dict[str, Any] = {
        "code": exc.code,
        "detail": exc.detail,
    }
    resolved_kind = kind or _resolve_readiness_blocker_kind_from_error_code(exc.code)
    if resolved_kind:
        blocker["kind"] = resolved_kind
    if exc.entity_type:
        blocker["entity_name"] = exc.entity_type
    if exc.canonical_id:
        blocker["field_or_table_path"] = exc.canonical_id
    if exc.target_database_id:
        blocker["database_id"] = exc.target_database_id
    diagnostic = exc.to_diagnostic()
    if diagnostic:
        blocker["diagnostic"] = diagnostic
        mapping_path = str(diagnostic.get("mapping_path") or "").strip()
        if mapping_path:
            blocker["field_or_table_path"] = mapping_path
    return blocker


def _resolve_readiness_blocker_kind_from_error_code(error_code: str) -> str | None:
    if error_code == MASTER_DATA_ENTITY_NOT_FOUND:
        return "canonical_entity_missing"
    if error_code == MASTER_DATA_BINDING_AMBIGUOUS:
        return "binding_ambiguous"
    if error_code == MASTER_DATA_BINDING_CONFLICT:
        return "binding_conflict"
    return None


def _resolve_requirement_scope_hint(*, requirement: MasterDataTokenRequirement) -> str:
    if requirement.ib_catalog_kind:
        return requirement.ib_catalog_kind
    if requirement.owner_counterparty_canonical_id:
        return requirement.owner_counterparty_canonical_id
    if requirement.chart_identity:
        return requirement.chart_identity
    return ""


def _sort_readiness_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    code_priority = {
        MASTER_DATA_BINDING_CONFLICT: 10,
        MASTER_DATA_BINDING_AMBIGUOUS: 20,
        MASTER_DATA_ENTITY_NOT_FOUND: 30,
    }
    return sorted(
        blockers,
        key=lambda blocker: (
            code_priority.get(str(blocker.get("code") or "").strip(), 100),
            str(blocker.get("kind") or ""),
            str(blocker.get("database_id") or ""),
            str(blocker.get("organization_id") or ""),
            str(blocker.get("entity_name") or ""),
            str(blocker.get("field_or_table_path") or ""),
            str(blocker.get("detail") or ""),
        ),
    )
