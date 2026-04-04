from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
from apps.databases.models import Database
from apps.intercompany_pools.gl_account_sets_store import (
    GLAccountSetCanonicalConflictError,
    GLAccountSetMemberResolutionError,
    GLAccountSetNotFoundError,
    GLAccountSetStoreError,
    get_canonical_gl_account_set,
    list_canonical_gl_account_sets,
    publish_canonical_gl_account_set,
    upsert_canonical_gl_account_set,
)
from apps.intercompany_pools.master_data_canonical_upsert import MasterDataCanonicalUpsertError
from apps.intercompany_pools.master_data_canonical_upsert import upsert_pool_master_data_contract
from apps.intercompany_pools.master_data_canonical_upsert import upsert_pool_master_data_gl_account
from apps.intercompany_pools.master_data_canonical_upsert import upsert_pool_master_data_item
from apps.intercompany_pools.master_data_canonical_upsert import upsert_pool_master_data_party
from apps.intercompany_pools.master_data_canonical_upsert import upsert_pool_master_data_tax_profile
from apps.intercompany_pools.master_data_errors import MasterDataResolveError
from apps.intercompany_pools.master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
    POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
    inspect_pool_master_data_registry,
    get_pool_master_data_entity_types,
    supports_pool_master_data_capability,
)
from apps.intercompany_pools.master_data_bindings import upsert_pool_master_data_binding
from apps.intercompany_pools.master_data_sync_execution import trigger_pool_master_data_outbound_sync_job
from apps.intercompany_pools.models import (
    PoolMasterBindingSyncStatus,
    PoolMasterBindingCatalogKind,
    PoolMasterContract,
    PoolMasterDataBinding,
    PoolMasterGLAccount,
    PoolMasterItem,
    PoolMasterParty,
    PoolMasterTaxProfile,
)
from apps.tenancy.models import Tenant

from .intercompany_pools import _parse_limit, _problem, _resolve_tenant_id

logger = logging.getLogger(__name__)

_DIRECT_BINDING_ENTITY_CHOICES = get_pool_master_data_entity_types(
    capability=POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
)


def _parse_offset(raw: object | None, *, default: int = 0) -> int:
    try:
        value = int(raw if raw is not None else default)
    except (TypeError, ValueError):
        return default
    if value < 0:
        return 0
    return value


def _validation_problem(*, detail: str, errors: object | None = None) -> Response:
    return _problem(
        code="VALIDATION_ERROR",
        title="Validation Error",
        detail=detail,
        status_code=http_status.HTTP_400_BAD_REQUEST,
        errors=errors,
    )


def _serialize_party(party: PoolMasterParty) -> dict[str, Any]:
    return {
        "id": str(party.id),
        "tenant_id": str(party.tenant_id),
        "canonical_id": party.canonical_id,
        "name": party.name,
        "full_name": party.full_name,
        "inn": party.inn,
        "kpp": party.kpp,
        "is_our_organization": bool(party.is_our_organization),
        "is_counterparty": bool(party.is_counterparty),
        "metadata": party.metadata if isinstance(party.metadata, dict) else {},
        "created_at": party.created_at,
        "updated_at": party.updated_at,
    }


def _serialize_item(item: PoolMasterItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "tenant_id": str(item.tenant_id),
        "canonical_id": item.canonical_id,
        "name": item.name,
        "sku": item.sku,
        "unit": item.unit,
        "metadata": item.metadata if isinstance(item.metadata, dict) else {},
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _serialize_contract(contract: PoolMasterContract) -> dict[str, Any]:
    return {
        "id": str(contract.id),
        "tenant_id": str(contract.tenant_id),
        "canonical_id": contract.canonical_id,
        "name": contract.name,
        "owner_counterparty_id": str(contract.owner_counterparty_id),
        "owner_counterparty_canonical_id": str(contract.owner_counterparty.canonical_id),
        "number": contract.number,
        "date": contract.date,
        "metadata": contract.metadata if isinstance(contract.metadata, dict) else {},
        "created_at": contract.created_at,
        "updated_at": contract.updated_at,
    }


def _serialize_tax_profile(tax_profile: PoolMasterTaxProfile) -> dict[str, Any]:
    vat_rate = tax_profile.vat_rate
    vat_rate_number = float(vat_rate) if isinstance(vat_rate, Decimal) else vat_rate
    return {
        "id": str(tax_profile.id),
        "tenant_id": str(tax_profile.tenant_id),
        "canonical_id": tax_profile.canonical_id,
        "vat_rate": vat_rate_number,
        "vat_included": bool(tax_profile.vat_included),
        "vat_code": tax_profile.vat_code,
        "metadata": tax_profile.metadata if isinstance(tax_profile.metadata, dict) else {},
        "created_at": tax_profile.created_at,
        "updated_at": tax_profile.updated_at,
    }


def _serialize_gl_account(gl_account: PoolMasterGLAccount) -> dict[str, Any]:
    return {
        "id": str(gl_account.id),
        "tenant_id": str(gl_account.tenant_id),
        "canonical_id": gl_account.canonical_id,
        "code": gl_account.code,
        "name": gl_account.name,
        "chart_identity": gl_account.chart_identity,
        "config_name": gl_account.config_name,
        "config_version": gl_account.config_version,
        "metadata": gl_account.metadata if isinstance(gl_account.metadata, dict) else {},
        "created_at": gl_account.created_at,
        "updated_at": gl_account.updated_at,
    }


def _serialize_binding(binding: PoolMasterDataBinding) -> dict[str, Any]:
    return {
        "id": str(binding.id),
        "tenant_id": str(binding.tenant_id),
        "entity_type": binding.entity_type,
        "canonical_id": binding.canonical_id,
        "database_id": str(binding.database_id),
        "ib_ref_key": binding.ib_ref_key,
        "ib_catalog_kind": binding.ib_catalog_kind,
        "owner_counterparty_canonical_id": binding.owner_counterparty_canonical_id,
        "chart_identity": binding.chart_identity,
        "sync_status": binding.sync_status,
        "fingerprint": binding.fingerprint,
        "metadata": binding.metadata if isinstance(binding.metadata, dict) else {},
        "last_synced_at": binding.last_synced_at,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
    }


def _gl_account_set_store_problem(exc: GLAccountSetStoreError) -> Response:
    if isinstance(exc, GLAccountSetCanonicalConflictError):
        return _problem(
            code="MASTER_DATA_GL_ACCOUNT_SET_CANONICAL_CONFLICT",
            title="GLAccountSet Canonical Conflict",
            detail=str(exc),
            status_code=http_status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, GLAccountSetMemberResolutionError):
        return _problem(
            code="MASTER_DATA_GL_ACCOUNT_SET_MEMBERS_INVALID",
            title="GLAccountSet Members Invalid",
            detail=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=exc.errors,
        )
    return _validation_problem(detail=str(exc))


def _schedule_outbound_master_data_sync_job_trigger(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    canonical_id: str,
    origin_system: str,
    origin_event_id: str,
) -> None:
    def _trigger_after_commit() -> None:
        try:
            trigger_pool_master_data_outbound_sync_job(
                tenant_id=tenant_id,
                database_id=database_id,
                entity_type=entity_type,
                canonical_id=canonical_id,
                origin_system=origin_system,
                origin_event_id=origin_event_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Master-data outbound sync trigger failed",
                extra={
                    "tenant_id": tenant_id,
                    "database_id": database_id,
                    "entity_type": entity_type,
                    "canonical_id": canonical_id,
                    "origin_system": origin_system,
                    "origin_event_id": origin_event_id,
                    "error": str(exc),
                },
                exc_info=True,
            )

    transaction.on_commit(_trigger_after_commit)


class _MasterDataListBaseQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=50)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)


