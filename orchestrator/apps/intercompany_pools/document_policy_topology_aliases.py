from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .models import PoolNodeVersion


POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID = "POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID"
MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING = "MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING"
MASTER_DATA_PARTY_ROLE_MISSING = "MASTER_DATA_PARTY_ROLE_MISSING"

_MASTER_DATA_TOKEN_PREFIX = "master_data."
_MASTER_DATA_TOKEN_SUFFIX = ".ref"
_PARTICIPANT_SIDES = {"parent", "child"}
_PARTY_ROLES = {"organization", "counterparty"}


@dataclass(frozen=True)
class TopologyAwareMasterDataAliasError(ValueError):
    code: str
    detail: str
    field_or_table_path: str = ""
    organization_id: str = ""
    database_id: str = ""
    edge_ref: Mapping[str, str] | None = None
    participant_side: str = ""
    required_role: str = ""
    diagnostic: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        ValueError.__init__(self, f"{self.code}: {self.detail}")

    def to_blocker(self) -> dict[str, Any]:
        blocker: dict[str, Any] = {
            "code": self.code,
            "detail": self.detail,
        }
        has_participant_context = bool(
            self.organization_id
            or self.edge_ref
            or self.participant_side
            or self.required_role
        )
        if self.field_or_table_path:
            blocker["field_or_table_path"] = self.field_or_table_path
        if self.organization_id or has_participant_context:
            blocker["organization_id"] = self.organization_id
        if self.database_id or has_participant_context:
            blocker["database_id"] = self.database_id
        if self.edge_ref:
            blocker["edge_ref"] = {
                "parent_node_id": str(self.edge_ref.get("parent_node_id") or "").strip(),
                "child_node_id": str(self.edge_ref.get("child_node_id") or "").strip(),
            }
        if self.participant_side:
            blocker["participant_side"] = self.participant_side
        if self.required_role:
            blocker["required_role"] = self.required_role
        if self.diagnostic:
            blocker["diagnostic"] = dict(self.diagnostic)
        return blocker


@dataclass(frozen=True)
class _TopologyAwareMasterDataAlias:
    entity_type: str
    participant_side: str
    required_role: str
    contract_canonical_id: str = ""


@dataclass(frozen=True)
class _TopologyEdgeParticipants:
    edge_ref: Mapping[str, str]
    parent_node: PoolNodeVersion
    child_node: PoolNodeVersion


