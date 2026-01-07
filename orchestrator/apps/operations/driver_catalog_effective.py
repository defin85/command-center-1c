from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient, ArtifactStorageError
from apps.runtime_settings.models import RuntimeSetting

from .driver_catalog_v2 import (
    CATALOG_ALIAS_ACTIVE,
    CATALOG_ALIAS_APPROVED,
    CATALOG_ALIAS_LATEST,
)

_CACHE_LOCK = threading.Lock()
_EFFECTIVE_CACHE: dict[tuple[str, str, str | None], dict[str, Any]] = {}
_EFFECTIVE_CACHE_TS: dict[tuple[str, str, str | None], float] = {}
_EFFECTIVE_CACHE_MAX_SIZE = 64

_LKG_KEY_PREFIX = "operations.driver_catalog_lkg."


@dataclass(frozen=True)
class DriverCatalogResolvedVersions:
    base_artifact: Artifact | None
    base_version: ArtifactVersion | None
    overrides_artifact: Artifact | None
    overrides_version: ArtifactVersion | None


@dataclass(frozen=True)
class EffectiveCatalogResult:
    catalog: dict[str, Any]
    base_version: str
    base_version_id: str
    overrides_version: str | None
    overrides_version_id: str | None
    source: str  # cache|storage|lkg


def compute_driver_catalog_etag(
    *,
    driver: str,
    base_version_id: str | None,
    overrides_version_id: str | None,
    roles_hash: str | None,
) -> str:
    payload = f"{driver}:{base_version_id or ''}:{overrides_version_id or ''}:{roles_hash or ''}".encode("utf-8")
    return f"\"{hashlib.sha256(payload).hexdigest()}\""


def resolve_driver_catalog_versions(driver: str) -> DriverCatalogResolvedVersions:
    driver = str(driver or "").strip().lower()
    base_name = f"driver_catalog.{driver}.base"
    overrides_name = f"driver_catalog.{driver}.overrides"

    base = Artifact.objects.filter(name=base_name, kind=ArtifactKind.DRIVER_CATALOG, is_deleted=False).first()
    overrides = Artifact.objects.filter(
        name=overrides_name, kind=ArtifactKind.DRIVER_CATALOG, is_deleted=False
    ).first()

    base_version = _resolve_alias_version(base, CATALOG_ALIAS_APPROVED) or _resolve_alias_version(base, CATALOG_ALIAS_LATEST)
    if base_version is None and base is not None:
        base_version = base.versions.order_by("-created_at").first()

    overrides_version = _resolve_alias_version(overrides, CATALOG_ALIAS_ACTIVE)
    if overrides_version is None and overrides is not None:
        overrides_version = overrides.versions.order_by("-created_at").first()

    return DriverCatalogResolvedVersions(
        base_artifact=base,
        base_version=base_version,
        overrides_artifact=overrides,
        overrides_version=overrides_version,
    )


def invalidate_driver_catalog_cache(driver: str) -> None:
    driver = str(driver or "").strip().lower()
    with _CACHE_LOCK:
        keys_to_remove = [key for key in _EFFECTIVE_CACHE.keys() if key[0] == driver]
        for key in keys_to_remove:
            _EFFECTIVE_CACHE.pop(key, None)
            _EFFECTIVE_CACHE_TS.pop(key, None)