class MasterDataPartyListQuerySerializer(_MasterDataListBaseQuerySerializer):
    query = serializers.CharField(required=False, allow_blank=True)
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(
        required=False,
        choices=[PoolMasterBindingCatalogKind.ORGANIZATION, PoolMasterBindingCatalogKind.COUNTERPARTY],
    )


class MasterDataItemListQuerySerializer(_MasterDataListBaseQuerySerializer):
    query = serializers.CharField(required=False, allow_blank=True)
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    sku = serializers.CharField(required=False, allow_blank=True)


class MasterDataContractListQuerySerializer(_MasterDataListBaseQuerySerializer):
    query = serializers.CharField(required=False, allow_blank=True)
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    owner_counterparty_canonical_id = serializers.CharField(required=False, allow_blank=True)


class MasterDataTaxProfileListQuerySerializer(_MasterDataListBaseQuerySerializer):
    query = serializers.CharField(required=False, allow_blank=True)
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    vat_code = serializers.CharField(required=False, allow_blank=True)


class MasterDataGLAccountListQuerySerializer(_MasterDataListBaseQuerySerializer):
    query = serializers.CharField(required=False, allow_blank=True)
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)
    chart_identity = serializers.CharField(required=False, allow_blank=True)
    config_name = serializers.CharField(required=False, allow_blank=True)
    config_version = serializers.CharField(required=False, allow_blank=True)


class MasterDataGLAccountSetListQuerySerializer(_MasterDataListBaseQuerySerializer):
    query = serializers.CharField(required=False, allow_blank=True)
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    chart_identity = serializers.CharField(required=False, allow_blank=True)
    config_name = serializers.CharField(required=False, allow_blank=True)
    config_version = serializers.CharField(required=False, allow_blank=True)


class MasterDataBindingListQuerySerializer(_MasterDataListBaseQuerySerializer):
    entity_type = serializers.ChoiceField(required=False, choices=_DIRECT_BINDING_ENTITY_CHOICES)
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    database_id = serializers.UUIDField(required=False)
    ib_catalog_kind = serializers.ChoiceField(
        required=False,
        choices=[PoolMasterBindingCatalogKind.ORGANIZATION, PoolMasterBindingCatalogKind.COUNTERPARTY],
    )
    owner_counterparty_canonical_id = serializers.CharField(required=False, allow_blank=True)
    chart_identity = serializers.CharField(required=False, allow_blank=True)
    sync_status = serializers.ChoiceField(required=False, choices=PoolMasterBindingSyncStatus.values)


class PoolMasterDataPartySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    canonical_id = serializers.CharField()
    name = serializers.CharField()
    full_name = serializers.CharField(required=False, allow_blank=True)
    inn = serializers.CharField(required=False, allow_blank=True)
    kpp = serializers.CharField(required=False, allow_blank=True)
    is_our_organization = serializers.BooleanField()
    is_counterparty = serializers.BooleanField()
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class PoolMasterDataPartyListResponseSerializer(serializers.Serializer):
    parties = PoolMasterDataPartySerializer(many=True)
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()


class PoolMasterDataPartyDetailResponseSerializer(serializers.Serializer):
    party = PoolMasterDataPartySerializer()


class PoolMasterDataPartyUpsertRequestSerializer(serializers.Serializer):
    party_id = serializers.UUIDField(required=False)
    canonical_id = serializers.CharField(max_length=128)
    name = serializers.CharField(max_length=255)
    full_name = serializers.CharField(required=False, allow_blank=True, default="")
    inn = serializers.CharField(required=False, allow_blank=True, default="")
    kpp = serializers.CharField(required=False, allow_blank=True, default="")
    is_our_organization = serializers.BooleanField(required=False, default=False)
    is_counterparty = serializers.BooleanField(required=False, default=True)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class PoolMasterDataPartyUpsertResponseSerializer(serializers.Serializer):
    party = PoolMasterDataPartySerializer()
    created = serializers.BooleanField()


class PoolMasterDataItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    canonical_id = serializers.CharField()
    name = serializers.CharField()
    sku = serializers.CharField(required=False, allow_blank=True)
    unit = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class PoolMasterDataItemListResponseSerializer(serializers.Serializer):
    items = PoolMasterDataItemSerializer(many=True)
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()


class PoolMasterDataItemDetailResponseSerializer(serializers.Serializer):
    item = PoolMasterDataItemSerializer()


class PoolMasterDataItemUpsertRequestSerializer(serializers.Serializer):
    item_id = serializers.UUIDField(required=False)
    canonical_id = serializers.CharField(max_length=128)
    name = serializers.CharField(max_length=255)
    sku = serializers.CharField(required=False, allow_blank=True, default="")
    unit = serializers.CharField(required=False, allow_blank=True, default="")
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class PoolMasterDataItemUpsertResponseSerializer(serializers.Serializer):
    item = PoolMasterDataItemSerializer()
    created = serializers.BooleanField()


class PoolMasterDataContractSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    canonical_id = serializers.CharField()
    name = serializers.CharField()
    owner_counterparty_id = serializers.UUIDField()
    owner_counterparty_canonical_id = serializers.CharField()
    number = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class PoolMasterDataContractListResponseSerializer(serializers.Serializer):
    contracts = PoolMasterDataContractSerializer(many=True)
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()


