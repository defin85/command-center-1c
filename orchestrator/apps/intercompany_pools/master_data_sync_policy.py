from __future__ import annotations

from dataclasses import dataclass

from apps.intercompany_pools.master_data_registry import normalize_pool_master_data_entity_type
from apps.intercompany_pools.models import PoolMasterDataSyncScope


MASTER_DATA_SYNC_POLICY_MISSING = "MASTER_DATA_SYNC_POLICY_MISSING"


@dataclass(frozen=True)
class PoolMasterDataSyncPolicyResolution:
    source: str  # database_scope | tenant_default | missing
    policy: str | None
    scope_id: str | None


class MasterDataSyncPolicyMissingError(ValueError):
    def __init__(self, *, tenant_id: str, entity_type: str, database_id: str | None) -> None:
        self.code = MASTER_DATA_SYNC_POLICY_MISSING
        self.tenant_id = str(tenant_id or "").strip()
        self.entity_type = str(entity_type or "").strip()
        self.database_id = str(database_id or "").strip()
        self.detail = (
            "Master-data sync policy is not configured for scope "
            f"tenant='{self.tenant_id}', entity='{self.entity_type}', "
            f"database='{self.database_id or '*'}'."
        )
        super().__init__(f"{self.code}: {self.detail}")

    def to_diagnostic(self) -> dict[str, str]:
        return {
            "error_code": self.code,
            "tenant_id": self.tenant_id,
            "entity_type": self.entity_type,
            "database_id": self.database_id,
        }


def _normalize_entity_type(entity_type: str) -> str:
    return normalize_pool_master_data_entity_type(entity_type)


def resolve_pool_master_data_sync_policy(
    *,
    tenant_id: str,
    entity_type: str,
    database_id: str | None = None,
) -> PoolMasterDataSyncPolicyResolution:
    normalized_entity_type = _normalize_entity_type(entity_type)
    normalized_tenant_id = str(tenant_id or "").strip()
    normalized_database_id = str(database_id or "").strip()

    scoped_queryset = PoolMasterDataSyncScope.objects.filter(
        tenant_id=normalized_tenant_id,
        entity_type=normalized_entity_type,
    )
    if normalized_database_id:
        row = (
            scoped_queryset.filter(database_id=normalized_database_id)
            .values("id", "policy")
            .first()
        )
        if row is not None:
            return PoolMasterDataSyncPolicyResolution(
                source="database_scope",
                policy=str(row["policy"]),
                scope_id=str(row["id"]),
            )

    default_row = (
        scoped_queryset.filter(database_id__isnull=True)
        .values("id", "policy")
        .first()
    )
    if default_row is not None:
        return PoolMasterDataSyncPolicyResolution(
            source="tenant_default",
            policy=str(default_row["policy"]),
            scope_id=str(default_row["id"]),
        )

    return PoolMasterDataSyncPolicyResolution(
        source="missing",
        policy=None,
        scope_id=None,
    )


def require_pool_master_data_sync_policy(
    *,
    tenant_id: str,
    entity_type: str,
    database_id: str | None = None,
) -> str:
    resolution = resolve_pool_master_data_sync_policy(
        tenant_id=tenant_id,
        entity_type=entity_type,
        database_id=database_id,
    )
    if resolution.policy is None:
        raise MasterDataSyncPolicyMissingError(
            tenant_id=tenant_id,
            entity_type=entity_type,
            database_id=database_id,
        )
    return resolution.policy
