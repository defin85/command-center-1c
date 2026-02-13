from __future__ import annotations

from apps.templates.odata_compatibility_preflight import (
    PROFILE_PATH,
    PROFILE_SCHEMA_PATH,
    _load_yaml_file as load_odata_yaml_file,
    _schema_errors as odata_schema_errors,
)
from apps.templates.workflow_decommission_preflight import (
    REGISTRY_PATH,
    REGISTRY_SCHEMA_PATH,
    _load_yaml_file as load_registry_yaml_file,
    _schema_errors as registry_schema_errors,
)


def test_execution_consumers_registry_yaml_matches_schema() -> None:
    registry = load_registry_yaml_file(REGISTRY_PATH)
    schema = load_registry_yaml_file(REGISTRY_SCHEMA_PATH)
    errors = registry_schema_errors(schema=schema, registry=registry)
    assert errors == []


def test_odata_compatibility_profile_yaml_matches_schema() -> None:
    profile = load_odata_yaml_file(PROFILE_PATH)
    schema = load_odata_yaml_file(PROFILE_SCHEMA_PATH)
    errors = odata_schema_errors(schema=schema, payload=profile)
    assert errors == []