class PoolMasterDataContractDetailResponseSerializer(serializers.Serializer):
    contract = PoolMasterDataContractSerializer()


class PoolMasterDataContractUpsertRequestSerializer(serializers.Serializer):
    contract_id = serializers.UUIDField(required=False)
    canonical_id = serializers.CharField(max_length=128)
    name = serializers.CharField(max_length=255)
    owner_counterparty_id = serializers.UUIDField()
    number = serializers.CharField(required=False, allow_blank=True, default="")
    date = serializers.DateField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class PoolMasterDataContractUpsertResponseSerializer(serializers.Serializer):
    contract = PoolMasterDataContractSerializer()
    created = serializers.BooleanField()


class PoolMasterDataTaxProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    canonical_id = serializers.CharField()
    vat_rate = serializers.FloatField()
    vat_included = serializers.BooleanField()
    vat_code = serializers.CharField()
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class PoolMasterDataTaxProfileListResponseSerializer(serializers.Serializer):
    tax_profiles = PoolMasterDataTaxProfileSerializer(many=True)
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()


class PoolMasterDataTaxProfileDetailResponseSerializer(serializers.Serializer):
    tax_profile = PoolMasterDataTaxProfileSerializer()


class PoolMasterDataTaxProfileUpsertRequestSerializer(serializers.Serializer):
    tax_profile_id = serializers.UUIDField(required=False)
    canonical_id = serializers.CharField(max_length=128)
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    vat_included = serializers.BooleanField()
    vat_code = serializers.CharField(max_length=64)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class PoolMasterDataTaxProfileUpsertResponseSerializer(serializers.Serializer):
    tax_profile = PoolMasterDataTaxProfileSerializer()
    created = serializers.BooleanField()


class PoolMasterDataGLAccountSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    canonical_id = serializers.CharField()
    code = serializers.CharField()
    name = serializers.CharField()
    chart_identity = serializers.CharField()
    config_name = serializers.CharField()
    config_version = serializers.CharField()
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class PoolMasterDataGLAccountListResponseSerializer(serializers.Serializer):
    gl_accounts = PoolMasterDataGLAccountSerializer(many=True)
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()


class PoolMasterDataGLAccountDetailResponseSerializer(serializers.Serializer):
    gl_account = PoolMasterDataGLAccountSerializer()


class PoolMasterDataGLAccountUpsertRequestSerializer(serializers.Serializer):
    gl_account_id = serializers.UUIDField(required=False)
    canonical_id = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=128)
    name = serializers.CharField(max_length=255)
    chart_identity = serializers.CharField(max_length=255)
    config_name = serializers.CharField(max_length=255)
    config_version = serializers.CharField(max_length=128)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class PoolMasterDataGLAccountUpsertResponseSerializer(serializers.Serializer):
    gl_account = PoolMasterDataGLAccountSerializer()
    created = serializers.BooleanField()


class PoolMasterDataGLAccountSetMemberWriteSerializer(serializers.Serializer):
    canonical_id = serializers.CharField(max_length=128)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class PoolMasterDataGLAccountSetMemberReadSerializer(serializers.Serializer):
    gl_account_id = serializers.UUIDField()
    canonical_id = serializers.CharField()
    code = serializers.CharField()
    name = serializers.CharField()
    chart_identity = serializers.CharField()
    config_name = serializers.CharField(required=False)
    config_version = serializers.CharField(required=False)
    sort_order = serializers.IntegerField(min_value=0)
    metadata = serializers.JSONField(required=False)


class PoolMasterDataGLAccountSetRevisionSerializer(serializers.Serializer):
    gl_account_set_revision_id = serializers.CharField()
    gl_account_set_id = serializers.UUIDField()
    contract_version = serializers.CharField()
    revision_number = serializers.IntegerField(min_value=1)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    chart_identity = serializers.CharField()
    config_name = serializers.CharField()
    config_version = serializers.CharField()
    members = PoolMasterDataGLAccountSetMemberReadSerializer(many=True)
    metadata = serializers.JSONField(required=False)
    created_by = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField()


class PoolMasterDataGLAccountSetSummarySerializer(serializers.Serializer):
    gl_account_set_id = serializers.UUIDField()
    canonical_id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    chart_identity = serializers.CharField()
    config_name = serializers.CharField()
    config_version = serializers.CharField()
    draft_members_count = serializers.IntegerField(min_value=0)
    published_revision_number = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    published_revision_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class PoolMasterDataGLAccountSetDetailSerializer(PoolMasterDataGLAccountSetSummarySerializer):
    draft_members = PoolMasterDataGLAccountSetMemberReadSerializer(many=True)
    revisions = PoolMasterDataGLAccountSetRevisionSerializer(many=True)
    published_revision = PoolMasterDataGLAccountSetRevisionSerializer(required=False, allow_null=True)


class PoolMasterDataGLAccountSetListResponseSerializer(serializers.Serializer):
    gl_account_sets = PoolMasterDataGLAccountSetSummarySerializer(many=True)
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()


class PoolMasterDataGLAccountSetDetailResponseSerializer(serializers.Serializer):
    gl_account_set = PoolMasterDataGLAccountSetDetailSerializer()


class PoolMasterDataGLAccountSetUpsertRequestSerializer(serializers.Serializer):
    gl_account_set_id = serializers.UUIDField(required=False)
    canonical_id = serializers.CharField(max_length=128)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    chart_identity = serializers.CharField(max_length=255)
    config_name = serializers.CharField(max_length=255)
    config_version = serializers.CharField(max_length=128)
    members = PoolMasterDataGLAccountSetMemberWriteSerializer(many=True, required=False, default=list)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class PoolMasterDataGLAccountSetMutationResponseSerializer(serializers.Serializer):
    gl_account_set = PoolMasterDataGLAccountSetDetailSerializer()
    created = serializers.BooleanField(required=False)


class PoolMasterDataBindingSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    entity_type = serializers.CharField()
    canonical_id = serializers.CharField()
    database_id = serializers.UUIDField()
    ib_ref_key = serializers.CharField()
    ib_catalog_kind = serializers.CharField(required=False, allow_blank=True)
    owner_counterparty_canonical_id = serializers.CharField(required=False, allow_blank=True)
    chart_identity = serializers.CharField(required=False, allow_blank=True)
    sync_status = serializers.CharField()
    fingerprint = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)
    last_synced_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class PoolMasterDataBindingListResponseSerializer(serializers.Serializer):
    bindings = PoolMasterDataBindingSerializer(many=True)
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()