def get_current_environment() -> str:
    return (os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()


def get_actor_roles(user) -> list[str]:
    if not user or not getattr(user, "is_authenticated", False):
        return []

    roles: list[str] = []
    if getattr(user, "is_staff", False):
        roles.append("staff")

    try:
        group_names = user.groups.values_list("name", flat=True)
    except Exception:
        group_names = []

    for name in group_names:
        value = str(name or "").strip()
        if value:
            roles.append(value)

    return sorted(set(roles))


def compute_actor_roles_hash(user) -> str:
    roles = get_actor_roles(user)
    env = get_current_environment()
    payload = f"{env}|{'|'.join(roles)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _parse_str_list(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    items: set[str] = set()
    for item in value:
        s = str(item or "").strip()
        if s:
            items.add(s)
    return items


def _command_permissions(command: dict[str, Any]) -> dict[str, Any] | None:
    raw = command.get("permissions")
    if isinstance(raw, dict):
        return raw
    return None


def _is_command_visible(
    *,
    roles: set[str],
    command: dict[str, Any],
    env: str,
) -> tuple[bool, str | None]:
    if command.get("disabled") is True:
        return False, "disabled"

    risk_level = str(command.get("risk_level") or "").strip().lower()
    if "staff" not in roles and risk_level == "dangerous":
        return False, "dangerous_non_staff"

    permissions = _command_permissions(command) or {}

    allowed_envs = _parse_str_list(permissions.get("allowed_envs"))
    denied_envs = _parse_str_list(permissions.get("denied_envs") or permissions.get("deny_envs"))
    if env and denied_envs and env in denied_envs:
        return False, "env_denied"
    if allowed_envs:
        if not env:
            return False, "env_unknown"
        if env not in allowed_envs:
            return False, "env_not_allowed"

    denied_roles = _parse_str_list(permissions.get("denied_roles") or permissions.get("deny_roles"))
    if denied_roles and roles.intersection(denied_roles):
        return False, "role_denied"

    allowed_roles = _parse_str_list(permissions.get("allowed_roles"))
    if allowed_roles and not roles.intersection(allowed_roles):
        return False, "role_not_allowed"

    return True, None


def get_command_min_db_level(command: dict[str, Any]) -> str | None:
    permissions = _command_permissions(command)
    if not permissions:
        return None
    raw = permissions.get("min_db_level")
    if raw is None:
        return None
    value = str(raw or "").strip().lower()
    return value or None


def explain_command_denied(user, command: dict[str, Any]) -> str | None:
    env = get_current_environment()
    roles = set(get_actor_roles(user))
    allowed, reason = _is_command_visible(roles=roles, command=command, env=env)
    if allowed:
        return None
    return reason or "denied"


def filter_catalog_for_user(user, catalog: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(catalog, dict):
        return catalog

    commands_by_id = catalog.get("commands_by_id")
    if not isinstance(commands_by_id, dict):
        return catalog

    env = get_current_environment()
    roles = set(get_actor_roles(user))

    filtered_commands: dict[str, Any] = {}
    for command_id, command in commands_by_id.items():
        if not isinstance(command_id, str) or not command_id:
            continue
        if not isinstance(command, dict):
            continue
        allowed, _reason = _is_command_visible(roles=roles, command=command, env=env)
        if not allowed:
            continue
        filtered_commands[command_id] = command

    filtered = dict(catalog)
    filtered["commands_by_id"] = filtered_commands
    return filtered


def get_effective_driver_catalog(
    *,
    driver: str,
    base_version: ArtifactVersion,
    overrides_version: ArtifactVersion | None,
) -> EffectiveCatalogResult:
    driver = str(driver or "").strip().lower()
    base_version_id = str(base_version.id)
    overrides_version_id = str(overrides_version.id) if overrides_version is not None else None
    cache_key = (driver, base_version_id, overrides_version_id)

    cached = _get_from_effective_cache(cache_key)
    if cached is not None:
        return EffectiveCatalogResult(
            catalog=cached,
            base_version=str(base_version.version),
            base_version_id=base_version_id,
            overrides_version=str(overrides_version.version) if overrides_version else None,
            overrides_version_id=overrides_version_id,
            source="cache",
        )

    catalog = load_effective_driver_catalog(base_version=base_version, overrides_version=overrides_version)
    _store_in_effective_cache(cache_key, catalog)
    _store_lkg_if_changed(
        driver=driver,
        base_version=base_version,
        overrides_version=overrides_version,
        catalog=catalog,
    )

    return EffectiveCatalogResult(
        catalog=catalog,
        base_version=str(base_version.version),
        base_version_id=base_version_id,
        overrides_version=str(overrides_version.version) if overrides_version else None,
        overrides_version_id=overrides_version_id,
        source="storage",
    )


def get_effective_driver_catalog_lkg(driver: str) -> EffectiveCatalogResult | None:
    driver = str(driver or "").strip().lower()
    key = f"{_LKG_KEY_PREFIX}{driver}"
    setting = RuntimeSetting.objects.filter(key=key).first()
    if not setting or not isinstance(setting.value, dict):
        return None

    value = setting.value
    catalog = value.get("catalog")
    if not isinstance(catalog, dict):
        return None

    base_version_id = str(value.get("base_version_id") or "")
    overrides_version_id = value.get("overrides_version_id")
    overrides_version_id = str(overrides_version_id) if overrides_version_id else None

    base_version = str(value.get("base_version") or "")
    overrides_version = value.get("overrides_version")
    overrides_version = str(overrides_version) if overrides_version else None

    return EffectiveCatalogResult(
        catalog=catalog,
        base_version=base_version,
        base_version_id=base_version_id,
        overrides_version=overrides_version,
        overrides_version_id=overrides_version_id,
        source="lkg",
    )


def load_effective_driver_catalog(
    *,
    base_version: ArtifactVersion,
    overrides_version: ArtifactVersion | None,
) -> dict[str, Any]:
    base_catalog = load_catalog_json(base_version)
    if overrides_version is None:
        return base_catalog

    overrides_catalog = load_catalog_json(overrides_version)
    patch = overrides_catalog.get("overrides")
    if not isinstance(patch, dict):
        return base_catalog

    _deep_merge(base_catalog, patch)
    return base_catalog


def load_catalog_json(version_obj: ArtifactVersion) -> dict[str, Any]:
    storage = ArtifactStorageClient()
    try:
        response = storage.get_object(version_obj.storage_key)
    except ArtifactStorageError:
        raise

    try:
        raw = response.read()
    finally:
        try:
            response.close()
        finally:
            release = getattr(response, "release_conn", None)
            if callable(release):
                release()

    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("catalog must be a JSON object")
    return parsed


def _get_from_effective_cache(cache_key: tuple[str, str, str | None]) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        cached = _EFFECTIVE_CACHE.get(cache_key)
        if cached is None:
            return None
        return cached


def _store_in_effective_cache(cache_key: tuple[str, str, str | None], catalog: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        if len(_EFFECTIVE_CACHE) >= _EFFECTIVE_CACHE_MAX_SIZE:
            keys_to_remove = list(_EFFECTIVE_CACHE.keys())[: _EFFECTIVE_CACHE_MAX_SIZE // 2]
            for key in keys_to_remove:
                _EFFECTIVE_CACHE.pop(key, None)
                _EFFECTIVE_CACHE_TS.pop(key, None)

        _EFFECTIVE_CACHE[cache_key] = catalog
        _EFFECTIVE_CACHE_TS[cache_key] = time.monotonic()


def _store_lkg_if_changed(
    *,
    driver: str,
    base_version: ArtifactVersion,
    overrides_version: ArtifactVersion | None,
    catalog: dict[str, Any],
) -> None:
    key = f"{_LKG_KEY_PREFIX}{driver}"
    base_version_id = str(base_version.id)
    overrides_version_id = str(overrides_version.id) if overrides_version is not None else None

    current = RuntimeSetting.objects.filter(key=key).first()
    if current and isinstance(current.value, dict):
        stored_base_id = str(current.value.get("base_version_id") or "")
        stored_overrides_id = current.value.get("overrides_version_id")
        stored_overrides_id = str(stored_overrides_id) if stored_overrides_id else None
        if stored_base_id == base_version_id and stored_overrides_id == overrides_version_id:
            return

    payload = {
        "driver": driver,
        "base_version": str(base_version.version),
        "base_version_id": base_version_id,
        "overrides_version": str(overrides_version.version) if overrides_version else None,
        "overrides_version_id": overrides_version_id,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "catalog": copy.deepcopy(catalog),
    }
    RuntimeSetting.objects.update_or_create(key=key, defaults={"value": payload})


def _resolve_alias_version(artifact: Artifact | None, alias: str) -> ArtifactVersion | None:
    if artifact is None:
        return None
    alias_obj = ArtifactAlias.objects.select_related("version").filter(artifact=artifact, alias=alias).first()
    return alias_obj.version if alias_obj else None


def _deep_merge(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
