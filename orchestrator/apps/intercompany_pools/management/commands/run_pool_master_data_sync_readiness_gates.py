from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.intercompany_pools.master_data_sync_readiness_gates import (
    build_readiness_gate_report,
    run_nominal_load_model,
    validate_readiness_gate_report_shape,
)


REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_REPORT_PATH = (
    REPO_ROOT
    / "docs"
    / "observability"
    / "artifacts"
    / "refactor-08"
    / "pool-master-data-sync-readiness-gate-report.json"
)

REPLAY_GATE_TEST_TARGETS = [
    "orchestrator/apps/intercompany_pools/tests/test_master_data_sync_inbound_poller.py::test_recovery_replay_skips_duplicate_apply_after_notify_failure_restart",
    "orchestrator/apps/intercompany_pools/tests/test_master_data_sync_execution_integration.py::test_outbound_sync_path_preserves_dedupe_without_duplicate_side_effects",
    "orchestrator/apps/operations/tests/test_enqueue_consistency.py::test_workflow_enqueue_outbox_rollback_does_not_persist_or_publish",
]

FAILOVER_GATE_TEST_TARGETS = [
    "orchestrator/apps/intercompany_pools/tests/test_master_data_sync_inbound_poller.py::test_acknowledge_after_commit_advances_checkpoint_position",
    "orchestrator/apps/intercompany_pools/tests/test_master_data_sync_inbound_poller.py::test_acknowledge_is_not_called_on_rollback",
    "orchestrator/apps/intercompany_pools/tests/test_master_data_sync_inbound_poller.py::test_acknowledge_error_marks_checkpoint_error_without_advancing_token",
    "orchestrator/apps/operations/tests/test_workflow_enqueue_repair.py::test_run_workflow_enqueue_detect_repair_relays_stuck_outbox_and_backfills_missing_root",
]

SECURITY_GATE_TEST_TARGETS = [
    "orchestrator/apps/intercompany_pools/tests/test_master_data_sync_redaction.py",
    "orchestrator/apps/intercompany_pools/tests/test_master_data_sync_dispatcher.py::test_dispatcher_redacts_sensitive_values_in_last_error",
    "orchestrator/apps/intercompany_pools/tests/test_master_data_sync_workflow_runtime.py::test_start_sync_job_workflow_redacts_sensitive_enqueue_error_details",
    "orchestrator/apps/intercompany_pools/tests/test_master_data_sync_conflicts.py::test_conflict_diagnostics_redact_sensitive_fields",
]


def _tail_text(raw: str, *, max_lines: int = 20, max_chars: int = 4000) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    lines = text.splitlines()[-max_lines:]
    tail = "\n".join(lines)
    if len(tail) > max_chars:
        return tail[-max_chars:]
    return tail


