# ruff: noqa: F405
"""Canonical metadata management endpoints for /databases."""

from __future__ import annotations

from typing import Any

from .common import *  # noqa: F403
from .common import _permission_denied, _resolve_tenant_id
from apps.intercompany_pools.business_configuration_operations import (
    BUSINESS_CONFIGURATION_JOB_KIND_VERIFICATION,
    enqueue_business_configuration_verification,
    find_active_business_configuration_operation,
    get_business_configuration_verification_availability,
)
from apps.intercompany_pools.business_configuration_profile import get_business_configuration_profile
from apps.intercompany_pools.master_data_sync_cluster_all_eligibility import (
    build_pool_master_data_sync_readiness_summary,
    get_pool_master_data_sync_cluster_all_eligibility_state,
    set_pool_master_data_sync_cluster_all_eligibility_state,
)
from apps.intercompany_pools.metadata_catalog import (
    MetadataCatalogError,
    get_database_metadata_catalog_state,
    refresh_metadata_catalog_snapshot,
)
from apps.databases.serializers import DatabaseSerializer


def _database_error(*, code: str, message: str, details: dict[str, Any] | None = None, status_code: int = 400):
    payload: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details:
        payload["error"]["details"] = details
    return Response(payload, status=status_code)


def _load_database_for_tenant(request, *, database_id: str) -> Database | None:
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return None
    return Database.all_objects.filter(id=database_id, tenant_id=str(tenant_id)).first()


def _serialize_configuration_profile_state(*, database: Database) -> dict[str, Any]:
    profile = get_business_configuration_profile(database=database) or {}
    availability = get_business_configuration_verification_availability(database=database)
    active_verification = find_active_business_configuration_operation(
        database=database,
        job_kind=BUSINESS_CONFIGURATION_JOB_KIND_VERIFICATION,
    )
    if active_verification is not None:
        status = "verification_pending"
        verification_operation_id = str(
            availability.get("active_operation_id") or active_verification.id
        )
    elif profile:
        status = str(profile.get("verification_status") or "").strip() or "verified"
        verification_operation_id = str(profile.get("verification_operation_id") or "").strip()
    else:
        status = "missing"
        verification_operation_id = ""

    return {
        "status": status,
        "config_name": str(profile.get("config_name") or ""),
        "config_version": str(profile.get("config_version") or ""),
        "config_generation_id": str(profile.get("config_generation_id") or ""),
        "config_root_name": str(profile.get("config_root_name") or ""),
        "config_vendor": str(profile.get("config_vendor") or ""),
        "config_name_source": str(profile.get("config_name_source") or ""),
        "verification_operation_id": verification_operation_id,
        "verified_at": profile.get("verified_at") or None,
        "generation_probe_requested_at": profile.get("generation_probe_requested_at") or None,
        "generation_probe_checked_at": profile.get("generation_probe_checked_at") or None,
        "observed_metadata_fetched_at": profile.get("observed_metadata_fetched_at") or None,
        "observed_metadata_hash": str(profile.get("observed_metadata_hash") or ""),
        "canonical_metadata_hash": str(profile.get("canonical_metadata_hash") or ""),
        "publication_drift": bool(profile.get("publication_drift")),
        "reverify_available": bool(availability.get("available")),
        "reverify_blocker_code": str(availability.get("blocker_code") or ""),
        "reverify_blocker_message": str(availability.get("blocker_message") or ""),
        "reverify_blocking_action": str(availability.get("blocking_action") or ""),
    }


def _serialize_pool_master_data_sync_state(*, database: Database) -> dict[str, Any]:
    return {
        "cluster_all_eligibility": {
            "state": get_pool_master_data_sync_cluster_all_eligibility_state(database=database),
        },
        "readiness": build_pool_master_data_sync_readiness_summary(database=database),
    }


