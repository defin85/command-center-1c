from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_openapi_contract() -> dict[str, Any]:
    contract_path = (
        Path(__file__).resolve().parents[4] / "contracts" / "orchestrator" / "openapi.yaml"
    )
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_pool_master_data_paths_and_operation_ids_are_present() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    expected = {
        "/api/v2/pools/master-data/registry/": ("get", "v2_pools_master_data_registry_retrieve"),
        "/api/v2/pools/master-data/parties/": ("get", "v2_pools_master_data_parties_list"),
        "/api/v2/pools/master-data/parties/{id}/": ("get", "v2_pools_master_data_parties_get"),
        "/api/v2/pools/master-data/parties/upsert/": ("post", "v2_pools_master_data_parties_upsert"),
        "/api/v2/pools/master-data/items/": ("get", "v2_pools_master_data_items_list"),
        "/api/v2/pools/master-data/items/{id}/": ("get", "v2_pools_master_data_items_get"),
        "/api/v2/pools/master-data/items/upsert/": ("post", "v2_pools_master_data_items_upsert"),
        "/api/v2/pools/master-data/contracts/": ("get", "v2_pools_master_data_contracts_list"),
        "/api/v2/pools/master-data/contracts/{id}/": ("get", "v2_pools_master_data_contracts_get"),
        "/api/v2/pools/master-data/contracts/upsert/": ("post", "v2_pools_master_data_contracts_upsert"),
        "/api/v2/pools/master-data/tax-profiles/": ("get", "v2_pools_master_data_tax_profiles_list"),
        "/api/v2/pools/master-data/tax-profiles/{id}/": ("get", "v2_pools_master_data_tax_profiles_get"),
        "/api/v2/pools/master-data/tax-profiles/upsert/": ("post", "v2_pools_master_data_tax_profiles_upsert"),
        "/api/v2/pools/master-data/gl-accounts/": ("get", "v2_pools_master_data_gl_accounts_list"),
        "/api/v2/pools/master-data/gl-accounts/{id}/": ("get", "v2_pools_master_data_gl_accounts_get"),
        "/api/v2/pools/master-data/gl-accounts/upsert/": ("post", "v2_pools_master_data_gl_accounts_upsert"),
        "/api/v2/pools/master-data/gl-account-sets/": ("get", "v2_pools_master_data_gl_account_sets_list"),
        "/api/v2/pools/master-data/gl-account-sets/{id}/": ("get", "v2_pools_master_data_gl_account_sets_get"),
        "/api/v2/pools/master-data/gl-account-sets/upsert/": (
            "post",
            "v2_pools_master_data_gl_account_sets_upsert",
        ),
        "/api/v2/pools/master-data/gl-account-sets/{id}/publish/": (
            "post",
            "v2_pools_master_data_gl_account_sets_publish",
        ),
        "/api/v2/pools/master-data/bindings/": ("get", "v2_pools_master_data_bindings_list"),
        "/api/v2/pools/master-data/bindings/{id}/": ("get", "v2_pools_master_data_bindings_get"),
        "/api/v2/pools/master-data/bindings/upsert/": ("post", "v2_pools_master_data_bindings_upsert"),
        "/api/v2/pools/master-data/bootstrap-import/preflight/": (
            "post",
            "v2_pools_master_data_bootstrap_import_preflight",
        ),
        "/api/v2/pools/master-data/bootstrap-import/jobs/": (
            "post",
            "v2_pools_master_data_bootstrap_import_jobs_create",
        ),
        "/api/v2/pools/master-data/bootstrap-import/jobs/{id}/": (
            "get",
            "v2_pools_master_data_bootstrap_import_jobs_get",
        ),
        "/api/v2/pools/master-data/bootstrap-import/jobs/{id}/cancel/": (
            "post",
            "v2_pools_master_data_bootstrap_import_jobs_cancel",
        ),
        "/api/v2/pools/master-data/bootstrap-import/jobs/{id}/retry-failed-chunks/": (
            "post",
            "v2_pools_master_data_bootstrap_import_jobs_retry_failed_chunks",
        ),
    }

    for path, (method, operation_id) in expected.items():
        path_item = paths.get(path)
        assert isinstance(path_item, dict), f"path missing: {path}"
        operation = path_item.get(method)
        assert isinstance(operation, dict), f"{method} operation missing for {path}"
        assert operation.get("operationId") == operation_id


def test_pool_master_data_list_contract_has_pagination_and_problem_details() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    list_paths = [
        "/api/v2/pools/master-data/parties/",
        "/api/v2/pools/master-data/items/",
        "/api/v2/pools/master-data/contracts/",
        "/api/v2/pools/master-data/tax-profiles/",
        "/api/v2/pools/master-data/gl-accounts/",
        "/api/v2/pools/master-data/gl-account-sets/",
        "/api/v2/pools/master-data/bindings/",
    ]

    for path in list_paths:
        path_item = paths.get(path)
        assert isinstance(path_item, dict)
        get_op = path_item.get("get")
        assert isinstance(get_op, dict)

        parameters = get_op.get("parameters")
        assert isinstance(parameters, list)
        names = {str(item.get("name")) for item in parameters if isinstance(item, dict)}
        assert {"limit", "offset"}.issubset(names)

        responses = get_op.get("responses")
        assert isinstance(responses, dict)
        assert {"200", "400", "401"}.issubset(set(responses.keys()))
        bad_request = responses["400"]["content"]["application/problem+json"]["schema"]["$ref"]
        assert bad_request == "#/components/schemas/ProblemDetailsError"


def test_pool_master_data_bootstrap_job_list_contract_has_pagination_and_problem_details() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    path_item = paths.get("/api/v2/pools/master-data/bootstrap-import/jobs/")
    assert isinstance(path_item, dict)

    get_op = path_item.get("get")
    assert isinstance(get_op, dict)
    assert get_op.get("operationId") == "v2_pools_master_data_bootstrap_import_jobs_list"

    parameters = get_op.get("parameters")
    assert isinstance(parameters, list)
    names = {str(item.get("name")) for item in parameters if isinstance(item, dict)}
    assert {"limit", "offset"}.issubset(names)

    responses = get_op.get("responses")
    assert isinstance(responses, dict)
    assert {"200", "400", "401"}.issubset(set(responses.keys()))
    bad_request = responses["400"]["content"]["application/problem+json"]["schema"]["$ref"]
    assert bad_request == "#/components/schemas/ProblemDetailsError"
