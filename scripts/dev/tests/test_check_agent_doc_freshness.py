import importlib.util
import io
from contextlib import redirect_stdout
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "check-agent-doc-freshness.py"
MODULE_SPEC = importlib.util.spec_from_file_location(
    "check_agent_doc_freshness",
    MODULE_PATH,
)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module from {MODULE_PATH}")

CHECKER = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(CHECKER)


class RequireLineWithTokensTests(unittest.TestCase):
    def test_passes_when_all_tokens_share_one_line(self) -> None:
        errors: list[str] = []

        CHECKER.require_line_with_tokens(
            errors,
            "| `frontend` | react/vite | frontend/src/main.tsx |",
            CHECKER.ROOT / "docs/agent/ARCHITECTURE_MAP.md",
            "frontend architecture row",
            ("`frontend`", "react/vite", "frontend/src/main.tsx"),
        )

        self.assertEqual(errors, [])

    def test_fails_when_tokens_are_split_across_lines(self) -> None:
        errors: list[str] = []

        CHECKER.require_line_with_tokens(
            errors,
            "`frontend`\nreact/vite\nfrontend/src/main.tsx\n",
            CHECKER.ROOT / "docs/agent/ARCHITECTURE_MAP.md",
            "frontend architecture row",
            ("`frontend`", "react/vite", "frontend/src/main.tsx"),
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("frontend architecture row", errors[0])


class CheckRuntimeDocSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = [
            {
                "runtime": "frontend",
                "stack": "react/vite",
                "entrypoint": "frontend/src/main.tsx",
                "start": "./scripts/dev/restart.sh frontend",
                "health": "http://localhost:15173",
                "tests": "cd frontend && npm run test:run -- <path>",
            }
        ]

    def test_accepts_matching_runtime_rows(self) -> None:
        errors: list[str] = []

        CHECKER.check_runtime_doc_semantics(
            errors,
            self.inventory,
            arch_map=(
                "| `frontend` | react/vite | frontend/src/main.tsx | UI |\n"
                "- `frontend`\n"
                "  - health: `http://localhost:15173`\n"
            ),
            runbook=(
                "| `frontend` | `./scripts/dev/restart.sh frontend` | "
                "`http://localhost:15173` | `./debug/eval-frontend.sh \"document.title\"` |\n"
            ),
            verify="| `frontend` | `cd frontend && npm run test:run -- <path>` |\n",
        )

        self.assertEqual(errors, [])

    def test_reports_mismatched_runbook_row(self) -> None:
        errors: list[str] = []

        CHECKER.check_runtime_doc_semantics(
            errors,
            self.inventory,
            arch_map=(
                "| `frontend` | react/vite | frontend/src/main.tsx | UI |\n"
                "- `frontend`\n"
                "  - health: `http://localhost:15173`\n"
            ),
            runbook=(
                "| `frontend` | `./scripts/dev/restart.sh frontend` | "
                "`http://localhost:9999` | `./debug/eval-frontend.sh \"document.title\"` |\n"
            ),
            verify="| `frontend` | `cd frontend && npm run test:run -- <path>` |\n",
        )

        self.assertTrue(any("runbook runtime row for frontend" in error for error in errors))


class CheckTaskRoutingSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = [
            {
                "runtime": "orchestrator",
                "type": "backend",
                "stack": "python/django/daphne",
                "entrypoint": "orchestrator/config/asgi.py",
                "start": "./scripts/dev/restart.sh orchestrator",
                "health": "http://localhost:8200/health",
                "tests": "./scripts/dev/pytest.sh -q <path>",
            },
            {
                "runtime": "api-gateway",
                "type": "backend",
                "stack": "go/gin",
                "entrypoint": "go-services/api-gateway/cmd/main.go",
                "start": "./scripts/dev/restart.sh api-gateway",
                "health": "http://localhost:8180/health",
                "tests": "cd go-services/api-gateway && go test ./...",
            },
            {
                "runtime": "worker",
                "type": "worker",
                "stack": "go",
                "entrypoint": "go-services/worker/cmd/main.go",
                "start": "./scripts/dev/restart.sh worker",
                "health": "http://localhost:9191/health",
                "tests": "cd go-services/worker && go test ./...",
            },
            {
                "runtime": "frontend",
                "type": "frontend",
                "stack": "react/vite",
                "entrypoint": "frontend/src/main.tsx",
                "start": "./scripts/dev/restart.sh frontend",
                "health": "http://localhost:15173",
                "tests": "cd frontend && npm run test:run -- <path>",
            },
        ]
        self.task_routing = """# Task Routing

## Frontend work

- Первые code entry points:
  - [frontend/src/main.tsx](../../frontend/src/main.tsx)
  - [frontend/src/App.tsx](../../frontend/src/App.tsx)
- Первые проверки:
  - `cd frontend && npm run generate:api`
  - `cd frontend && npm run lint`
  - `cd frontend && npm run test:run -- <path>`
  - `cd frontend && npm run test:browser:ui-platform`
- Machine-readable surfaces:
  - [frontend/package.json](../../frontend/package.json)
  - `./debug/runtime-inventory.sh --json`

## Orchestrator work

- Первые code entry points:
  - [orchestrator/config/asgi.py](../../orchestrator/config/asgi.py)
- Первые проверки:
  - `./scripts/dev/lint.sh --python`
  - `./scripts/dev/pytest.sh -q <path>`
- Machine-readable surfaces:
  - `./debug/runtime-inventory.sh --json`

## Go services work

- Первые code entry points:
  - [go-services/api-gateway/cmd/main.go](../../go-services/api-gateway/cmd/main.go)
  - [go-services/worker/cmd/main.go](../../go-services/worker/cmd/main.go)
- Первые проверки:
  - `./scripts/dev/lint.sh --go`
  - `cd go-services/api-gateway && go test ./...`
  - `cd go-services/worker && go test ./...`
- Machine-readable surfaces:
  - `./debug/runtime-inventory.sh --json`

## Contracts и OpenSpec work

- Первые проверки:
  - `openspec validate <change-id> --strict --no-interactive`
  - `./scripts/dev/check-agent-doc-freshness.sh`
- Machine-readable surfaces:
  - `openspec list`
  - `openspec list --specs`
  - `bd ready`

## Runtime-debug и live verification

- Первые проверки:
  - `./debug/runtime-inventory.sh --json`
  - `./scripts/dev/health-check.sh`
  - `./debug/probe.sh all`
- Machine-readable surfaces:
  - `./debug/restart-runtime.sh <runtime>`

## Agent docs и guidance work

- Первые проверки:
  - `./scripts/dev/check-agent-doc-freshness.sh`
  - `openspec validate <change-id> --strict --no-interactive`
- Machine-readable surfaces:
  - [frontend/package.json](../../frontend/package.json)
  - `./debug/runtime-inventory.sh --json`
  - [.codex/config.toml](../../.codex/config.toml)
"""

    def test_accepts_matching_task_routing_sections(self) -> None:
        errors: list[str] = []

        CHECKER.check_task_routing_semantics(
            errors,
            self.inventory,
            task_routing=self.task_routing,
        )

        self.assertEqual(errors, [])

    def test_reports_when_frontend_test_command_leaks_out_of_section(self) -> None:
        errors: list[str] = []

        CHECKER.check_task_routing_semantics(
            errors,
            self.inventory,
            task_routing=self.task_routing.replace(
                "`cd frontend && npm run test:run -- <path>`",
                "`cd frontend && npm run vitest -- <path>`",
            ),
        )

        self.assertTrue(any("Frontend work" in error for error in errors))


class FrontendSmokeCoverageTests(unittest.TestCase):
    def test_validate_ui_platform_is_smoke_checked(self) -> None:
        self.assertIn(
            "validate:ui-platform",
            CHECKER.FRONTEND_SMOKE_SCRIPTS,
        )


class MainPipelineTests(unittest.TestCase):
    def test_main_surfaces_validate_ui_platform_smoke_failure(self) -> None:
        inventory = [
            {
                "runtime": "orchestrator",
                "type": "backend",
                "stack": "python/django/daphne",
                "entrypoint": "orchestrator/config/asgi.py",
                "start": "./scripts/dev/restart.sh orchestrator",
                "health": "http://localhost:8200/health",
                "tests": "./scripts/dev/pytest.sh -q <path>",
            },
            {
                "runtime": "api-gateway",
                "type": "backend",
                "stack": "go/gin",
                "entrypoint": "go-services/api-gateway/cmd/main.go",
                "start": "./scripts/dev/restart.sh api-gateway",
                "health": "http://localhost:8180/health",
                "tests": "cd go-services/api-gateway && go test ./...",
            },
            {
                "runtime": "worker",
                "type": "worker",
                "stack": "go",
                "entrypoint": "go-services/worker/cmd/main.go",
                "start": "./scripts/dev/restart.sh worker",
                "health": "http://localhost:9191/health",
                "tests": "cd go-services/worker && go test ./...",
            },
            {
                "runtime": "frontend",
                "type": "frontend",
                "stack": "react/vite",
                "entrypoint": "frontend/src/main.tsx",
                "start": "./scripts/dev/restart.sh frontend",
                "health": "http://localhost:15173",
                "tests": "cd frontend && npm run test:run -- <path>",
            },
        ]
        commands_seen: list[list[str]] = []
        original_path_exists = Path.exists

        def fake_require_command_success(
            errors: list[str],
            description: str,
            command: list[str],
            *,
            cwd: Path | None = None,
        ) -> None:
            commands_seen.append(command)
            if "validate:ui-platform" in command:
                errors.append(
                    f"{description} failed: frontend validate:ui-platform smoke was not executed"
                )

        def fake_path_exists(self: Path) -> bool:
            if self == CHECKER.ROOT / "frontend/node_modules":
                return True
            return original_path_exists(self)

        with (
            mock.patch.object(CHECKER, "load_inventory", return_value=inventory),
            mock.patch.object(CHECKER, "check_runtime_doc_semantics", return_value=None),
            mock.patch.object(CHECKER, "require_command_success", side_effect=fake_require_command_success),
            mock.patch.object(CHECKER.Path, "exists", new=fake_path_exists),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            exit_code = CHECKER.main()

        self.assertEqual(exit_code, 1)
        self.assertTrue(
            any("validate:ui-platform" in " ".join(command) for command in commands_seen),
            msg=f"validate:ui-platform smoke command was not scheduled: {commands_seen}",
        )
        self.assertIn("validate:ui-platform", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
