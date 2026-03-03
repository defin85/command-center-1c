from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from random import Random
from typing import Any


READINESS_GATE_SCHEMA_VERSION = "pool_master_data_sync_readiness_gate_report.v1"
READINESS_GATE_KEYS = ("load", "replay_consistency", "failover_restart", "security")
REQUIRED_ORR_SIGNOFF_ROLES = ("platform", "security", "operations")

READINESS_GATE_THRESHOLDS: dict[str, dict[str, dict[str, Any]]] = {
    "load": {
        "reconcile_window_p95_seconds": {"operator": "<=", "value": 120.0},
        "reconcile_window_p99_seconds": {"operator": "<=", "value": 150.0},
        "coverage_ratio": {"operator": ">=", "value": 0.995},
        "partial_outcome_rate": {"operator": "<=", "value": 0.05},
    },
    "replay_consistency": {
        "lost_events_total": {"operator": "==", "value": 0.0},
        "duplicate_apply_total": {"operator": "==", "value": 0.0},
        "deterministic_replay_match_ratio": {"operator": "==", "value": 1.0},
    },
    "failover_restart": {
        "checkpoint_monotonicity_violations": {"operator": "==", "value": 0.0},
        "ack_before_commit_violations": {"operator": "==", "value": 0.0},
        "worker_recovery_to_steady_state_seconds": {"operator": "<=", "value": 60.0},
    },
    "security": {
        "secrets_exposed_in_diagnostics": {"operator": "==", "value": 0.0},
        "secrets_exposed_in_last_error": {"operator": "==", "value": 0.0},
        "redaction_test_failures": {"operator": "==", "value": 0.0},
    },
}


def _utc_now_rfc3339() -> str:
    now_utc = datetime.now(dt_timezone.utc).replace(microsecond=0)
    return now_utc.isoformat().replace("+00:00", "Z")


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    ordered = sorted(float(value) for value in values)
    q = max(0.0, min(float(percentile), 100.0))
    rank = (len(ordered) - 1) * (q / 100.0)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = rank - lower_index
    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    return lower_value + (upper_value - lower_value) * weight


def run_nominal_load_model(
    *,
    windows: int = 40,
    scopes_per_window: int = 720,
    random_seed: int = 20260303,
    base_latency_seconds: float = 78.0,
    jitter_seconds: float = 16.0,
    tail_probability: float = 0.00005,
    tail_extra_seconds: float = 38.0,
    deadline_seconds: float = 120.0,
) -> dict[str, float]:
    safe_windows = max(1, int(windows))
    safe_scopes = max(1, int(scopes_per_window))
    safe_base_latency = max(0.0, float(base_latency_seconds))
    safe_jitter = max(0.0, float(jitter_seconds))
    safe_tail_probability = max(0.0, min(float(tail_probability), 1.0))
    safe_tail_extra = max(0.0, float(tail_extra_seconds))
    safe_deadline = max(1.0, float(deadline_seconds))

    rng = Random(int(random_seed))
    window_durations: list[float] = []
    window_coverages: list[float] = []
    partial_windows = 0

    for _ in range(safe_windows):
        latencies: list[float] = []
        on_time = 0
        for _scope in range(safe_scopes):
            latency = safe_base_latency + (rng.random() * safe_jitter)
            if rng.random() < safe_tail_probability:
                latency += safe_tail_extra
            latencies.append(latency)
            if latency <= safe_deadline:
                on_time += 1

        coverage = float(on_time) / float(safe_scopes)
        if coverage < 1.0:
            partial_windows += 1
        window_coverages.append(coverage)
        window_durations.append(max(latencies))

    coverage_ratio = sum(window_coverages) / float(len(window_coverages))
    partial_outcome_rate = float(partial_windows) / float(safe_windows)

    return {
        "reconcile_window_p95_seconds": round(_percentile(window_durations, 95.0), 6),
        "reconcile_window_p99_seconds": round(_percentile(window_durations, 99.0), 6),
        "coverage_ratio": round(coverage_ratio, 9),
        "partial_outcome_rate": round(partial_outcome_rate, 9),
        "model_windows": float(safe_windows),
        "model_scopes_per_window": float(safe_scopes),
    }


def _compare_threshold(
    *,
    measured_value: float,
    operator: str,
    threshold_value: float,
) -> bool:
    if operator == "<=":
        return measured_value <= threshold_value
    if operator == ">=":
        return measured_value >= threshold_value
    if operator == "==":
        return abs(measured_value - threshold_value) <= 1e-9
    raise ValueError(f"Unsupported threshold operator: {operator}")


