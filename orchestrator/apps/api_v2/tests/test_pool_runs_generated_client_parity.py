from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_openapi_contract() -> dict[str, Any]:
    contract_path = _repo_root() / "contracts" / "orchestrator" / "openapi.yaml"
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _schema(contract: dict[str, Any], name: str) -> dict[str, Any]:
    components = contract.get("components")
    assert isinstance(components, dict)
    schemas = components.get("schemas")
    assert isinstance(schemas, dict)
    value = schemas.get(name)
    assert isinstance(value, dict), f"schema not found: {name}"
    return value


def _generated_model_fields(filename: str) -> set[str]:
    model_path = _repo_root() / "frontend" / "src" / "api" / "generated" / "model" / filename
    content = model_path.read_text(encoding="utf-8")
    return set(re.findall(r"^\s{2}([a-zA-Z0-9_]+)\??:", content, flags=re.MULTILINE))


def test_generated_v2_has_safe_command_operations_from_openapi() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)
    assert "/api/v2/pools/runs/{run_id}/confirm-publication/" in paths
    assert "/api/v2/pools/runs/{run_id}/abort-publication/" in paths

    generated_v2_path = _repo_root() / "frontend" / "src" / "api" / "generated" / "v2" / "v2.ts"
    content = generated_v2_path.read_text(encoding="utf-8")

    assert "postPoolsRunsConfirmPublication" in content
    assert "postPoolsRunsAbortPublication" in content
    assert "url: `/api/v2/pools/runs/${runId}/confirm-publication/`" in content
    assert "url: `/api/v2/pools/runs/${runId}/abort-publication/`" in content


def test_generated_models_cover_contract_pool_runs_schemas() -> None:
    contract = _load_openapi_contract()

    checks = {
        "PoolRun": "poolRun.ts",
        "PoolPublicationAttempt": "poolPublicationAttempt.ts",
        "PoolRunSafeCommandResponse": "poolRunSafeCommandResponse.ts",
        "PoolRunSafeCommandConflict": "poolRunSafeCommandConflict.ts",
        "PoolRunProvenance": "poolRunProvenance.ts",
        "PoolRunRetryChainAttempt": "poolRunRetryChainAttempt.ts",
    }

    for schema_name, model_file in checks.items():
        schema = _schema(contract, schema_name)
        properties = schema.get("properties")
        assert isinstance(properties, dict)
        contract_fields = set(properties.keys())
        generated_fields = _generated_model_fields(model_file)
        assert contract_fields.issubset(generated_fields), (
            f"{schema_name} fields missing in generated model {model_file}: "
            f"{sorted(contract_fields - generated_fields)}"
        )


def test_generated_retry_chain_attempt_kind_enum_matches_contract() -> None:
    contract = _load_openapi_contract()
    retry_chain_schema = _schema(contract, "PoolRunRetryChainAttempt")
    attempt_kind = retry_chain_schema.get("properties", {}).get("attempt_kind")
    assert isinstance(attempt_kind, dict)
    assert attempt_kind.get("enum") == ["initial", "retry"]

    enum_path = (
        _repo_root()
        / "frontend"
        / "src"
        / "api"
        / "generated"
        / "model"
        / "poolRunRetryChainAttemptAttemptKind.ts"
    )
    enum_content = enum_path.read_text(encoding="utf-8")
    assert 'initial: "initial"' in enum_content
    assert 'retry: "retry"' in enum_content
