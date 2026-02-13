from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
POOL_WORKFLOW_ARTIFACTS_DIR = (
    REPO_ROOT / "openspec/specs/pool-workflow-execution-core/artifacts"
)

EXECUTION_CONSUMERS_REGISTRY_FILE = "execution-consumers-registry.yaml"
EXECUTION_CONSUMERS_REGISTRY_SCHEMA_FILE = "execution-consumers-registry.schema.yaml"
ODATA_COMPATIBILITY_PROFILE_FILE = "odata-compatibility-profile.yaml"
ODATA_COMPATIBILITY_PROFILE_SCHEMA_FILE = "odata-compatibility-profile.schema.yaml"


def resolve_pool_workflow_artifact_path(filename: str) -> Path:
    return POOL_WORKFLOW_ARTIFACTS_DIR / filename


def resolve_execution_consumers_registry_paths() -> tuple[Path, Path]:
    return (
        resolve_pool_workflow_artifact_path(EXECUTION_CONSUMERS_REGISTRY_FILE),
        resolve_pool_workflow_artifact_path(EXECUTION_CONSUMERS_REGISTRY_SCHEMA_FILE),
    )


def resolve_odata_compatibility_profile_paths() -> tuple[Path, Path]:
    return (
        resolve_pool_workflow_artifact_path(ODATA_COMPATIBILITY_PROFILE_FILE),
        resolve_pool_workflow_artifact_path(ODATA_COMPATIBILITY_PROFILE_SCHEMA_FILE),
    )