def evaluate_gate_thresholds(
    *,
    gate_key: str,
    measured_values: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    thresholds = READINESS_GATE_THRESHOLDS[gate_key]
    checks: list[dict[str, Any]] = []
    gate_failed = False

    for metric_name, rule in thresholds.items():
        operator = str(rule["operator"])
        threshold_value = float(rule["value"])
        raw_measured = measured_values.get(metric_name)

        if raw_measured is None:
            checks.append(
                {
                    "metric": metric_name,
                    "status": "missing",
                    "operator": operator,
                    "threshold_value": threshold_value,
                    "measured_value": None,
                }
            )
            gate_failed = True
            continue

        try:
            measured_value = float(raw_measured)
        except (TypeError, ValueError):
            checks.append(
                {
                    "metric": metric_name,
                    "status": "invalid",
                    "operator": operator,
                    "threshold_value": threshold_value,
                    "measured_value": raw_measured,
                }
            )
            gate_failed = True
            continue

        passed = _compare_threshold(
            measured_value=measured_value,
            operator=operator,
            threshold_value=threshold_value,
        )
        checks.append(
            {
                "metric": metric_name,
                "status": "pass" if passed else "fail",
                "operator": operator,
                "threshold_value": threshold_value,
                "measured_value": measured_value,
            }
        )
        if not passed:
            gate_failed = True

    return ("fail" if gate_failed else "pass"), checks


def build_readiness_gate_report(
    *,
    measured_values_by_gate: dict[str, dict[str, Any]],
    evidence_refs_by_gate: dict[str, list[dict[str, Any]]],
    signoff_by_role: dict[str, str],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    report_gates: dict[str, Any] = {}

    for gate_key in READINESS_GATE_KEYS:
        measured_values = dict(measured_values_by_gate.get(gate_key) or {})
        gate_status, checks = evaluate_gate_thresholds(
            gate_key=gate_key,
            measured_values=measured_values,
        )
        report_gates[gate_key] = {
            "status": gate_status,
            "measured_values": measured_values,
            "thresholds": dict(READINESS_GATE_THRESHOLDS[gate_key]),
            "checks": checks,
            "evidence_refs": list(evidence_refs_by_gate.get(gate_key) or []),
        }

    signed_off_by: dict[str, str] = {}
    missing_roles: list[str] = []
    for role in REQUIRED_ORR_SIGNOFF_ROLES:
        actor = str((signoff_by_role or {}).get(role) or "").strip()
        signed_off_by[role] = actor
        if not actor:
            missing_roles.append(role)

    orr_status = "complete" if not missing_roles else "missing"
    overall_status = "pass"
    if any(report_gates[key]["status"] != "pass" for key in READINESS_GATE_KEYS):
        overall_status = "fail"
    if orr_status != "complete":
        overall_status = "fail"

    return {
        "schema_version": READINESS_GATE_SCHEMA_VERSION,
        "generated_at_utc": str(generated_at_utc or _utc_now_rfc3339()),
        "overall_status": overall_status,
        "gates": report_gates,
        "orr_signoff": {
            "required_roles": list(REQUIRED_ORR_SIGNOFF_ROLES),
            "signed_off_by": signed_off_by,
            "missing_roles": missing_roles,
            "status": orr_status,
        },
    }


def validate_readiness_gate_report_shape(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    payload = report if isinstance(report, dict) else {}

    if str(payload.get("schema_version") or "") != READINESS_GATE_SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if not str(payload.get("generated_at_utc") or ""):
        errors.append("generated_at_utc is required")
    if str(payload.get("overall_status") or "") not in {"pass", "fail"}:
        errors.append("overall_status must be pass|fail")

    gates = payload.get("gates")
    if not isinstance(gates, dict):
        errors.append("gates section is required")
    else:
        for gate_key in READINESS_GATE_KEYS:
            gate_payload = gates.get(gate_key)
            if not isinstance(gate_payload, dict):
                errors.append(f"gates.{gate_key} is required")
                continue
            if str(gate_payload.get("status") or "") not in {"pass", "fail"}:
                errors.append(f"gates.{gate_key}.status must be pass|fail")
            if not isinstance(gate_payload.get("measured_values"), dict):
                errors.append(f"gates.{gate_key}.measured_values is required")
            if not isinstance(gate_payload.get("thresholds"), dict):
                errors.append(f"gates.{gate_key}.thresholds is required")
            if not isinstance(gate_payload.get("checks"), list):
                errors.append(f"gates.{gate_key}.checks is required")
            if not isinstance(gate_payload.get("evidence_refs"), list):
                errors.append(f"gates.{gate_key}.evidence_refs is required")

    orr_signoff = payload.get("orr_signoff")
    if not isinstance(orr_signoff, dict):
        errors.append("orr_signoff is required")
    else:
        required_roles = orr_signoff.get("required_roles")
        if list(required_roles or []) != list(REQUIRED_ORR_SIGNOFF_ROLES):
            errors.append("orr_signoff.required_roles mismatch")
        if not isinstance(orr_signoff.get("signed_off_by"), dict):
            errors.append("orr_signoff.signed_off_by is required")
        if str(orr_signoff.get("status") or "") not in {"complete", "missing"}:
            errors.append("orr_signoff.status must be complete|missing")
        if not isinstance(orr_signoff.get("missing_roles"), list):
            errors.append("orr_signoff.missing_roles is required")

    return errors
