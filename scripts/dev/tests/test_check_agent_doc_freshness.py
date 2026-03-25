import importlib.util
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
