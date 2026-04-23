from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_src_openapi_contract() -> dict[str, Any]:
    contract_path = (
        Path(__file__).resolve().parents[4] / "contracts" / "orchestrator" / "src" / "openapi.yaml"
    )
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _load_src_path_item(filename: str) -> dict[str, Any]:
    path_item = (
        Path(__file__).resolve().parents[4]
        / "contracts"
        / "orchestrator"
        / "src"
        / "paths"
        / filename
    )
    payload = yaml.safe_load(path_item.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _load_src_schema(filename: str) -> dict[str, Any]:
    schema_path = (
        Path(__file__).resolve().parents[4]
        / "contracts"
        / "orchestrator"
        / "src"
        / "components"
        / "schemas"
        / filename
    )
    payload = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _find_parameter(parameters: list[dict[str, Any]], *, name: str, location: str) -> dict[str, Any]:
    for parameter in parameters:
        if parameter.get("name") == name and parameter.get("in") == location:
            return parameter
    raise AssertionError(f"parameter {location}:{name} is missing")


def test_ui_incident_telemetry_paths_are_tracked_in_src_contract() -> None:
    contract = _load_src_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    assert paths.get("/api/v2/ui/incident-telemetry/ingest/") == {
        "$ref": "paths/api_v2_ui_incident-telemetry_ingest_.yaml"
    }
    assert paths.get("/api/v2/ui/incident-telemetry/incidents/") == {
        "$ref": "paths/api_v2_ui_incident-telemetry_incidents_.yaml"
    }
    assert paths.get("/api/v2/ui/incident-telemetry/timeline/") == {
        "$ref": "paths/api_v2_ui_incident-telemetry_timeline_.yaml"
    }


def test_ui_incident_telemetry_ingest_src_contract_requires_tenant_header_and_request_schema() -> None:
    path_item = _load_src_path_item("api_v2_ui_incident-telemetry_ingest_.yaml")
    post_op = path_item.get("post")
    assert isinstance(post_op, dict)
    assert post_op["summary"] == "Ingest redacted UI incident telemetry batch"

    parameters = post_op.get("parameters")
    assert isinstance(parameters, list)
    tenant_header = _find_parameter(parameters, name="X-CC1C-Tenant-ID", location="header")
    assert tenant_header["required"] is True
    assert tenant_header["schema"] == {"type": "string", "format": "uuid"}

    request_body = post_op.get("requestBody")
    assert isinstance(request_body, dict)
    assert request_body["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/UiIncidentTelemetryIngestRequest.yaml"
    }

    responses = post_op.get("responses")
    assert isinstance(responses, dict)
    assert responses["202"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/UiIncidentTelemetryIngestResponse.yaml"
    }
    assert responses["404"]["content"]["application/problem+json"]["schema"] == {
        "$ref": "../components/schemas/ProblemDetailsError.yaml"
    }


def test_ui_incident_telemetry_read_surfaces_preserve_machine_readable_filters() -> None:
    expected_query_parameters = {
        "actor_username",
        "end",
        "limit",
        "offset",
        "request_id",
        "route_path",
        "session_id",
        "start",
        "trace_id",
        "ui_action_id",
        "user_id",
    }

    incidents_path = _load_src_path_item("api_v2_ui_incident-telemetry_incidents_.yaml")
    incidents_get = incidents_path.get("get")
    assert isinstance(incidents_get, dict)
    assert incidents_get["summary"] == "List recent UI incident summaries"
    incidents_parameters = incidents_get.get("parameters")
    assert isinstance(incidents_parameters, list)
    assert {
        parameter["name"]
        for parameter in incidents_parameters
        if parameter.get("in") == "query"
    } == expected_query_parameters
    assert _find_parameter(
        incidents_parameters, name="X-CC1C-Tenant-ID", location="header"
    )["required"] is True
    assert incidents_get["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/UiIncidentSummaryListResponse.yaml"
    }
    assert incidents_get["responses"]["403"]["content"]["application/problem+json"]["schema"] == {
        "$ref": "../components/schemas/ProblemDetailsError.yaml"
    }

    timeline_path = _load_src_path_item("api_v2_ui_incident-telemetry_timeline_.yaml")
    timeline_get = timeline_path.get("get")
    assert isinstance(timeline_get, dict)
    assert timeline_get["summary"] == "Get ordered UI incident timeline"
    timeline_parameters = timeline_get.get("parameters")
    assert isinstance(timeline_parameters, list)
    assert {
        parameter["name"]
        for parameter in timeline_parameters
        if parameter.get("in") == "query"
    } == expected_query_parameters
    assert _find_parameter(
        timeline_parameters, name="X-CC1C-Tenant-ID", location="header"
    )["required"] is True
    assert timeline_get["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/UiIncidentTimelineResponse.yaml"
    }


def test_ui_incident_telemetry_src_schemas_cover_summary_and_timeline_contract() -> None:
    ingest_request = _load_src_schema("UiIncidentTelemetryIngestRequest.yaml")
    ingest_properties = ingest_request.get("properties")
    assert isinstance(ingest_properties, dict)
    assert ingest_properties["flush_reason"]["enum"] == [
        "size_threshold",
        "time_threshold",
        "pagehide",
        "shutdown",
        "manual",
    ]
    assert ingest_properties["events"] == {"type": "array", "items": {}}
    assert ingest_request.get("required") == ["batch_id", "events", "flush_reason"]

    summary = _load_src_schema("UiIncidentSummary.yaml")
    summary_properties = summary.get("properties")
    assert isinstance(summary_properties, dict)
    assert summary_properties["release"] == {"$ref": "./UiIncidentRelease.yaml"}
    assert summary_properties["preview"] == {"$ref": "./UiIncidentSummaryPreview.yaml"}

    summary_preview = _load_src_schema("UiIncidentSummaryPreview.yaml")
    summary_preview_properties = summary_preview.get("properties")
    assert isinstance(summary_preview_properties, dict)
    assert {
        "caused_by_ui_action_id",
        "control_id",
        "navigation_mode",
        "oscillating_keys",
        "param_diff",
        "route_writer_owner",
        "surface_id",
        "transition_count",
        "window_ms",
        "write_reason",
        "writer_owners",
    }.issubset(summary_preview_properties)

    timeline_response = _load_src_schema("UiIncidentTimelineResponse.yaml")
    timeline_properties = timeline_response.get("properties")
    assert isinstance(timeline_properties, dict)
    assert timeline_properties["timeline"] == {
        "type": "array",
        "items": {"$ref": "./UiIncidentTimelineEvent.yaml"},
    }
    assert timeline_response.get("required") == ["count", "timeline", "total"]