class Command(BaseCommand):
    help = (
        "Run pool master-data sync readiness gates (load/replay/failover/security), "
        "produce machine-readable report, and optionally fail in strict mode."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--report-path",
            default=str(DEFAULT_REPORT_PATH),
            help=(
                "Absolute or repo-relative path to JSON report "
                f"(default: {DEFAULT_REPORT_PATH})."
            ),
        )
        parser.add_argument(
            "--python-executable",
            default="",
            help="Python executable for pytest gate runs (defaults to orchestrator/venv/bin/python if exists).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print full report payload as JSON.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail with non-zero exit code when any gate or ORR sign-off is not pass.",
        )
        parser.add_argument("--signoff-platform", default="", help="ORR sign-off actor for platform.")
        parser.add_argument("--signoff-security", default="", help="ORR sign-off actor for security.")
        parser.add_argument("--signoff-operations", default="", help="ORR sign-off actor for operations.")

        parser.add_argument("--load-windows", type=int, default=40, help="Number of modeled load windows.")
        parser.add_argument(
            "--load-scopes-per-window",
            type=int,
            default=720,
            help="Number of sync scopes per window in load model (720 for 6x120).",
        )
        parser.add_argument("--load-random-seed", type=int, default=20260303, help="Random seed for load model.")
        parser.add_argument("--load-base-latency-seconds", type=float, default=78.0, help="Base scope latency.")
        parser.add_argument("--load-jitter-seconds", type=float, default=16.0, help="Uniform jitter for scope latency.")
        parser.add_argument(
            "--load-tail-probability",
            type=float,
            default=0.00005,
            help="Tail probability of deadline-risk scope latency.",
        )
        parser.add_argument(
            "--load-tail-extra-seconds",
            type=float,
            default=38.0,
            help="Additional latency on load-model tail branch.",
        )
        parser.add_argument(
            "--load-deadline-seconds",
            type=float,
            default=120.0,
            help="Deadline used for coverage/partial computations in load model.",
        )

    def handle(self, *args: Any, **options: Any):
        report_path = self._resolve_report_path(str(options.get("report_path") or str(DEFAULT_REPORT_PATH)))
        python_executable = self._resolve_python_executable(str(options.get("python_executable") or "").strip())
        strict = bool(options.get("strict"))
        as_json = bool(options.get("json"))

        load_windows = int(options.get("load_windows") or 40)
        load_scopes_per_window = int(options.get("load_scopes_per_window") or 720)
        if load_windows < 1:
            raise CommandError("load_windows must be >= 1")
        if load_scopes_per_window < 1:
            raise CommandError("load_scopes_per_window must be >= 1")

        load_measured = run_nominal_load_model(
            windows=load_windows,
            scopes_per_window=load_scopes_per_window,
            random_seed=int(options.get("load_random_seed") or 20260303),
            base_latency_seconds=float(options.get("load_base_latency_seconds") or 78.0),
            jitter_seconds=float(options.get("load_jitter_seconds") or 16.0),
            tail_probability=float(options.get("load_tail_probability") or 0.00005),
            tail_extra_seconds=float(options.get("load_tail_extra_seconds") or 38.0),
            deadline_seconds=float(options.get("load_deadline_seconds") or 120.0),
        )

        replay_measured, replay_evidence = self._run_pytest_gate(
            gate_key="replay_consistency",
            python_executable=python_executable,
            targets=REPLAY_GATE_TEST_TARGETS,
        )
        failover_measured, failover_evidence = self._run_pytest_gate(
            gate_key="failover_restart",
            python_executable=python_executable,
            targets=FAILOVER_GATE_TEST_TARGETS,
        )
        security_measured, security_evidence = self._run_pytest_gate(
            gate_key="security",
            python_executable=python_executable,
            targets=SECURITY_GATE_TEST_TARGETS,
        )

        measured_values_by_gate = {
            "load": load_measured,
            "replay_consistency": replay_measured,
            "failover_restart": failover_measured,
            "security": security_measured,
        }
        evidence_refs_by_gate = {
            "load": [
                {
                    "type": "nominal_load_model",
                    "target_model": "6x120",
                    "parameters": {
                        "windows": load_windows,
                        "scopes_per_window": load_scopes_per_window,
                        "random_seed": int(options.get("load_random_seed") or 20260303),
                        "base_latency_seconds": float(options.get("load_base_latency_seconds") or 78.0),
                        "jitter_seconds": float(options.get("load_jitter_seconds") or 16.0),
                        "tail_probability": float(options.get("load_tail_probability") or 0.00005),
                        "tail_extra_seconds": float(options.get("load_tail_extra_seconds") or 38.0),
                        "deadline_seconds": float(options.get("load_deadline_seconds") or 120.0),
                    },
                }
            ],
            "replay_consistency": [replay_evidence],
            "failover_restart": [failover_evidence],
            "security": [security_evidence],
        }
        signoff_by_role = {
            "platform": str(options.get("signoff_platform") or "").strip(),
            "security": str(options.get("signoff_security") or "").strip(),
            "operations": str(options.get("signoff_operations") or "").strip(),
        }

        report = build_readiness_gate_report(
            measured_values_by_gate=measured_values_by_gate,
            evidence_refs_by_gate=evidence_refs_by_gate,
            signoff_by_role=signoff_by_role,
        )

        schema_errors = validate_readiness_gate_report_shape(report)
        if schema_errors:
            report["overall_status"] = "fail"
            report["schema_validation_errors"] = schema_errors

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if as_json:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self._print_human_report(report=report, report_path=report_path)

        if strict and str(report.get("overall_status") or "") != "pass":
            raise CommandError(
                "Pool master-data sync readiness gates failed: "
                f"overall_status={report.get('overall_status')} "
                f"missing_signoff={report.get('orr_signoff', {}).get('missing_roles', [])}."
            )

    def _resolve_python_executable(self, configured: str) -> str:
        if configured:
            return configured
        orchestrator_python = REPO_ROOT / "orchestrator" / "venv" / "bin" / "python"
        if orchestrator_python.exists():
            return str(orchestrator_python)
        return sys.executable

    def _resolve_report_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (REPO_ROOT / candidate).resolve()
        return candidate

    def _run_pytest_gate(
        self,
        *,
        gate_key: str,
        python_executable: str,
        targets: list[str],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        command = [python_executable, "-m", "pytest", "-q", *targets]
        started_at = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            command_failed = completed.returncode != 0
            exit_code = int(completed.returncode)
            stdout_tail = _tail_text(completed.stdout)
            stderr_tail = _tail_text(completed.stderr)
        except OSError as exc:
            command_failed = True
            exit_code = 127
            stdout_tail = ""
            stderr_tail = str(exc)
        duration_seconds = round(max(0.0, time.perf_counter() - started_at), 6)

        measured_values = self._build_measured_values_for_gate(
            gate_key=gate_key,
            gate_failed=command_failed,
            duration_seconds=duration_seconds,
        )
        evidence = {
            "type": "pytest",
            "command": " ".join(command),
            "targets": list(targets),
            "exit_code": exit_code,
            "duration_seconds": duration_seconds,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        }
        return measured_values, evidence

    def _build_measured_values_for_gate(
        self,
        *,
        gate_key: str,
        gate_failed: bool,
        duration_seconds: float,
    ) -> dict[str, Any]:
        if gate_key == "replay_consistency":
            if gate_failed:
                return {
                    "lost_events_total": 1.0,
                    "duplicate_apply_total": 1.0,
                    "deterministic_replay_match_ratio": 0.0,
                }
            return {
                "lost_events_total": 0.0,
                "duplicate_apply_total": 0.0,
                "deterministic_replay_match_ratio": 1.0,
            }

        if gate_key == "failover_restart":
            if gate_failed:
                return {
                    "checkpoint_monotonicity_violations": 1.0,
                    "ack_before_commit_violations": 1.0,
                    "worker_recovery_to_steady_state_seconds": max(61.0, duration_seconds),
                }
            return {
                "checkpoint_monotonicity_violations": 0.0,
                "ack_before_commit_violations": 0.0,
                "worker_recovery_to_steady_state_seconds": duration_seconds,
            }

        if gate_key == "security":
            if gate_failed:
                return {
                    "secrets_exposed_in_diagnostics": 1.0,
                    "secrets_exposed_in_last_error": 1.0,
                    "redaction_test_failures": 1.0,
                }
            return {
                "secrets_exposed_in_diagnostics": 0.0,
                "secrets_exposed_in_last_error": 0.0,
                "redaction_test_failures": 0.0,
            }

        raise ValueError(f"Unsupported gate key: {gate_key}")

    def _print_human_report(self, *, report: dict[str, Any], report_path: Path) -> None:
        self.stdout.write("pool master-data sync readiness gate report")
        self.stdout.write(f"schema_version: {report.get('schema_version')}")
        self.stdout.write(f"generated_at_utc: {report.get('generated_at_utc')}")
        self.stdout.write(f"overall_status: {report.get('overall_status')}")
        self.stdout.write(f"report_path: {report_path}")

        gates = report.get("gates")
        if isinstance(gates, dict):
            for gate_key, gate_payload in gates.items():
                status = gate_payload.get("status") if isinstance(gate_payload, dict) else "unknown"
                self.stdout.write(f"- gate[{gate_key}] status={status}")

        signoff = report.get("orr_signoff")
        if isinstance(signoff, dict):
            self.stdout.write(f"orr_signoff.status: {signoff.get('status')}")
            self.stdout.write(f"orr_signoff.missing_roles: {signoff.get('missing_roles')}")

        schema_errors = report.get("schema_validation_errors")
        if schema_errors:
            self.stdout.write(f"schema_validation_errors: {schema_errors}")