def _serialize_metadata_management_payload(*, tenant_id: str, database: Database) -> dict[str, Any]:
    state = get_database_metadata_catalog_state(tenant_id=tenant_id, database=database)
    profile_state = _serialize_configuration_profile_state(database=database)
    pool_master_data_sync_state = _serialize_pool_master_data_sync_state(database=database)

    if state.snapshot is None or state.resolution is None:
        return {
            "database_id": str(database.id),
            "configuration_profile": profile_state,
            "metadata_snapshot": {
                "status": "missing",
                "missing_reason": (
                    "configuration_profile_unavailable"
                    if state.profile is None
                    else "current_snapshot_missing"
                ),
                "snapshot_id": "",
                "source": "",
                "fetched_at": None,
                "catalog_version": "",
                "config_name": str((state.profile or {}).get("config_name") or ""),
                "config_version": str((state.profile or {}).get("config_version") or ""),
                "extensions_fingerprint": "",
                "metadata_hash": "",
                "resolution_mode": "",
                "is_shared_snapshot": False,
                "provenance_database_id": "",
                "provenance_confirmed_at": None,
                "observed_metadata_hash": profile_state["observed_metadata_hash"],
                "publication_drift": profile_state["publication_drift"],
            },
            "pool_master_data_sync": pool_master_data_sync_state,
        }

    snapshot = state.snapshot
    resolution = state.resolution
    return {
        "database_id": str(database.id),
        "configuration_profile": profile_state,
        "metadata_snapshot": {
            "status": "available",
            "missing_reason": "",
            "snapshot_id": str(snapshot.id),
            "source": str(snapshot.source or ""),
            "fetched_at": snapshot.fetched_at,
            "catalog_version": snapshot.catalog_version,
            "config_name": snapshot.config_name,
            "config_version": snapshot.config_version,
            "extensions_fingerprint": snapshot.extensions_fingerprint,
            "metadata_hash": snapshot.metadata_hash,
            "resolution_mode": resolution.resolution_mode,
            "is_shared_snapshot": resolution.is_shared_snapshot,
            "provenance_database_id": resolution.provenance_database_id,
            "provenance_confirmed_at": resolution.provenance_confirmed_at,
            "observed_metadata_hash": profile_state["observed_metadata_hash"],
            "publication_drift": profile_state["publication_drift"],
        },
        "pool_master_data_sync": pool_master_data_sync_state,
    }


