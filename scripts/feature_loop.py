from __future__ import annotations

import argparse
from pathlib import Path

from feature_loop_core import (
    build_runtime,
    run_baseline,
    run_ci_replay,
    run_holdout,
    run_iteration,
    run_revert,
)


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an eval-driven feature loop with keep/revert decisions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("baseline", help="Record the baseline state.")
    add_shared_args(baseline)
    baseline.add_argument(
        "--allowed-path",
        action="append",
        default=[],
        help="Extra relative paths that may be restored during revert.",
    )
    baseline.add_argument(
        "--adapter-script",
        help=(
            "Optional repo-owned adapter used for input/expected cases. "
            "Defaults to scripts/feature_loop_adapter.py when present."
        ),
    )

    iteration = subparsers.add_parser(
        "iteration", help="Evaluate current changes against the best known state."
    )
    add_shared_args(iteration)
    iteration.add_argument(
        "--auto-revert",
        action="store_true",
        help="Restore the last kept snapshot when the iteration does not improve.",
    )
    iteration.add_argument(
        "--keep-equal",
        action="store_true",
        help="Keep states that tie the current best score.",
    )
    iteration.add_argument(
        "--label",
        default="",
        help="Optional human-readable label for the iteration entry.",
    )

    holdout = subparsers.add_parser(
        "holdout", help="Run the protected holdout cases for confirmation."
    )
    holdout.add_argument("--run-id", required=True, help="Existing run id.")
    holdout.add_argument(
        "--holdout",
        help=(
            "Relative or absolute path to the holdout case manifest. "
            "Defaults to the value stored during baseline."
        ),
    )

    revert = subparsers.add_parser(
        "revert", help="Restore the last kept snapshot inside the allowed paths."
    )
    revert.add_argument("--run-id", required=True, help="Existing run id.")
    revert.add_argument(
        "--verify",
        action="store_true",
        help="Run development checks after the restore.",
    )

    ci_replay = subparsers.add_parser(
        "ci-replay",
        help="Replay the best kept candidate in a clean copied working tree.",
    )
    ci_replay.add_argument("--run-id", required=True, help="Existing run id.")
    ci_replay.add_argument(
        "--phase",
        choices=("dev", "holdout", "both"),
        default="both",
        help="Which manifests to replay in the clean working tree.",
    )
    ci_replay.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the copied working tree after replay for manual inspection.",
    )

    return parser.parse_args()


def add_shared_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", required=True, help="Existing run id.")
    parser.add_argument(
        "--dev",
        default="data/benchmarks/dev.jsonl",
        help="Relative path to the development case manifest.",
    )
    parser.add_argument(
        "--holdout",
        default="data/holdout/holdout.jsonl",
        help="Relative or absolute path to the holdout case manifest.",
    )


def main() -> int:
    args = parse_args()
    runtime = build_runtime(
        ROOT,
        args.run_id,
        getattr(args, "adapter_script", None),
    )

    if args.command == "baseline":
        return run_baseline(
            runtime,
            dev_manifest=args.dev,
            holdout_manifest=args.holdout,
            extra_allowed_paths=args.allowed_path,
        )
    if args.command == "iteration":
        return run_iteration(
            runtime,
            auto_revert=args.auto_revert,
            keep_equal=args.keep_equal,
            label=args.label,
        )
    if args.command == "holdout":
        return run_holdout(runtime, holdout_manifest=args.holdout)
    if args.command == "revert":
        return run_revert(runtime, verify=args.verify)
    if args.command == "ci-replay":
        return run_ci_replay(runtime, phase=args.phase, keep_temp=args.keep_temp)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