class PoolMasterDataBindingDetailResponseSerializer(serializers.Serializer):
    binding = PoolMasterDataBindingSerializer()


class PoolMasterDataBindingUpsertRequestSerializer(serializers.Serializer):
    binding_id = serializers.UUIDField(required=False)
    entity_type = serializers.ChoiceField(choices=_DIRECT_BINDING_ENTITY_CHOICES)
    canonical_id = serializers.CharField(max_length=128)
    database_id = serializers.UUIDField()
    ib_ref_key = serializers.CharField(max_length=128)
    ib_catalog_kind = serializers.CharField(required=False, allow_blank=True, default="")
    owner_counterparty_canonical_id = serializers.CharField(required=False, allow_blank=True, default="")
    chart_identity = serializers.CharField(required=False, allow_blank=True, default="")
    sync_status = serializers.ChoiceField(
        required=False,
        default=PoolMasterBindingSyncStatus.RESOLVED,
        choices=PoolMasterBindingSyncStatus.values,
    )
    fingerprint = serializers.CharField(required=False, allow_blank=True, default="")
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class PoolMasterDataBindingUpsertResponseSerializer(serializers.Serializer):
    binding = PoolMasterDataBindingSerializer()
    created = serializers.BooleanField()


class PoolMasterDataRegistryCapabilitiesSerializer(serializers.Serializer):
    direct_binding = serializers.BooleanField()
    token_exposure = serializers.BooleanField()
    bootstrap_import = serializers.BooleanField()
    outbox_fanout = serializers.BooleanField()
    sync_outbound = serializers.BooleanField()
    sync_inbound = serializers.BooleanField()
    sync_reconcile = serializers.BooleanField()


class PoolMasterDataRegistryTokenContractSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    qualifier_kind = serializers.CharField()
    qualifier_required = serializers.BooleanField()
    qualifier_options = serializers.ListField(child=serializers.CharField())


class PoolMasterDataRegistryBootstrapContractSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    dependency_order = serializers.IntegerField(required=False, allow_null=True)


class PoolMasterDataRegistryEntrySerializer(serializers.Serializer):
    entity_type = serializers.CharField()
    label = serializers.CharField()
    kind = serializers.CharField()
    display_order = serializers.IntegerField(min_value=0)
    binding_scope_fields = serializers.ListField(child=serializers.CharField())
    capabilities = PoolMasterDataRegistryCapabilitiesSerializer()
    token_contract = PoolMasterDataRegistryTokenContractSerializer()
    bootstrap_contract = PoolMasterDataRegistryBootstrapContractSerializer()
    runtime_consumers = serializers.ListField(child=serializers.CharField())