@extend_schema(
    tags=["v2"],
    summary="Get database metadata management state",
    description="Return truthful configuration profile and metadata snapshot state for the selected database.",
    parameters=[
        OpenApiParameter(name="database_id", type=str, required=True, description="Database UUID"),
    ],
    responses={
        200: DatabaseMetadataManagementResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: DatabaseErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_metadata_management(request):
    serializer = DatabaseMetadataManagementActionRequestSerializer(data=request.query_params)
    if not serializer.is_valid():
        return _database_error(
            code="VALIDATION_ERROR",
            message="Invalid query parameters",
            details=serializer.errors,
            status_code=400,
        )

    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _permission_denied("Tenant context is missing.")

    database = _load_database_for_tenant(request, database_id=serializer.validated_data["database_id"])
    if database is None:
        return _database_error(code="DATABASE_NOT_FOUND", message="Database not found", status_code=404)

    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE, database):
        return _permission_denied("You do not have permission to access this database.")

    return Response(
        _serialize_metadata_management_payload(
            tenant_id=str(tenant_id),
            database=database,
        )
    )


@extend_schema(
    tags=["v2"],
    summary="Queue configuration identity re-verification",
    description="Queue async business configuration profile verification for the selected database.",
    request=DatabaseMetadataManagementActionRequestSerializer,
    responses={
        202: DatabaseMetadataManagementReverifyResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: DatabaseErrorResponseSerializer,
        409: DatabaseErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reverify_configuration_profile(request):
    serializer = DatabaseMetadataManagementActionRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _database_error(
            code="VALIDATION_ERROR",
            message="Invalid payload",
            details=serializer.errors,
            status_code=400,
        )

    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _permission_denied("Tenant context is missing.")

    database = _load_database_for_tenant(request, database_id=serializer.validated_data["database_id"])
    if database is None:
        return _database_error(code="DATABASE_NOT_FOUND", message="Database not found", status_code=404)

    if not request.user.has_perm(perms.PERM_DATABASES_OPERATE_DATABASE, database):
        return _permission_denied("You do not have permission to operate this database.")

    availability = get_business_configuration_verification_availability(database=database)
    if not availability.get("available"):
        details: dict[str, Any] | None = None
        if any(
            str(availability.get(key) or "").strip()
            for key in ("blocking_action", "active_operation_id")
        ):
            details = {
                "blocking_action": str(availability.get("blocking_action") or ""),
                "active_operation_id": str(availability.get("active_operation_id") or ""),
            }
        return _database_error(
            code=str(
                availability.get("blocker_code") or "BUSINESS_CONFIGURATION_VERIFICATION_UNAVAILABLE"
            ),
            message=str(
                availability.get("blocker_message")
                or "Configuration identity re-verify is unavailable for selected database."
            ),
            details=details,
            status_code=409,
        )

    operation = enqueue_business_configuration_verification(
        database=database,
        reason="manual_database_metadata_management",
    )
    if operation is None:
        return _database_error(
            code="BUSINESS_CONFIGURATION_VERIFICATION_UNAVAILABLE",
            message="Configuration identity re-verify is unavailable for selected database.",
            status_code=409,
        )

    log_admin_action(
        request,
        action="database.metadata_management.reverify_configuration_profile",
        outcome="success",
        target_type="database",
        target_id=str(database.id),
        metadata={"operation_id": str(operation.id)},
    )

    return Response(
        {
            "database_id": str(database.id),
            "operation_id": str(operation.id),
            "status": "queued",
            "message": "Configuration identity re-verify queued",
        },
        status=http_status.HTTP_202_ACCEPTED,
    )


@extend_schema(
    tags=["v2"],
    summary="Refresh metadata snapshot for selected database",
    description="Refresh normalized metadata snapshot and return updated canonical metadata management state.",
    request=DatabaseMetadataManagementActionRequestSerializer,
    responses={
        200: DatabaseMetadataManagementResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: DatabaseErrorResponseSerializer,
        409: DatabaseErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def refresh_metadata_snapshot(request):
    serializer = DatabaseMetadataManagementActionRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _database_error(
            code="VALIDATION_ERROR",
            message="Invalid payload",
            details=serializer.errors,
            status_code=400,
        )

    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _permission_denied("Tenant context is missing.")

    database = _load_database_for_tenant(request, database_id=serializer.validated_data["database_id"])
    if database is None:
        return _database_error(code="DATABASE_NOT_FOUND", message="Database not found", status_code=404)

    if not request.user.has_perm(perms.PERM_DATABASES_OPERATE_DATABASE, database):
        return _permission_denied("You do not have permission to operate this database.")

    try:
        refresh_metadata_catalog_snapshot(
            tenant_id=str(tenant_id),
            database=database,
            requested_by_username=str(getattr(request.user, "username", "") or "").strip(),
            source="live_refresh",
        )
    except MetadataCatalogError as exc:
        return _database_error(code=exc.code, message=exc.detail, status_code=exc.status_code)

    log_admin_action(
        request,
        action="database.metadata_management.refresh_metadata_snapshot",
        outcome="success",
        target_type="database",
        target_id=str(database.id),
        metadata={"source": "live_refresh"},
    )

    return Response(
        _serialize_metadata_management_payload(
            tenant_id=str(tenant_id),
            database=database,
        )
    )


@extend_schema(
    tags=["v2"],
    summary="Update pool master-data cluster_all eligibility",
    description="Set explicit cluster_all eligibility state for pool master-data sync on the selected database.",
    request=DatabaseMasterDataSyncEligibilityUpdateRequestSerializer,
    responses={
        200: DatabaseMasterDataSyncEligibilityUpdateResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: DatabaseErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_pool_master_data_sync_eligibility(request):
    serializer = DatabaseMasterDataSyncEligibilityUpdateRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _database_error(
            code="VALIDATION_ERROR",
            message="Invalid payload",
            details=serializer.errors,
            status_code=400,
        )

    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _permission_denied("Tenant context is missing.")

    database = _load_database_for_tenant(request, database_id=serializer.validated_data["database_id"])
    if database is None:
        return _database_error(code="DATABASE_NOT_FOUND", message="Database not found", status_code=404)

    if not request.user.has_perm(perms.PERM_DATABASES_MANAGE_DATABASE, database):
        return _permission_denied("You do not have permission to update database metadata.")

    state = str(serializer.validated_data["cluster_all_eligibility_state"] or "")
    database.metadata = set_pool_master_data_sync_cluster_all_eligibility_state(
        database=database,
        state=state,
    )
    database.save(update_fields=["metadata", "updated_at"])

    log_admin_action(
        request,
        action="database.pool_master_data_sync.cluster_all_eligibility.update",
        outcome="success",
        target_type="database",
        target_id=str(database.id),
        metadata={
            "cluster_all_eligibility_state": state,
        },
    )

    return Response(
        {
            "database": DatabaseSerializer(database).data,
            "metadata_management": _serialize_metadata_management_payload(
                tenant_id=str(tenant_id),
                database=database,
            ),
            "message": "Pool master-data cluster_all eligibility updated",
        }
    )
