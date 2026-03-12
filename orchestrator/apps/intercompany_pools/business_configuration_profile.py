from __future__ import annotations

from io import BytesIO
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import zipfile

from django.utils import timezone

from apps.artifacts.storage import ArtifactStorageClient
from apps.databases.models import Database


BUSINESS_CONFIGURATION_PROFILE_KEY = "business_configuration_profile"

_XML_CONFIGURATION = "Configuration"
_XML_PROPERTIES = "Properties"
_XML_NAME = "Name"
_XML_SYNONYM = "Synonym"
_XML_VENDOR = "Vendor"
_XML_VERSION = "Version"
_XML_ITEM = "item"
_XML_LANG = "lang"
_XML_CONTENT = "content"


def normalize_business_configuration_profile(raw: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None

    config_name = _trim_string(raw.get("config_name"))
    config_version = _trim_string(raw.get("config_version"))
    if not config_name or not config_version:
        return None

    normalized: dict[str, Any] = {
        "config_name": config_name,
        "config_version": config_version,
    }

    for key in (
        "config_root_name",
        "config_vendor",
        "config_generation_id",
        "config_name_source",
        "verification_status",
        "verification_operation_id",
        "verification_artifact_path",
        "generation_probe_operation_id",
        "observed_metadata_hash",
        "canonical_metadata_hash",
    ):
        value = _trim_string(raw.get(key))
        if value:
            normalized[key] = value

    for key in (
        "verified_at",
        "observed_metadata_fetched_at",
        "generation_probe_requested_at",
        "generation_probe_checked_at",
    ):
        value = _normalize_datetime_token(raw.get(key))
        if value:
            normalized[key] = value

    if "publication_drift" in raw:
        normalized["publication_drift"] = bool(raw.get("publication_drift"))

    return normalized


def get_business_configuration_profile(*, database: Database) -> dict[str, Any] | None:
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    return normalize_business_configuration_profile(
        metadata.get(BUSINESS_CONFIGURATION_PROFILE_KEY)
        if isinstance(metadata.get(BUSINESS_CONFIGURATION_PROFILE_KEY), Mapping)
        else None
    )


def persist_business_configuration_profile(
    *,
    database: Database,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = normalize_business_configuration_profile(profile)
    if normalized is None:
        raise ValueError("business configuration profile requires config_name and config_version")

    metadata = dict(database.metadata or {})
    metadata[BUSINESS_CONFIGURATION_PROFILE_KEY] = normalized
    database.metadata = metadata
    database.save(update_fields=["metadata", "updated_at"])
    return normalized


def mark_business_configuration_publication_state(
    *,
    database: Database,
    observed_metadata_hash: str,
    fetched_at: datetime | None,
    canonical_metadata_hash: str,
) -> dict[str, Any] | None:
    profile = get_business_configuration_profile(database=database)
    if profile is None:
        return None

    updated = dict(profile)
    updated["observed_metadata_hash"] = _trim_string(observed_metadata_hash)
    updated["canonical_metadata_hash"] = _trim_string(canonical_metadata_hash)
    updated["publication_drift"] = (
        bool(updated["observed_metadata_hash"])
        and bool(updated["canonical_metadata_hash"])
        and updated["observed_metadata_hash"] != updated["canonical_metadata_hash"]
    )
    updated["observed_metadata_fetched_at"] = _normalize_datetime_token(fetched_at) or timezone.now().isoformat()
    return persist_business_configuration_profile(database=database, profile=updated)


def parse_business_configuration_profile_xml(raw_xml: str | bytes) -> dict[str, Any]:
    if isinstance(raw_xml, bytes):
        xml_bytes = raw_xml
    else:
        xml_bytes = str(raw_xml or "").encode("utf-8")
    if not xml_bytes.strip():
        raise ValueError("Configuration.xml payload is empty")

    root = ET.fromstring(xml_bytes)
    configuration = _find_direct_child(root, _XML_CONFIGURATION) or root
    properties = _find_direct_child(configuration, _XML_PROPERTIES)
    if properties is None:
        raise ValueError("Configuration.xml does not contain Properties")

    root_name = _find_direct_child_text(properties, _XML_NAME)
    vendor = _find_direct_child_text(properties, _XML_VENDOR)
    version = _find_direct_child_text(properties, _XML_VERSION)
    if not version:
        raise ValueError("Configuration.xml does not contain Version")

    synonym_node = _find_direct_child(properties, _XML_SYNONYM)
    config_name, name_source = _resolve_config_name(synonym_node=synonym_node, root_name=root_name)
    if not config_name:
        raise ValueError("Configuration.xml does not contain business configuration name")

    profile = {
        "config_name": config_name,
        "config_root_name": root_name,
        "config_version": version,
        "config_vendor": vendor,
        "config_name_source": name_source,
        "verification_status": "verified",
        "verified_at": timezone.now().isoformat(),
    }
    return normalize_business_configuration_profile(profile) or profile


def parse_config_generation_id_worker_result(result_data: Mapping[str, Any] | None) -> str | None:
    if not isinstance(result_data, Mapping):
        return None

    for key in ("config_generation_id", "generation_id"):
        value = _trim_string(result_data.get(key))
        if value:
            return value

    stdout = _trim_string(result_data.get("stdout"))
    if stdout:
        first_line = stdout.splitlines()[0].strip()
        return first_line or None
    return None


def load_configuration_xml_from_worker_result(result_data: Mapping[str, Any] | None) -> str | None:
    if not isinstance(result_data, Mapping):
        return None

    for key in ("configuration_xml", "config_xml", "stdout"):
        value = result_data.get(key)
        if isinstance(value, str) and value.strip().startswith("<?xml"):
            return value

    artifact_path = _trim_string(result_data.get("artifact_path"))
    if not artifact_path:
        return None
    return load_configuration_xml_from_artifact_path(artifact_path)


def load_configuration_xml_from_artifact_path(artifact_path: str) -> str:
    token = _trim_string(artifact_path)
    if not token:
        raise ValueError("artifact path is empty")

    if token.startswith("s3://"):
        parsed = urlparse(token)
        storage_key = parsed.path.lstrip("/")
        if not storage_key:
            raise ValueError("artifact path does not contain storage key")
        storage = ArtifactStorageClient()
        response = storage.get_object(storage_key)
        try:
            payload = response.read()
        finally:
            try:
                response.close()
            except Exception:
                pass
            try:
                response.release_conn()
            except Exception:
                pass
        return _load_configuration_xml_from_bytes(payload)

    path = Path(token)
    if path.exists():
        if path.is_dir():
            for candidate in sorted(path.rglob("Configuration.xml")):
                if candidate.is_file():
                    return candidate.read_text(encoding="utf-8-sig")
            raise ValueError(f"Configuration.xml was not found under directory artifact: {token}")
        return _load_configuration_xml_from_bytes(path.read_bytes())

    raise ValueError(f"unsupported artifact path: {token}")


def _load_configuration_xml_from_bytes(payload: bytes) -> str:
    if not payload:
        raise ValueError("artifact payload is empty")
    if zipfile.is_zipfile(BytesIO(payload)):
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            for name in archive.namelist():
                normalized_name = str(name or "").replace("\\", "/").rsplit("/", 1)[-1]
                if normalized_name == "Configuration.xml":
                    return archive.read(name).decode("utf-8-sig")
        raise ValueError("Configuration.xml was not found inside artifact archive")
    return payload.decode("utf-8-sig")


def _resolve_config_name(*, synonym_node: ET.Element | None, root_name: str) -> tuple[str, str]:
    if synonym_node is not None:
        items = [
            item
            for item in list(synonym_node)
            if _local_name(item.tag) == _XML_ITEM
        ]
        for lang in ("ru", ""):
            for item in items:
                item_lang = _find_direct_child_text(item, _XML_LANG)
                item_content = _find_direct_child_text(item, _XML_CONTENT)
                if lang == "ru" and item_lang == "ru" and item_content:
                    return item_content, "synonym_ru"
                if lang == "" and item_content:
                    return item_content, "synonym_any"

    if root_name:
        return root_name, "name"
    return "", ""


def _find_direct_child(parent: ET.Element, local_name: str) -> ET.Element | None:
    for child in list(parent):
        if _local_name(child.tag) == local_name:
            return child
    return None


def _find_direct_child_text(parent: ET.Element, local_name: str) -> str:
    child = _find_direct_child(parent, local_name)
    return _trim_string(child.text if child is not None else "")


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    if ":" in tag:
        return tag.rsplit(":", 1)[-1]
    return tag


def _trim_string(value: object) -> str:
    return str(value or "").strip()


def _normalize_datetime_token(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return _trim_string(value)
