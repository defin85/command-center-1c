import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[3]


class LifecycleWorkerEnvContractTests(unittest.TestCase):
    def _write_fake_worker_binary(self, bin_dir: Path, capture_file: Path) -> None:
        binary_path = bin_dir / "cc1c-worker"
        binary_path.write_text(
            textwrap.dedent(
                """\
                #!/bin/bash
                printf 'ENABLE_GO_SCHEDULER=%s\n' "${ENABLE_GO_SCHEDULER:-}" >> "${CC1C_CAPTURE_FILE}"
                printf 'WORKER_STREAM_NAME=%s\n' "${WORKER_STREAM_NAME:-}" >> "${CC1C_CAPTURE_FILE}"
                printf 'WORKER_CONSUMER_GROUP=%s\n' "${WORKER_CONSUMER_GROUP:-}" >> "${CC1C_CAPTURE_FILE}"
                sleep 5
                """
            ),
            encoding="utf-8",
        )
        binary_path.chmod(binary_path.stat().st_mode | stat.S_IXUSR)
        capture_file.write_text("", encoding="utf-8")

    def _start_go_service_and_capture(self, service_name: str, inherited_scheduler: str | None) -> str:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            bin_dir = tmp_path / "bin"
            log_dir = tmp_path / "logs"
            pid_dir = tmp_path / "pids"
            capture_file = tmp_path / "capture.txt"
            bin_dir.mkdir()
            log_dir.mkdir()
            pid_dir.mkdir()
            self._write_fake_worker_binary(bin_dir, capture_file)

            scheduler_export = ""
            if inherited_scheduler is not None:
                scheduler_export = f'export ENABLE_GO_SCHEDULER="{inherited_scheduler}"\n'

            script = textwrap.dedent(
                f"""\
                set -euo pipefail
                export CC1C_LIB_SKIP_PROMPTS=1
                source "{ROOT / 'scripts/lib/init.sh'}" >/dev/null
                PROJECT_ROOT="{ROOT}"
                GO_SERVICES_DIR="$PROJECT_ROOT/go-services"
                BIN_DIR="{bin_dir}"
                LOGS_DIR="{log_dir}"
                PIDS_DIR="{pid_dir}"
                SKIP_GO_REBUILD=true
                export CC1C_CAPTURE_FILE="{capture_file}"
                {scheduler_export}\
                _start_go_service "{service_name}"
                pid="$LAST_SERVICE_PID"
                sleep 1
                kill "$pid" >/dev/null 2>&1 || true
                wait "$pid" 2>/dev/null || true
                """
            )

            subprocess.run(
                ["bash", "-lc", script],
                check=True,
                cwd=ROOT,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
            )

            return capture_file.read_text(encoding="utf-8")

    def test_regular_worker_masks_inherited_scheduler_flag(self) -> None:
        capture = self._start_go_service_and_capture("worker", inherited_scheduler="true")

        self.assertIn("ENABLE_GO_SCHEDULER=false", capture)
        self.assertIn("WORKER_STREAM_NAME=", capture)

    def test_worker_workflows_keeps_scheduler_default_on_shared_binary(self) -> None:
        capture = self._start_go_service_and_capture("worker-workflows", inherited_scheduler=None)

        self.assertIn("ENABLE_GO_SCHEDULER=true", capture)
        self.assertIn("WORKER_STREAM_NAME=commands:worker:workflows", capture)
        self.assertIn("WORKER_CONSUMER_GROUP=worker-workflows", capture)


class RestartAllWorkerWorkflowsAliasTests(unittest.TestCase):
    def test_single_service_restart_uses_worker_binary_alias_wiring(self) -> None:
        script_text = (ROOT / "scripts/dev/restart-all.sh").read_text(encoding="utf-8")

        self.assertIn('rebuild_target=$(resolve_go_service_binary_target "$SINGLE_SERVICE")', script_text)
        self.assertIn('status=$(detect_go_service_changes "$rebuild_target")', script_text)
        self.assertIn('REBUILD_SERVICES+=("$rebuild_target")', script_text)
        self.assertIn('bash "$PROJECT_ROOT/scripts/build.sh" --service="$rebuild_target"', script_text)


if __name__ == "__main__":
    unittest.main()
