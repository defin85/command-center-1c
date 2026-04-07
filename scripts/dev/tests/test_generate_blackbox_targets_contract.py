from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/dev/generate-blackbox-targets.sh"


class GenerateBlackboxTargetsContractTests(unittest.TestCase):
    def _run_script(self, env_file_text: str) -> str:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            script_path = project_root / "scripts/dev/generate-blackbox-targets.sh"
            targets_dir = project_root / "infrastructure/monitoring/prometheus/targets"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            targets_dir.mkdir(parents=True, exist_ok=True)
            script_path.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
            script_path.chmod(0o755)
            (project_root / ".env.local").write_text(env_file_text, encoding="utf-8")

            subprocess.run(
                ["bash", str(script_path)],
                check=True,
                cwd=project_root,
                capture_output=True,
                text=True,
            )

            return (targets_dir / "blackbox_http.yml").read_text(encoding="utf-8")

    def test_localhost_frontend_target_is_normalized_to_ipv4_loopback(self) -> None:
        http_targets = self._run_script(
            textwrap.dedent(
                """\
                RAS_SERVER_ADDR=192.168.32.143:1645
                CC1C_BASE_HOST=localhost
                FRONTEND_PORT=15173
                """
            )
        )

        self.assertIn('- "http://127.0.0.1:15173/"', http_targets)
        self.assertIn('frontend_target: "http://127.0.0.1:15173/"', http_targets)

    def test_non_localhost_frontend_target_is_preserved(self) -> None:
        http_targets = self._run_script(
            textwrap.dedent(
                """\
                RAS_SERVER_ADDR=192.168.32.143:1645
                FRONTEND_URL=http://host.docker.internal:15173
                """
            )
        )

        self.assertIn('- "http://host.docker.internal:15173/"', http_targets)
        self.assertIn('frontend_target: "http://host.docker.internal:15173/"', http_targets)


if __name__ == "__main__":
    unittest.main()
