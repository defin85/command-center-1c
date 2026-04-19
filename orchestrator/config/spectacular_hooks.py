from __future__ import annotations

from copy import deepcopy
from typing import Any

_OPTIONAL_TENANT_HEADER = {
    "name": "X-CC1C-Tenant-ID",
    "in": "header",
    "required": False,
    "schema": {"type": "string", "format": "uuid"},
    "description": (
        "Optional tenant context selector. If omitted, tenant is resolved via user preference or first membership. "
        "For staff users, omission may return cross-tenant results on some endpoints."
    ),
}
_REQUIRED_UI_INCIDENT_TENANT_HEADER = {
    "name": "X-CC1C-Tenant-ID",
    "in": "header",
    "required": True,
    "schema": {"type": "string", "format": "uuid"},
    "description": "Required tenant context selector for UI incident telemetry ingest and staff diagnostics queries.",
}
_LOCALE_HEADER = {
    "name": "X-CC1C-Locale",
    "in": "header",
    "required": False,
    "schema": {"type": "string", "enum": ["ru", "en"]},
    "description": (
        "Optional operator locale override. If omitted, locale is resolved from browser language signal "
        "and then falls back to the deployment default."
    ),
}
_REQUIRED_TENANT_HEADER_PATHS = {
    "/api/v2/ui/incident-telemetry/ingest/",
    "/api/v2/ui/incident-telemetry/incidents/",
    "/api/v2/ui/incident-telemetry/timeline/",
}


def remove_nullable_oneof_nullenum(result: dict[str, Any], generator: Any, request: Any, public: bool):
    """
    orval (TypeScript) can't handle some redundant "nullable + oneOf(null)" constructs and may
    fail with duplicate schema name collisions.

    drf-spectacular can emit:
      nullable: true
      oneOf: [<schema>, NullEnum]

    Since NullEnum already encodes nullability, drop the redundant "nullable: true".
    """

    def _walk(node: Any):
        if isinstance(node, dict):
            if node.get("nullable") is True and "oneOf" in node:
                one_of = node.get("oneOf")
                if isinstance(one_of, list) and any(
                    isinstance(item, dict) and item.get("$ref") == "#/components/schemas/NullEnum"
                    for item in one_of
                ):
                    node.pop("nullable", None)
            for value in node.values():
                _walk(value)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)

    components = result.get("components") or {}
    schemas = components.get("schemas") or {}
    _walk(schemas)
    return result


def add_tenant_header_parameter(result: dict[str, Any], generator: Any, request: Any, public: bool):
    """
    Document optional context headers for API v2.

    Runtime behavior is implemented in apps.tenancy.authentication.TenantContextAuthentication.
    """

    paths = result.get("paths")
    if not isinstance(paths, dict):
        return result

    for path, path_item in paths.items():
        if not isinstance(path, str) or not path.startswith("/api/v2/"):
            continue
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                continue
            params = operation.setdefault("parameters", [])
            if not isinstance(params, list):
                continue
            desired_headers = [
                _REQUIRED_UI_INCIDENT_TENANT_HEADER
                if path in _REQUIRED_TENANT_HEADER_PATHS
                else _OPTIONAL_TENANT_HEADER,
                _LOCALE_HEADER,
            ]
            for desired in desired_headers:
                existing = next(
                    (
                        p for p in params
                        if isinstance(p, dict) and p.get("in") == "header" and p.get("name") == desired["name"]
                    ),
                    None,
                )
                if existing is None:
                    params.append(deepcopy(desired))
                    continue
                existing.update(deepcopy(desired))

    return result