def rewrite_document_policy_mappings_for_edge(
    *,
    field_mapping: Mapping[str, Any],
    table_parts_mapping: Mapping[str, Any],
    edge_ref: Mapping[str, str],
    parent_node: PoolNodeVersion,
    child_node: PoolNodeVersion,
    field_mapping_path: str,
    table_parts_mapping_path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    participants = _TopologyEdgeParticipants(
        edge_ref=dict(edge_ref),
        parent_node=parent_node,
        child_node=child_node,
    )
    rewritten_field_mapping = _rewrite_mapping_value(
        value=field_mapping,
        path=field_mapping_path,
        participants=participants,
    )
    rewritten_table_parts_mapping = _rewrite_mapping_value(
        value=table_parts_mapping,
        path=table_parts_mapping_path,
        participants=participants,
    )
    return _as_object(rewritten_field_mapping), _as_object(rewritten_table_parts_mapping)


def _rewrite_mapping_value(
    *,
    value: Any,
    path: str,
    participants: _TopologyEdgeParticipants,
) -> Any:
    if isinstance(value, Mapping):
        return {
            str(raw_key): _rewrite_mapping_value(
                value=raw_item,
                path=f"{path}.{str(raw_key)}",
                participants=participants,
            )
            for raw_key, raw_item in value.items()
        }
    if isinstance(value, list):
        return [
            _rewrite_mapping_value(
                value=item,
                path=f"{path}[{index}]",
                participants=participants,
            )
            for index, item in enumerate(value)
        ]
    if not isinstance(value, str):
        return value

    token = value.strip()
    alias = _parse_topology_aware_master_data_alias(token=token, path=path)
    if alias is None:
        return value

    participant = _resolve_participant_party(
        participants=participants,
        participant_side=alias.participant_side,
        required_role=alias.required_role,
        token=token,
        path=path,
    )
    if alias.entity_type == "party":
        return f"master_data.party.{participant['canonical_id']}.{alias.required_role}.ref"
    return (
        "master_data.contract."
        f"{alias.contract_canonical_id}.{participant['canonical_id']}.ref"
    )


def _parse_topology_aware_master_data_alias(
    *,
    token: str,
    path: str,
) -> _TopologyAwareMasterDataAlias | None:
    if not token.startswith(_MASTER_DATA_TOKEN_PREFIX) or not token.endswith(_MASTER_DATA_TOKEN_SUFFIX):
        return None

    body = token.removeprefix(_MASTER_DATA_TOKEN_PREFIX).removesuffix(_MASTER_DATA_TOKEN_SUFFIX)
    segments = [segment.strip() for segment in body.split(".") if segment.strip()]
    if not segments:
        return None

    entity_type = segments[0]
    if entity_type == "party" and len(segments) >= 4 and segments[1] == "edge":
        participant_side = segments[2] if len(segments) > 2 else ""
        required_role = segments[3] if len(segments) > 3 else ""
        if len(segments) != 4 or participant_side not in _PARTICIPANT_SIDES or required_role not in _PARTY_ROLES:
            raise _build_invalid_alias_error(token=token, path=path)
        return _TopologyAwareMasterDataAlias(
            entity_type="party",
            participant_side=participant_side,
            required_role=required_role,
        )

    if entity_type == "contract" and len(segments) >= 4 and segments[2] == "edge":
        contract_canonical_id = segments[1] if len(segments) > 1 else ""
        participant_side = segments[3] if len(segments) > 3 else ""
        if len(segments) != 4 or not contract_canonical_id or participant_side not in _PARTICIPANT_SIDES:
            raise _build_invalid_alias_error(token=token, path=path)
        return _TopologyAwareMasterDataAlias(
            entity_type="contract",
            participant_side=participant_side,
            required_role="counterparty",
            contract_canonical_id=contract_canonical_id,
        )

    return None


def _resolve_participant_party(
    *,
    participants: _TopologyEdgeParticipants,
    participant_side: str,
    required_role: str,
    token: str,
    path: str,
) -> dict[str, str]:
    node = participants.parent_node if participant_side == "parent" else participants.child_node
    organization = node.organization
    organization_id = str(node.organization_id or "").strip()
    database_id = str(getattr(organization, "database_id", "") or "").strip()
    master_party = getattr(organization, "master_party", None) if organization.master_party_id else None
    if master_party is None:
        raise TopologyAwareMasterDataAliasError(
            code=MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING,
            detail="Missing Organization->Party binding for topology participant required by document policy alias.",
            field_or_table_path=path,
            organization_id=organization_id,
            database_id=database_id,
            edge_ref=participants.edge_ref,
            participant_side=participant_side,
            required_role=required_role,
            diagnostic={"token": token},
        )

    if required_role == "organization" and not bool(master_party.is_our_organization):
        raise _build_missing_role_error(
            token=token,
            path=path,
            participants=participants,
            participant_side=participant_side,
            required_role=required_role,
            organization_id=organization_id,
            database_id=database_id,
            master_party_canonical_id=str(master_party.canonical_id or "").strip(),
        )
    if required_role == "counterparty" and not bool(master_party.is_counterparty):
        raise _build_missing_role_error(
            token=token,
            path=path,
            participants=participants,
            participant_side=participant_side,
            required_role=required_role,
            organization_id=organization_id,
            database_id=database_id,
            master_party_canonical_id=str(master_party.canonical_id or "").strip(),
        )

    return {
        "canonical_id": str(master_party.canonical_id or "").strip(),
    }


def _build_invalid_alias_error(*, token: str, path: str) -> TopologyAwareMasterDataAliasError:
    return TopologyAwareMasterDataAliasError(
        code=POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID,
        detail=f"Malformed topology-aware master-data alias '{token}' at {path}.",
        field_or_table_path=path,
        diagnostic={"token": token},
    )


def _build_missing_role_error(
    *,
    token: str,
    path: str,
    participants: _TopologyEdgeParticipants,
    participant_side: str,
    required_role: str,
    organization_id: str,
    database_id: str,
    master_party_canonical_id: str,
) -> TopologyAwareMasterDataAliasError:
    return TopologyAwareMasterDataAliasError(
        code=MASTER_DATA_PARTY_ROLE_MISSING,
        detail="Bound Organization->Party mapping does not provide the required role for topology participant alias.",
        field_or_table_path=path,
        organization_id=organization_id,
        database_id=database_id,
        edge_ref=participants.edge_ref,
        participant_side=participant_side,
        required_role=required_role,
        diagnostic={
            "token": token,
            "master_party_canonical_id": master_party_canonical_id,
        },
    )


def _as_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
