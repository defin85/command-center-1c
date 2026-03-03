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
from apps.intercompany_pools.models import (
    PoolMasterBindingSyncStatus,
    PoolMasterBindingCatalogKind,
    PoolMasterContract,
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterItem,
    PoolMasterParty,
    PoolMasterTaxProfile,
)
from apps.intercompany_pools.master_data_sync_origin import (
    MASTER_DATA_SYNC_ORIGIN_IB,
    normalize_master_data_sync_origin,
    should_skip_outbound_sync_for_origin,
)
from apps.intercompany_pools.master_data_sync_execution import (
    trigger_pool_master_data_outbound_sync_job,
)
from apps.intercompany_pools.master_data_sync_outbox import enqueue_master_data_sync_outbox_intent

from .intercompany_pools import _parse_limit, _problem, _resolve_tenant_id

logger = logging.getLogger(__name__)


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
        "sync_status": binding.sync_status,
        "fingerprint": binding.fingerprint,
        "metadata": binding.metadata if isinstance(binding.metadata, dict) else {},
        "last_synced_at": binding.last_synced_at,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
    }


def _assign_changed_fields(instance: object, payload: dict[str, Any]) -> bool:
    changed = False
    for field_name, value in payload.items():
        if getattr(instance, field_name) != value:
            setattr(instance, field_name, value)
            changed = True
    return changed


def _enqueue_canonical_mutation_outbox_intents(
    *,
    tenant_id: str | UUID,
    entity_type: str,
    canonical_id: str,
    mutation_kind: str,
    payload: dict[str, Any],
    origin_event_id: str,
    origin_system: str = "cc",
) -> None:
    origin = normalize_master_data_sync_origin(
        origin_system=origin_system,
        origin_event_id=origin_event_id,
    )
    if should_skip_outbound_sync_for_origin(
        origin_system=origin.origin_system,
        origin_event_id=origin.origin_event_id,
        target_system=MASTER_DATA_SYNC_ORIGIN_IB,
    ):
        return

    database_ids = list(
        Database.objects.filter(tenant_id=tenant_id).values_list("id", flat=True)
    )
    for database_id in database_ids:
        enqueue_master_data_sync_outbox_intent(
            tenant_id=str(tenant_id),
            database_id=str(database_id),
            entity_type=entity_type,
            canonical_id=canonical_id,
            mutation_kind=mutation_kind,
            payload=payload,
            origin_system=origin.origin_system,
            origin_event_id=origin.origin_event_id,
        )
        _schedule_outbound_master_data_sync_job_trigger(
            tenant_id=str(tenant_id),
            database_id=str(database_id),
            entity_type=entity_type,
            canonical_id=canonical_id,
            origin_system=origin.origin_system,
            origin_event_id=origin.origin_event_id,
        )


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


class MasterDataBindingListQuerySerializer(_MasterDataListBaseQuerySerializer):
    entity_type = serializers.ChoiceField(required=False, choices=PoolMasterDataEntityType.values)
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    database_id = serializers.UUIDField(required=False)
    ib_catalog_kind = serializers.ChoiceField(
        required=False,
        choices=[PoolMasterBindingCatalogKind.ORGANIZATION, PoolMasterBindingCatalogKind.COUNTERPARTY],
    )
    owner_counterparty_canonical_id = serializers.CharField(required=False, allow_blank=True)
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


class PoolMasterDataBindingSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    entity_type = serializers.CharField()
    canonical_id = serializers.CharField()
    database_id = serializers.UUIDField()
    ib_ref_key = serializers.CharField()
    ib_catalog_kind = serializers.CharField(required=False, allow_blank=True)
    owner_counterparty_canonical_id = serializers.CharField(required=False, allow_blank=True)
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
    entity_type = serializers.ChoiceField(choices=PoolMasterDataEntityType.values)
    canonical_id = serializers.CharField(max_length=128)
    database_id = serializers.UUIDField()
    ib_ref_key = serializers.CharField(max_length=128)
    ib_catalog_kind = serializers.CharField(required=False, allow_blank=True, default="")
    owner_counterparty_canonical_id = serializers.CharField(required=False, allow_blank=True, default="")
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
    if party is None:
        party = PoolMasterParty.objects.filter(tenant_id=tenant_id, canonical_id=data["canonical_id"]).first()

    created = party is None
    payload = {
        "tenant_id": tenant_id,
        "canonical_id": data["canonical_id"],
        "name": data["name"],
        "full_name": data.get("full_name", ""),
        "inn": data.get("inn", ""),
        "kpp": data.get("kpp", ""),
        "is_our_organization": data.get("is_our_organization", False),
        "is_counterparty": data.get("is_counterparty", True),
        "metadata": data.get("metadata", {}),
    }
    try:
        with transaction.atomic():
            changed = True
            if created:
                party = PoolMasterParty.objects.create(**payload)
            else:
                changed = _assign_changed_fields(party, payload)
                if changed:
                    party.save()

            if changed:
                origin_event_id = f"party:{party.id}:{int(party.updated_at.timestamp())}"
                _enqueue_canonical_mutation_outbox_intents(
                    tenant_id=tenant_id,
                    entity_type=PoolMasterDataEntityType.PARTY,
                    canonical_id=str(party.canonical_id),
                    mutation_kind="party_upsert",
                    payload={
                        "canonical_id": str(party.canonical_id),
                        "name": str(party.name or ""),
                        "full_name": str(party.full_name or ""),
                        "inn": str(party.inn or ""),
                        "kpp": str(party.kpp or ""),
                        "is_our_organization": bool(party.is_our_organization),
                        "is_counterparty": bool(party.is_counterparty),
                        "metadata": dict(party.metadata or {}),
                    },
                    origin_event_id=origin_event_id,
                )
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
    if item is None:
        item = PoolMasterItem.objects.filter(tenant_id=tenant_id, canonical_id=data["canonical_id"]).first()

    created = item is None
    payload = {
        "tenant_id": tenant_id,
        "canonical_id": data["canonical_id"],
        "name": data["name"],
        "sku": data.get("sku", ""),
        "unit": data.get("unit", ""),
        "metadata": data.get("metadata", {}),
    }
    try:
        with transaction.atomic():
            changed = True
            if created:
                item = PoolMasterItem.objects.create(**payload)
            else:
                changed = _assign_changed_fields(item, payload)
                if changed:
                    item.save()

            if changed:
                origin_event_id = f"item:{item.id}:{int(item.updated_at.timestamp())}"
                _enqueue_canonical_mutation_outbox_intents(
                    tenant_id=tenant_id,
                    entity_type=PoolMasterDataEntityType.ITEM,
                    canonical_id=str(item.canonical_id),
                    mutation_kind="item_upsert",
                    payload={
                        "canonical_id": str(item.canonical_id),
                        "name": str(item.name or ""),
                        "sku": str(item.sku or ""),
                        "unit": str(item.unit or ""),
                        "metadata": dict(item.metadata or {}),
                    },
                    origin_event_id=origin_event_id,
                )
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
    if contract is None:
        contract = PoolMasterContract.objects.filter(
            tenant_id=tenant_id,
            canonical_id=data["canonical_id"],
            owner_counterparty=owner_counterparty,
        ).first()

    created = contract is None
    payload = {
        "tenant_id": tenant_id,
        "canonical_id": data["canonical_id"],
        "name": data["name"],
        "owner_counterparty": owner_counterparty,
        "number": data.get("number", ""),
        "date": data.get("date"),
        "metadata": data.get("metadata", {}),
    }
    try:
        with transaction.atomic():
            changed = True
            if created:
                contract = PoolMasterContract.objects.create(**payload)
            else:
                changed = _assign_changed_fields(contract, payload)
                if changed:
                    contract.save()

            if changed:
                origin_event_id = f"contract:{contract.id}:{int(contract.updated_at.timestamp())}"
                _enqueue_canonical_mutation_outbox_intents(
                    tenant_id=tenant_id,
                    entity_type=PoolMasterDataEntityType.CONTRACT,
                    canonical_id=str(contract.canonical_id),
                    mutation_kind="contract_upsert",
                    payload={
                        "canonical_id": str(contract.canonical_id),
                        "name": str(contract.name or ""),
                        "owner_counterparty_id": str(contract.owner_counterparty_id),
                        "owner_counterparty_canonical_id": str(contract.owner_counterparty.canonical_id),
                        "number": str(contract.number or ""),
                        "date": contract.date.isoformat() if contract.date else "",
                        "metadata": dict(contract.metadata or {}),
                    },
                    origin_event_id=origin_event_id,
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
    if tax_profile is None:
        tax_profile = PoolMasterTaxProfile.objects.filter(tenant_id=tenant_id, canonical_id=data["canonical_id"]).first()

    created = tax_profile is None
    payload = {
        "tenant_id": tenant_id,
        "canonical_id": data["canonical_id"],
        "vat_rate": data["vat_rate"],
        "vat_included": data["vat_included"],
        "vat_code": data["vat_code"],
        "metadata": data.get("metadata", {}),
    }
    try:
        with transaction.atomic():
            changed = True
            if created:
                tax_profile = PoolMasterTaxProfile.objects.create(**payload)
            else:
                changed = _assign_changed_fields(tax_profile, payload)
                if changed:
                    tax_profile.save()

            if changed:
                origin_event_id = f"tax_profile:{tax_profile.id}:{int(tax_profile.updated_at.timestamp())}"
                _enqueue_canonical_mutation_outbox_intents(
                    tenant_id=tenant_id,
                    entity_type=PoolMasterDataEntityType.TAX_PROFILE,
                    canonical_id=str(tax_profile.canonical_id),
                    mutation_kind="tax_profile_upsert",
                    payload={
                        "canonical_id": str(tax_profile.canonical_id),
                        "vat_rate": str(tax_profile.vat_rate),
                        "vat_included": bool(tax_profile.vat_included),
                        "vat_code": str(tax_profile.vat_code or ""),
                        "metadata": dict(tax_profile.metadata or {}),
                    },
                    origin_event_id=origin_event_id,
                )
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
    if binding is None:
        binding = PoolMasterDataBinding.objects.filter(
            tenant_id=tenant_id,
            entity_type=data["entity_type"],
            canonical_id=data["canonical_id"],
            database=database,
            ib_catalog_kind=data.get("ib_catalog_kind", ""),
            owner_counterparty_canonical_id=data.get("owner_counterparty_canonical_id", ""),
        ).first()

    created = binding is None
    payload = {
        "tenant_id": tenant_id,
        "entity_type": data["entity_type"],
        "canonical_id": data["canonical_id"],
        "database": database,
        "ib_ref_key": data["ib_ref_key"],
        "ib_catalog_kind": data.get("ib_catalog_kind", ""),
        "owner_counterparty_canonical_id": data.get("owner_counterparty_canonical_id", ""),
        "sync_status": data.get("sync_status", PoolMasterBindingSyncStatus.RESOLVED),
        "fingerprint": data.get("fingerprint", ""),
        "metadata": data.get("metadata", {}),
    }
    try:
        with transaction.atomic():
            changed = True
            if created:
                binding = PoolMasterDataBinding.objects.create(**payload)
            else:
                changed = _assign_changed_fields(binding, payload)
                if changed:
                    binding.save()

            if changed:
                origin_event_id = f"binding:{binding.id}:{int(binding.updated_at.timestamp())}"
                enqueue_master_data_sync_outbox_intent(
                    tenant_id=str(binding.tenant_id),
                    database_id=str(binding.database_id),
                    entity_type=str(binding.entity_type),
                    canonical_id=str(binding.canonical_id),
                    mutation_kind="binding_upsert",
                    payload={
                        "entity_type": str(binding.entity_type),
                        "canonical_id": str(binding.canonical_id),
                        "ib_ref_key": str(binding.ib_ref_key or ""),
                        "ib_catalog_kind": str(binding.ib_catalog_kind or ""),
                        "owner_counterparty_canonical_id": str(
                            binding.owner_counterparty_canonical_id or ""
                        ),
                        "sync_status": str(binding.sync_status or ""),
                        "fingerprint": str(binding.fingerprint or ""),
                        "metadata": dict(binding.metadata or {}),
                    },
                    origin_system="cc",
                    origin_event_id=origin_event_id,
                )
                _schedule_outbound_master_data_sync_job_trigger(
                    tenant_id=str(binding.tenant_id),
                    database_id=str(binding.database_id),
                    entity_type=str(binding.entity_type),
                    canonical_id=str(binding.canonical_id),
                    origin_system="cc",
                    origin_event_id=origin_event_id,
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

    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response({"binding": _serialize_binding(binding), "created": created}, status=response_status)
