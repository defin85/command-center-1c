from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repo-owned adapter for input/expected feature loop cases."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser(
        "evaluate-case", help="Evaluate a single input/expected case."
    )
    evaluate.add_argument("--case-file", required=True, help="Path to the JSON case file.")
    evaluate.add_argument("--phase", required=True, help="Current loop phase.")
    evaluate.add_argument("--iteration", required=True, help="Current loop iteration.")
    return parser.parse_args()


def write_payload(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("passed") else 1


def resolve_callable(spec: str):
    module_name, separator, attribute_name = spec.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError(
            "adapter_callable must use the form 'module_name:callable_name'"
        )

    search_roots = [ROOT]
    src_root = ROOT / "src"
    if src_root.exists():
        search_roots.insert(0, src_root)

    for search_root in reversed(search_roots):
        path_value = str(search_root)
        if path_value not in sys.path:
            sys.path.insert(0, path_value)

    module = importlib.import_module(module_name)
    target = getattr(module, attribute_name)
    if not callable(target):
        raise TypeError(f"Resolved target is not callable: {spec}")
    return target


def run_evaluate_case(args: argparse.Namespace) -> int:
    case_path = Path(args.case_file)
    case = json.loads(case_path.read_text(encoding="utf-8"))

    adapter_callable = case.get("adapter_callable")
    if not isinstance(adapter_callable, str) or not adapter_callable.strip():
        return write_payload(
            {
                "passed": False,
                "actual": None,
                "details": {
                    "error": (
                        "input/expected cases require an 'adapter_callable' field or "
                        "a repo-specific replacement adapter script"
                    ),
                    "phase": args.phase,
                    "iteration": args.iteration,
                },
            }
        )

    try:
        target = resolve_callable(adapter_callable.strip())
        actual = target(case.get("input"))
    except Exception as exc:  # pragma: no cover - exercised via CLI integration tests
        return write_payload(
            {
                "passed": False,
                "actual": None,
                "details": {
                    "error": str(exc),
                    "adapter_callable": adapter_callable,
                    "phase": args.phase,
                    "iteration": args.iteration,
                },
            }
        )

    return write_payload(
        {
            "passed": actual == case.get("expected"),
            "actual": actual,
            "details": {
                "adapter_callable": adapter_callable,
                "phase": args.phase,
                "iteration": args.iteration,
            },
        }
    )


def main() -> int:
    args = parse_args()
    if args.command == "evaluate-case":
        return run_evaluate_case(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
