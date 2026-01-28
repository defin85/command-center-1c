"""Operations endpoints: CLI command catalog and driver commands."""

from __future__ import annotations

import json
import logging
from typing import Any

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.artifacts.storage import ArtifactStorageError
from apps.operations.driver_catalog_effective import (
    compute_actor_roles_hash,
    compute_driver_catalog_etag,
    filter_catalog_for_user,
    get_effective_driver_catalog,
    get_effective_driver_catalog_lkg,
    resolve_driver_catalog_versions,
)

from .schemas import (
    CliCommandCatalogResponseSerializer,
    DriverCommandsResponseV2Serializer,
    OperationErrorResponseSerializer,
)

logger = logging.getLogger(__name__)

@extend_schema(
    tags=['v2'],
    summary='Get CLI command catalog',
    description='List supported DESIGNER batch commands for designer_cli.',
    responses={
        200: CliCommandCatalogResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cli_command_catalog(request):
    roles_hash = compute_actor_roles_hash(request.user)

    resolved = resolve_driver_catalog_versions("cli")
    if resolved.base_version is None:
        payload = {
            "version": "unknown",
            "source": "command_schemas",
            "generated_at": "",
            "commands": [],
        }
        etag = compute_driver_catalog_etag(
            driver="cli",
            base_version_id=None,
            overrides_version_id=None,
            roles_hash=roles_hash,
        )
        response = Response(payload)
        response["ETag"] = etag
        response["Cache-Control"] = "private, max-age=0"
        return response

    effective = get_effective_driver_catalog(
        driver="cli",
        base_version=resolved.base_version,
        overrides_version=resolved.overrides_version,
    )
    catalog_v2 = filter_catalog_for_user(request.user, effective.catalog)

    source_meta = catalog_v2.get("source") if isinstance(catalog_v2, dict) else {}
    if not isinstance(source_meta, dict):
        source_meta = {}

    version_str = str(catalog_v2.get("platform_version") or "").strip() or "unknown"
    source_str = str(
        source_meta.get("doc_url")
        or source_meta.get("doc_id")
        or source_meta.get("hint")
        or "command_schemas"
    ).strip() or "command_schemas"
    generated_at = str(catalog_v2.get("generated_at") or "").strip()

    commands_by_id = catalog_v2.get("commands_by_id") if isinstance(catalog_v2, dict) else {}
    if not isinstance(commands_by_id, dict):
        commands_by_id = {}

    commands = []
    for cmd_id in sorted(k for k in commands_by_id.keys() if isinstance(k, str) and k.strip()):
        cmd = commands_by_id.get(cmd_id)
        if not isinstance(cmd, dict):
            continue

        item: dict[str, Any] = {
            "id": cmd_id,
            "label": str(cmd.get("label") or cmd_id),
        }

        description = cmd.get("description")
        if isinstance(description, str) and description:
            item["description"] = description

        argv = cmd.get("argv")
        if isinstance(argv, list) and argv and all(isinstance(x, str) and x.strip() for x in argv):
            item["usage"] = " ".join(str(x).strip() for x in argv if str(x).strip())

        source_section = cmd.get("source_section")
        if isinstance(source_section, str) and source_section:
            item["source_section"] = source_section

        params_by_name = cmd.get("params_by_name")
        if isinstance(params_by_name, dict) and params_by_name:
            params = []
            for name, schema in sorted(params_by_name.items(), key=lambda kv: str(kv[0])):
                if not isinstance(name, str) or not name.strip() or not isinstance(schema, dict):
                    continue

                param: dict[str, Any] = {"name": name}
                kind = str(schema.get("kind") or "").strip() or "flag"
                param["kind"] = kind

                label = schema.get("label")
                if isinstance(label, str) and label:
                    param["label"] = label

                required = schema.get("required")
                if isinstance(required, bool):
                    param["required"] = required

                expects_value = schema.get("expects_value")
                if isinstance(expects_value, bool):
                    param["expects_value"] = expects_value

                flag = schema.get("flag")
                if isinstance(flag, str) and flag:
                    param["flag"] = flag

                params.append(param)

            if params:
                commands.append({**item, "params": params})
                continue

        commands.append(item)

    payload = {
        "version": version_str,
        "source": source_str,
        "generated_at": generated_at,
        "commands": commands,
    }

    etag = compute_driver_catalog_etag(
        driver="cli",
        base_version_id=effective.base_version_id,
        overrides_version_id=effective.overrides_version_id,
        roles_hash=roles_hash,
    )
    response = Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = "private, max-age=0"
    return response


@extend_schema(
    tags=["v2"],
    summary="Get driver command catalog (v2)",
    description=(
        "Return schema-driven command catalog for the requested driver.\n\n"
        "Supports conditional requests via ETag/If-None-Match (returns 304)."
    ),
    parameters=[
        OpenApiParameter(
            name="driver",
            type=str,
            required=True,
            description="Driver name (cli/ibcmd)",
        ),
    ],
    responses={
        200: DriverCommandsResponseV2Serializer,
        304: OpenApiResponse(description="Not Modified"),
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_driver_commands(request):
    driver = str(request.query_params.get("driver") or "").strip()
    if not driver:
        return Response({
            "success": False,
            "error": {"code": "MISSING_DRIVER", "message": "driver is required"},
        }, status=400)

    driver = driver.lower()
    if driver not in {"cli", "ibcmd"}:
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)

    roles_hash = compute_actor_roles_hash(request.user)

    resolved = resolve_driver_catalog_versions(driver)
    if resolved.base_version is not None:
        base_version_id = str(resolved.base_version.id)
        overrides_version_id = str(resolved.overrides_version.id) if resolved.overrides_version is not None else None
        current_etag = compute_driver_catalog_etag(
            driver=driver,
            base_version_id=base_version_id,
            overrides_version_id=overrides_version_id,
            roles_hash=roles_hash,
        )
        if request.headers.get("If-None-Match") == current_etag:
            response = Response(status=304)
            response["ETag"] = current_etag
            return response

        try:
            effective = get_effective_driver_catalog(
                driver=driver,
                base_version=resolved.base_version,
                overrides_version=resolved.overrides_version,
            )
            catalog = filter_catalog_for_user(request.user, effective.catalog)
            etag = compute_driver_catalog_etag(
                driver=driver,
                base_version_id=effective.base_version_id,
                overrides_version_id=effective.overrides_version_id,
                roles_hash=roles_hash,
            )

            payload = {
                "driver": driver,
                "base_version": str(effective.base_version),
                "overrides_version": str(effective.overrides_version) if effective.overrides_version else None,
                "generated_at": str(catalog.get("generated_at") or ""),
                "catalog": catalog,
            }
            response = Response(payload)
            response["ETag"] = etag
            response["Cache-Control"] = "private, max-age=0"
            return response
        except (ArtifactStorageError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            error_message = str(exc)
            if isinstance(exc, ArtifactStorageError):
                logger.warning(
                    "Failed to load driver catalog from storage",
                    extra={"driver": driver, "error": error_message},
                )
                error_code = "STORAGE_ERROR"
            else:
                logger.warning(
                    "Failed to parse driver catalog",
                    extra={"driver": driver, "error": error_message},
                )
                error_code = "CATALOG_INVALID"

        lkg = get_effective_driver_catalog_lkg(driver)
        if lkg is not None:
            etag = compute_driver_catalog_etag(
                driver=driver,
                base_version_id=lkg.base_version_id,
                overrides_version_id=lkg.overrides_version_id,
                roles_hash=roles_hash,
            )
            if request.headers.get("If-None-Match") == etag:
                response = Response(status=304)
                response["ETag"] = etag
                return response

            catalog = filter_catalog_for_user(request.user, lkg.catalog)
            payload = {
                "driver": driver,
                "base_version": str(lkg.base_version),
                "overrides_version": str(lkg.overrides_version) if lkg.overrides_version else None,
                "generated_at": str(catalog.get("generated_at") or ""),
                "catalog": catalog,
            }
            response = Response(payload)
            response["ETag"] = etag
            response["Cache-Control"] = "private, max-age=0"
            return response

        return Response(
            {"success": False, "error": {"code": error_code, "message": error_message}},
            status=500,
        )

    payload = {
        "driver": driver,
        "base_version": "unknown",
        "overrides_version": None,
        "generated_at": "",
        "catalog": {
            "catalog_version": 2,
            "driver": driver,
            "platform_version": "",
            "source": {"type": "not_available", "hint": f"{driver} catalog is not imported yet"},
            "generated_at": "",
            "commands_by_id": {},
        },
    }
    etag = compute_driver_catalog_etag(
        driver=driver,
        base_version_id=None,
        overrides_version_id=None,
        roles_hash=roles_hash,
    )

    if request.headers.get("If-None-Match") == etag:
        response = Response(status=304)
        response["ETag"] = etag
        return response

    response = Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = "private, max-age=0"
    return response
