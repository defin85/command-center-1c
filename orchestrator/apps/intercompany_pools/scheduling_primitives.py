from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


SERVER_AFFINITY_UNRESOLVED = "SERVER_AFFINITY_UNRESOLVED"


@dataclass(frozen=True)
class SchedulingAffinityResolution:
    server_affinity: str
    source: str


def normalize_affinity_token(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    if "://" in token:
        token = token.split("://", 1)[1]
    token = token.strip().strip("/")
    token = re.sub(r"[^a-z0-9._:-]+", "-", token)
    token = token.strip("-")
    return token


def _resolve_affinity_override(metadata: Any, *, metadata_namespace: str) -> str:
    if not isinstance(metadata, dict):
        return ""

    nested = metadata.get(metadata_namespace)
    if isinstance(nested, dict):
        value = normalize_affinity_token(nested.get("server_affinity"))
        if value:
            return value

    namespace_key = f"{metadata_namespace}_server_affinity"
    for key in (
        namespace_key,
        "sync_server_affinity",
        "server_affinity",
    ):
        value = normalize_affinity_token(metadata.get(key))
        if value:
            return value
    return ""


def _resolve_database_endpoint(database: Any) -> str:
    cluster = getattr(database, "cluster", None)
    if cluster is not None:
        ras_server = normalize_affinity_token(getattr(cluster, "ras_server", ""))
        if ras_server:
            return ras_server
        ras_host = normalize_affinity_token(getattr(cluster, "ras_host", ""))
        ras_port = int(getattr(cluster, "ras_port", 0) or 0)
        if ras_host:
            return f"{ras_host}:{ras_port}" if ras_port > 0 else ras_host

    server_address = normalize_affinity_token(getattr(database, "server_address", ""))
    server_port = int(getattr(database, "server_port", 0) or 0)
    if server_address:
        return f"{server_address}:{server_port}" if server_port > 0 else server_address

    host = normalize_affinity_token(getattr(database, "host", ""))
    port = int(getattr(database, "port", 0) or 0)
    if host:
        return f"{host}:{port}" if port > 0 else host
    return ""


def resolve_database_server_affinity(
    *,
    database: Any,
    metadata_namespace: str,
) -> SchedulingAffinityResolution:
    cluster = getattr(database, "cluster", None)

    database_override = _resolve_affinity_override(
        getattr(database, "metadata", None),
        metadata_namespace=metadata_namespace,
    )
    if database_override:
        return SchedulingAffinityResolution(server_affinity=database_override, source="database_override")

    cluster_override = _resolve_affinity_override(
        getattr(cluster, "metadata", None),
        metadata_namespace=metadata_namespace,
    )
    if cluster_override:
        return SchedulingAffinityResolution(server_affinity=cluster_override, source="cluster_mapping")

    endpoint = _resolve_database_endpoint(database)
    if endpoint:
        return SchedulingAffinityResolution(server_affinity=f"srv:{endpoint}", source="derived_endpoint")

    raise ValueError(
        f"{SERVER_AFFINITY_UNRESOLVED}: unable to resolve server affinity for database "
        f"'{getattr(database, 'id', 'unknown')}'"
    )