class PoolMasterDataRegistryInspectResponseSerializer(serializers.Serializer):
    contract_version = serializers.CharField()
    entries = PoolMasterDataRegistryEntrySerializer(many=True)
    count = serializers.IntegerField(min_value=0)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_registry_retrieve",
    summary="Inspect master-data reusable registry",
    responses={
        200: PoolMasterDataRegistryInspectResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inspect_master_data_registry(request):
    return Response(inspect_pool_master_data_registry(), status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_parties_list",
    summary="List master-data parties",
    parameters=[MasterDataPartyListQuerySerializer],
    responses={
        200: PoolMasterDataPartyListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_parties(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    query_serializer = MasterDataPartyListQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(
            detail="Invalid query parameters.",
            errors=query_serializer.errors,
        )
    params = query_serializer.validated_data
    limit = _parse_limit(params.get("limit"), default=50, max_value=200)
    offset = _parse_offset(params.get("offset"), default=0)

    queryset = PoolMasterParty.objects.filter(tenant_id=tenant_id)
    query = str(params.get("query") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(canonical_id__icontains=query)
            | Q(name__icontains=query)
            | Q(full_name__icontains=query)
            | Q(inn__icontains=query)
            | Q(kpp__icontains=query)
        )
    canonical_id = str(params.get("canonical_id") or "").strip()
    if canonical_id:
        queryset = queryset.filter(canonical_id=canonical_id)
    role = str(params.get("role") or "").strip()
    if role == PoolMasterBindingCatalogKind.ORGANIZATION:
        queryset = queryset.filter(is_our_organization=True)
    elif role == PoolMasterBindingCatalogKind.COUNTERPARTY:
        queryset = queryset.filter(is_counterparty=True)

    count = queryset.count()
    parties = list(queryset.order_by("name", "canonical_id")[offset : offset + limit])
    return Response(
        {
            "parties": [_serialize_party(party) for party in parties],
            "count": count,
            "limit": limit,
            "offset": offset,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_parties_get",
    summary="Get master-data party by id",
    responses={
        200: PoolMasterDataPartyDetailResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_master_data_party(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    party = PoolMasterParty.objects.filter(id=id, tenant_id=tenant_id).first()
    if party is None:
        return _problem(
            code="MASTER_DATA_PARTY_NOT_FOUND",
            title="Master Data Party Not Found",
            detail="Party not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return Response({"party": _serialize_party(party)}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_parties_upsert",
    summary="Create or update master-data party",
    request=PoolMasterDataPartyUpsertRequestSerializer,
    responses={
        200: PoolMasterDataPartyUpsertResponseSerializer,
        201: PoolMasterDataPartyUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_master_data_party(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = PoolMasterDataPartyUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(
            detail="Party payload validation failed.",
            errors=serializer.errors,
        )
    data = serializer.validated_data

    party = None
    party_id = data.get("party_id")
    if party_id is not None:
        party = PoolMasterParty.objects.filter(id=party_id, tenant_id=tenant_id).first()
        if party is None:
            return _problem(
                code="MASTER_DATA_PARTY_NOT_FOUND",
                title="Master Data Party Not Found",
                detail="Party not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    try:
        result = upsert_pool_master_data_party(
            tenant_id=tenant_id,
            canonical_id=str(data["canonical_id"]),
            name=str(data["name"]),
            full_name=str(data.get("full_name", "")),
            inn=str(data.get("inn", "")),
            kpp=str(data.get("kpp", "")),
            is_our_organization=bool(data.get("is_our_organization", False)),
            is_counterparty=bool(data.get("is_counterparty", True)),
            metadata=dict(data.get("metadata", {})),
            existing=party,
            origin_system="cc",
        )
        party = result.entity
        created = bool(result.created)
    except DjangoValidationError as exc:
        return _validation_problem(
            detail="Party payload validation failed.",
            errors=exc.message_dict if hasattr(exc, "message_dict") else str(exc),
        )
    except IntegrityError:
        return _problem(
            code="MASTER_DATA_PARTY_CANONICAL_CONFLICT",
            title="Master Data Party Canonical Conflict",
            detail="Party with this canonical_id already exists in tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response({"party": _serialize_party(party), "created": created}, status=response_status)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_items_list",
    summary="List master-data items",
    parameters=[MasterDataItemListQuerySerializer],
    responses={
        200: PoolMasterDataItemListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_items(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    query_serializer = MasterDataItemListQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)
    params = query_serializer.validated_data
    limit = _parse_limit(params.get("limit"), default=50, max_value=200)
    offset = _parse_offset(params.get("offset"), default=0)

    queryset = PoolMasterItem.objects.filter(tenant_id=tenant_id)
    query = str(params.get("query") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(canonical_id__icontains=query)
            | Q(name__icontains=query)
            | Q(sku__icontains=query)
        )
    canonical_id = str(params.get("canonical_id") or "").strip()
    if canonical_id:
        queryset = queryset.filter(canonical_id=canonical_id)
    sku = str(params.get("sku") or "").strip()
    if sku:
        queryset = queryset.filter(sku__icontains=sku)

    count = queryset.count()
    items = list(queryset.order_by("name", "canonical_id")[offset : offset + limit])
    return Response(
        {
            "items": [_serialize_item(item) for item in items],
            "count": count,
            "limit": limit,
            "offset": offset,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_items_get",
    summary="Get master-data item by id",
    responses={
        200: PoolMasterDataItemDetailResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_master_data_item(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    item = PoolMasterItem.objects.filter(id=id, tenant_id=tenant_id).first()
    if item is None:
        return _problem(
            code="MASTER_DATA_ITEM_NOT_FOUND",
            title="Master Data Item Not Found",
            detail="Item not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return Response({"item": _serialize_item(item)}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_items_upsert",
    summary="Create or update master-data item",
    request=PoolMasterDataItemUpsertRequestSerializer,
    responses={
        200: PoolMasterDataItemUpsertResponseSerializer,
        201: PoolMasterDataItemUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_master_data_item(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = PoolMasterDataItemUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="Item payload validation failed.", errors=serializer.errors)
    data = serializer.validated_data

    item = None
    item_id = data.get("item_id")
    if item_id is not None:
        item = PoolMasterItem.objects.filter(id=item_id, tenant_id=tenant_id).first()
        if item is None:
            return _problem(
                code="MASTER_DATA_ITEM_NOT_FOUND",
                title="Master Data Item Not Found",
                detail="Item not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    try:
        result = upsert_pool_master_data_item(
            tenant_id=tenant_id,
            canonical_id=str(data["canonical_id"]),
            name=str(data["name"]),
            sku=str(data.get("sku", "")),
            unit=str(data.get("unit", "")),
            metadata=dict(data.get("metadata", {})),
            existing=item,
            origin_system="cc",
        )
        item = result.entity
        created = bool(result.created)
    except DjangoValidationError as exc:
        return _validation_problem(
            detail="Item payload validation failed.",
            errors=exc.message_dict if hasattr(exc, "message_dict") else str(exc),
        )
    except IntegrityError:
        return _problem(
            code="MASTER_DATA_ITEM_CANONICAL_CONFLICT",
            title="Master Data Item Canonical Conflict",
            detail="Item with this canonical_id already exists in tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response({"item": _serialize_item(item), "created": created}, status=response_status)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_contracts_list",
    summary="List master-data contracts",
    parameters=[MasterDataContractListQuerySerializer],
    responses={
        200: PoolMasterDataContractListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_contracts(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    query_serializer = MasterDataContractListQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)
    params = query_serializer.validated_data
    limit = _parse_limit(params.get("limit"), default=50, max_value=200)
    offset = _parse_offset(params.get("offset"), default=0)

    queryset = PoolMasterContract.objects.filter(tenant_id=tenant_id).select_related("owner_counterparty")
    query = str(params.get("query") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(canonical_id__icontains=query)
            | Q(name__icontains=query)
            | Q(number__icontains=query)
        )
    canonical_id = str(params.get("canonical_id") or "").strip()
    if canonical_id:
        queryset = queryset.filter(canonical_id=canonical_id)
    owner_counterparty_canonical_id = str(params.get("owner_counterparty_canonical_id") or "").strip()
    if owner_counterparty_canonical_id:
        queryset = queryset.filter(owner_counterparty__canonical_id=owner_counterparty_canonical_id)

    count = queryset.count()
    contracts = list(queryset.order_by("name", "canonical_id")[offset : offset + limit])
    return Response(
        {
            "contracts": [_serialize_contract(contract) for contract in contracts],
            "count": count,
            "limit": limit,
            "offset": offset,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_contracts_get",
    summary="Get master-data contract by id",
    responses={
        200: PoolMasterDataContractDetailResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_master_data_contract(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    contract = PoolMasterContract.objects.filter(id=id, tenant_id=tenant_id).select_related("owner_counterparty").first()
    if contract is None:
        return _problem(
            code="MASTER_DATA_CONTRACT_NOT_FOUND",
            title="Master Data Contract Not Found",
            detail="Contract not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return Response({"contract": _serialize_contract(contract)}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_contracts_upsert",
    summary="Create or update master-data contract",
    request=PoolMasterDataContractUpsertRequestSerializer,
    responses={
        200: PoolMasterDataContractUpsertResponseSerializer,
        201: PoolMasterDataContractUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_master_data_contract(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = PoolMasterDataContractUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="Contract payload validation failed.", errors=serializer.errors)
    data = serializer.validated_data

    owner_counterparty = PoolMasterParty.objects.filter(id=data["owner_counterparty_id"], tenant_id=tenant_id).first()
    if owner_counterparty is None:
        return _problem(
            code="MASTER_DATA_OWNER_COUNTERPARTY_NOT_FOUND",
            title="Owner Counterparty Not Found",
            detail="Owner counterparty not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    if not owner_counterparty.is_counterparty:
        return _problem(
            code="MASTER_DATA_OWNER_COUNTERPARTY_ROLE_INVALID",
            title="Owner Counterparty Role Invalid",
            detail="Owner counterparty must have counterparty role.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    contract = None
    contract_id = data.get("contract_id")
    if contract_id is not None:
        contract = (
            PoolMasterContract.objects.filter(id=contract_id, tenant_id=tenant_id)
            .select_related("owner_counterparty")
            .first()
        )
        if contract is None:
            return _problem(
                code="MASTER_DATA_CONTRACT_NOT_FOUND",
                title="Master Data Contract Not Found",
                detail="Contract not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    try:
        result = upsert_pool_master_data_contract(
            tenant_id=tenant_id,
            canonical_id=str(data["canonical_id"]),
            name=str(data["name"]),
            owner_counterparty=owner_counterparty,
            number=str(data.get("number", "")),
            date=data.get("date"),
            metadata=dict(data.get("metadata", {})),
            existing=contract,
            origin_system="cc",
        )
        contract = result.entity
        created = bool(result.created)
    except MasterDataCanonicalUpsertError as exc:
        return _problem(
            code=str(exc.code),
            title="Master Data Contract Upsert Failed",
            detail=str(exc.detail),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )
    except DjangoValidationError as exc:
        return _validation_problem(
            detail="Contract payload validation failed.",
            errors=exc.message_dict if hasattr(exc, "message_dict") else str(exc),
        )
    except IntegrityError:
        return _problem(
            code="MASTER_DATA_CONTRACT_SCOPE_CONFLICT",
            title="Master Data Contract Scope Conflict",
            detail="Contract with this canonical_id and owner counterparty already exists in tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    contract = PoolMasterContract.objects.select_related("owner_counterparty").get(id=contract.id)
    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response({"contract": _serialize_contract(contract), "created": created}, status=response_status)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_tax_profiles_list",
    summary="List master-data tax profiles",
    parameters=[MasterDataTaxProfileListQuerySerializer],
    responses={
        200: PoolMasterDataTaxProfileListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_tax_profiles(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    query_serializer = MasterDataTaxProfileListQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)
    params = query_serializer.validated_data
    limit = _parse_limit(params.get("limit"), default=50, max_value=200)
    offset = _parse_offset(params.get("offset"), default=0)

    queryset = PoolMasterTaxProfile.objects.filter(tenant_id=tenant_id)
    query = str(params.get("query") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(canonical_id__icontains=query)
            | Q(vat_code__icontains=query)
        )
    canonical_id = str(params.get("canonical_id") or "").strip()
    if canonical_id:
        queryset = queryset.filter(canonical_id=canonical_id)
    vat_code = str(params.get("vat_code") or "").strip()
    if vat_code:
        queryset = queryset.filter(vat_code__icontains=vat_code)

    count = queryset.count()
    tax_profiles = list(queryset.order_by("canonical_id")[offset : offset + limit])
    return Response(
        {
            "tax_profiles": [_serialize_tax_profile(tax_profile) for tax_profile in tax_profiles],
            "count": count,
            "limit": limit,
            "offset": offset,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_tax_profiles_get",
    summary="Get master-data tax profile by id",
    responses={
        200: PoolMasterDataTaxProfileDetailResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_master_data_tax_profile(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    tax_profile = PoolMasterTaxProfile.objects.filter(id=id, tenant_id=tenant_id).first()
    if tax_profile is None:
        return _problem(
            code="MASTER_DATA_TAX_PROFILE_NOT_FOUND",
            title="Master Data Tax Profile Not Found",
            detail="Tax profile not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return Response({"tax_profile": _serialize_tax_profile(tax_profile)}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_tax_profiles_upsert",
    summary="Create or update master-data tax profile",
    request=PoolMasterDataTaxProfileUpsertRequestSerializer,
    responses={
        200: PoolMasterDataTaxProfileUpsertResponseSerializer,
        201: PoolMasterDataTaxProfileUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_master_data_tax_profile(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = PoolMasterDataTaxProfileUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="Tax profile payload validation failed.", errors=serializer.errors)
    data = serializer.validated_data

    tax_profile = None
    tax_profile_id = data.get("tax_profile_id")
    if tax_profile_id is not None:
        tax_profile = PoolMasterTaxProfile.objects.filter(id=tax_profile_id, tenant_id=tenant_id).first()
        if tax_profile is None:
            return _problem(
                code="MASTER_DATA_TAX_PROFILE_NOT_FOUND",
                title="Master Data Tax Profile Not Found",
                detail="Tax profile not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    try:
        result = upsert_pool_master_data_tax_profile(
            tenant_id=tenant_id,
            canonical_id=str(data["canonical_id"]),
            vat_rate=data["vat_rate"],
            vat_included=bool(data["vat_included"]),
            vat_code=str(data["vat_code"]),
            metadata=dict(data.get("metadata", {})),
            existing=tax_profile,
            origin_system="cc",
        )
        tax_profile = result.entity
        created = bool(result.created)
    except DjangoValidationError as exc:
        return _validation_problem(
            detail="Tax profile payload validation failed.",
            errors=exc.message_dict if hasattr(exc, "message_dict") else str(exc),
        )
    except IntegrityError:
        return _problem(
            code="MASTER_DATA_TAX_PROFILE_CANONICAL_CONFLICT",
            title="Master Data Tax Profile Canonical Conflict",
            detail="Tax profile with this canonical_id already exists in tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response({"tax_profile": _serialize_tax_profile(tax_profile), "created": created}, status=response_status)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_gl_accounts_list",
    summary="List master-data GL accounts",
    parameters=[MasterDataGLAccountListQuerySerializer],
    responses={
        200: PoolMasterDataGLAccountListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_gl_accounts(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    query_serializer = MasterDataGLAccountListQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)
    params = query_serializer.validated_data
    limit = _parse_limit(params.get("limit"), default=50, max_value=200)
    offset = _parse_offset(params.get("offset"), default=0)

    queryset = PoolMasterGLAccount.objects.filter(tenant_id=tenant_id)
    query = str(params.get("query") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(canonical_id__icontains=query)
            | Q(code__icontains=query)
            | Q(name__icontains=query)
            | Q(chart_identity__icontains=query)
        )
    canonical_id = str(params.get("canonical_id") or "").strip()
    if canonical_id:
        queryset = queryset.filter(canonical_id=canonical_id)
    code = str(params.get("code") or "").strip()
    if code:
        queryset = queryset.filter(code__icontains=code)
    chart_identity = str(params.get("chart_identity") or "").strip()
    if chart_identity:
        queryset = queryset.filter(chart_identity=chart_identity)
    config_name = str(params.get("config_name") or "").strip()
    if config_name:
        queryset = queryset.filter(config_name=config_name)
    config_version = str(params.get("config_version") or "").strip()
    if config_version:
        queryset = queryset.filter(config_version=config_version)

    count = queryset.count()
    gl_accounts = list(queryset.order_by("code", "canonical_id")[offset : offset + limit])
    return Response(
        {
            "gl_accounts": [_serialize_gl_account(gl_account) for gl_account in gl_accounts],
            "count": count,
            "limit": limit,
            "offset": offset,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_gl_accounts_get",
    summary="Get master-data GL account by id",
    responses={
        200: PoolMasterDataGLAccountDetailResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_master_data_gl_account(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    gl_account = PoolMasterGLAccount.objects.filter(id=id, tenant_id=tenant_id).first()
    if gl_account is None:
        return _problem(
            code="MASTER_DATA_GL_ACCOUNT_NOT_FOUND",
            title="Master Data GL Account Not Found",
            detail="GL account not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return Response({"gl_account": _serialize_gl_account(gl_account)}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_gl_accounts_upsert",
    summary="Create or update master-data GL account",
    request=PoolMasterDataGLAccountUpsertRequestSerializer,
    responses={
        200: PoolMasterDataGLAccountUpsertResponseSerializer,
        201: PoolMasterDataGLAccountUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_master_data_gl_account(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = PoolMasterDataGLAccountUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="GL account payload validation failed.", errors=serializer.errors)
    data = serializer.validated_data

    gl_account = None
    gl_account_id = data.get("gl_account_id")
    if gl_account_id is not None:
        gl_account = PoolMasterGLAccount.objects.filter(id=gl_account_id, tenant_id=tenant_id).first()
        if gl_account is None:
            return _problem(
                code="MASTER_DATA_GL_ACCOUNT_NOT_FOUND",
                title="Master Data GL Account Not Found",
                detail="GL account not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    try:
        result = upsert_pool_master_data_gl_account(
            tenant_id=tenant_id,
            canonical_id=str(data["canonical_id"]),
            code=str(data["code"]),
            name=str(data["name"]),
            chart_identity=str(data["chart_identity"]),
            config_name=str(data["config_name"]),
            config_version=str(data["config_version"]),
            metadata=dict(data.get("metadata", {})),
            existing=gl_account,
            origin_system="cc",
        )
        gl_account = result.entity
        created = bool(result.created)
    except DjangoValidationError as exc:
        return _validation_problem(
            detail="GL account payload validation failed.",
            errors=exc.message_dict if hasattr(exc, "message_dict") else str(exc),
        )
    except IntegrityError:
        return _problem(
            code="MASTER_DATA_GL_ACCOUNT_CANONICAL_CONFLICT",
            title="Master Data GL Account Canonical Conflict",
            detail="GL account with this canonical_id already exists in tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response(
        {"gl_account": _serialize_gl_account(gl_account), "created": created},
        status=response_status,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_gl_account_sets_list",
    summary="List reusable GL account sets",
    parameters=[MasterDataGLAccountSetListQuerySerializer],
    responses={
        200: PoolMasterDataGLAccountSetListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_gl_account_sets(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    query_serializer = MasterDataGLAccountSetListQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)
    params = query_serializer.validated_data
    limit = _parse_limit(params.get("limit"), default=50, max_value=200)
    offset = _parse_offset(params.get("offset"), default=0)

    gl_account_sets = list_canonical_gl_account_sets(tenant=tenant)
    query = str(params.get("query") or "").strip().lower()
    canonical_id = str(params.get("canonical_id") or "").strip()
    chart_identity = str(params.get("chart_identity") or "").strip()
    config_name = str(params.get("config_name") or "").strip()
    config_version = str(params.get("config_version") or "").strip()

    filtered = []
    for item in gl_account_sets:
        if canonical_id and str(item.get("canonical_id") or "") != canonical_id:
            continue
        if chart_identity and str(item.get("chart_identity") or "") != chart_identity:
            continue
        if config_name and str(item.get("config_name") or "") != config_name:
            continue
        if config_version and str(item.get("config_version") or "") != config_version:
            continue
        if query:
            haystack = " ".join(
                [
                    str(item.get("canonical_id") or ""),
                    str(item.get("name") or ""),
                    str(item.get("description") or ""),
                    str(item.get("chart_identity") or ""),
                ]
            ).lower()
            if query not in haystack:
                continue
        filtered.append(item)

    count = len(filtered)
    page = filtered[offset : offset + limit]
    return Response(
        {
            "gl_account_sets": page,
            "count": count,
            "limit": limit,
            "offset": offset,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_gl_account_sets_get",
    summary="Get reusable GL account set detail",
    responses={
        200: PoolMasterDataGLAccountSetDetailResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_master_data_gl_account_set(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    try:
        gl_account_set = get_canonical_gl_account_set(tenant=tenant, gl_account_set_id=str(id))
    except GLAccountSetNotFoundError:
        return _problem(
            code="MASTER_DATA_GL_ACCOUNT_SET_NOT_FOUND",
            title="GLAccountSet Not Found",
            detail="GLAccountSet not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except GLAccountSetStoreError as exc:
        return _gl_account_set_store_problem(exc)
    return Response({"gl_account_set": gl_account_set}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_gl_account_sets_upsert",
    summary="Create or update reusable GL account set draft",
    request=PoolMasterDataGLAccountSetUpsertRequestSerializer,
    responses={
        200: PoolMasterDataGLAccountSetMutationResponseSerializer,
        201: PoolMasterDataGLAccountSetMutationResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_master_data_gl_account_set(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    serializer = PoolMasterDataGLAccountSetUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="GLAccountSet payload validation failed.", errors=serializer.errors)
    try:
        gl_account_set, created = upsert_canonical_gl_account_set(
            tenant=tenant,
            gl_account_set=dict(serializer.validated_data),
            actor_username=request.user.username if request.user and request.user.is_authenticated else "",
        )
    except GLAccountSetNotFoundError:
        return _problem(
            code="MASTER_DATA_GL_ACCOUNT_SET_NOT_FOUND",
            title="GLAccountSet Not Found",
            detail="GLAccountSet not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except GLAccountSetStoreError as exc:
        return _gl_account_set_store_problem(exc)

    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response(
        {"gl_account_set": gl_account_set, "created": created},
        status=response_status,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_gl_account_sets_publish",
    summary="Publish immutable GL account set revision",
    request=None,
    responses={
        200: PoolMasterDataGLAccountSetMutationResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def publish_master_data_gl_account_set(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    try:
        gl_account_set = publish_canonical_gl_account_set(
            tenant=tenant,
            gl_account_set_id=str(id),
            actor_username=request.user.username if request.user and request.user.is_authenticated else "",
        )
    except GLAccountSetNotFoundError:
        return _problem(
            code="MASTER_DATA_GL_ACCOUNT_SET_NOT_FOUND",
            title="GLAccountSet Not Found",
            detail="GLAccountSet not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except GLAccountSetStoreError as exc:
        return _gl_account_set_store_problem(exc)
    return Response({"gl_account_set": gl_account_set}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bindings_list",
    summary="List master-data bindings",
    parameters=[MasterDataBindingListQuerySerializer],
    responses={
        200: PoolMasterDataBindingListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_bindings(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    query_serializer = MasterDataBindingListQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)
    params = query_serializer.validated_data
    limit = _parse_limit(params.get("limit"), default=50, max_value=200)
    offset = _parse_offset(params.get("offset"), default=0)

    queryset = PoolMasterDataBinding.objects.filter(tenant_id=tenant_id)
    entity_type = str(params.get("entity_type") or "").strip()
    if entity_type:
        queryset = queryset.filter(entity_type=entity_type)
    canonical_id = str(params.get("canonical_id") or "").strip()
    if canonical_id:
        queryset = queryset.filter(canonical_id=canonical_id)
    database_id = params.get("database_id")
    if database_id is not None:
        queryset = queryset.filter(database_id=database_id)
    ib_catalog_kind = str(params.get("ib_catalog_kind") or "").strip()
    if ib_catalog_kind:
        queryset = queryset.filter(ib_catalog_kind=ib_catalog_kind)
    owner_counterparty_canonical_id = str(params.get("owner_counterparty_canonical_id") or "").strip()
    if owner_counterparty_canonical_id:
        queryset = queryset.filter(owner_counterparty_canonical_id=owner_counterparty_canonical_id)
    chart_identity = str(params.get("chart_identity") or "").strip()
    if chart_identity:
        queryset = queryset.filter(chart_identity=chart_identity)
    sync_status = str(params.get("sync_status") or "").strip()
    if sync_status:
        queryset = queryset.filter(sync_status=sync_status)

    count = queryset.count()
    bindings = list(queryset.order_by("-updated_at", "id")[offset : offset + limit])
    return Response(
        {
            "bindings": [_serialize_binding(binding) for binding in bindings],
            "count": count,
            "limit": limit,
            "offset": offset,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bindings_get",
    summary="Get master-data binding by id",
    responses={
        200: PoolMasterDataBindingDetailResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_master_data_binding(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    binding = PoolMasterDataBinding.objects.filter(id=id, tenant_id=tenant_id).first()
    if binding is None:
        return _problem(
            code="MASTER_DATA_BINDING_NOT_FOUND",
            title="Master Data Binding Not Found",
            detail="Binding not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return Response({"binding": _serialize_binding(binding)}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bindings_upsert",
    summary="Create or update master-data binding",
    request=PoolMasterDataBindingUpsertRequestSerializer,
    responses={
        200: PoolMasterDataBindingUpsertResponseSerializer,
        201: PoolMasterDataBindingUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_master_data_binding(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = PoolMasterDataBindingUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="Binding payload validation failed.", errors=serializer.errors)
    data = serializer.validated_data

    database = Database.objects.filter(id=data["database_id"], tenant_id=tenant_id).first()
    if database is None:
        return _problem(
            code="MASTER_DATA_DATABASE_NOT_FOUND",
            title="Master Data Database Not Found",
            detail="Database not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    binding = None
    binding_id = data.get("binding_id")
    if binding_id is not None:
        binding = PoolMasterDataBinding.objects.filter(id=binding_id, tenant_id=tenant_id).first()
        if binding is None:
            return _problem(
                code="MASTER_DATA_BINDING_NOT_FOUND",
                title="Master Data Binding Not Found",
                detail="Binding not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    tenant = binding.tenant if binding is not None else database.tenant
    try:
        result = upsert_pool_master_data_binding(
            tenant=tenant,
            entity_type=str(data["entity_type"]),
            canonical_id=str(data["canonical_id"]),
            database=database,
            existing_binding=binding,
            ib_ref_key=str(data["ib_ref_key"]),
            ib_catalog_kind=str(data.get("ib_catalog_kind", "")),
            owner_counterparty_canonical_id=str(data.get("owner_counterparty_canonical_id", "")),
            chart_identity=str(data.get("chart_identity", "")),
            sync_status=str(data.get("sync_status", PoolMasterBindingSyncStatus.RESOLVED)),
            fingerprint=str(data.get("fingerprint", "")),
            metadata=data.get("metadata", {}),
            origin_system="cc",
        )
    except MasterDataResolveError as exc:
        if exc.code == "MASTER_DATA_ENTITY_NOT_FOUND":
            return _problem(
                code="MASTER_DATA_ENTITY_NOT_FOUND",
                title="Master Data Entity Not Found",
                detail=exc.detail,
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )
        return _validation_problem(
            detail="Binding payload validation failed.",
            errors=exc.errors or [{"detail": exc.detail}],
        )
    except DjangoValidationError as exc:
        return _validation_problem(
            detail="Binding payload validation failed.",
            errors=exc.message_dict if hasattr(exc, "message_dict") else str(exc),
        )
    except IntegrityError:
        return _problem(
            code="MASTER_DATA_BINDING_SCOPE_CONFLICT",
            title="Master Data Binding Scope Conflict",
            detail="Binding with this scope already exists in tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    binding = result.binding
    if result.changed and supports_pool_master_data_capability(
        entity_type=str(binding.entity_type),
        capability=POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
    ):
        origin_event_id = f"binding:{binding.id}:{int(binding.updated_at.timestamp())}"
        _schedule_outbound_master_data_sync_job_trigger(
            tenant_id=str(binding.tenant_id),
            database_id=str(binding.database_id),
            entity_type=str(binding.entity_type),
            canonical_id=str(binding.canonical_id),
            origin_system="cc",
            origin_event_id=origin_event_id,
        )

    response_status = http_status.HTTP_201_CREATED if result.created else http_status.HTTP_200_OK
    return Response({"binding": _serialize_binding(binding), "created": result.created}, status=response_status)
