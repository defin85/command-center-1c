from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a structured run directory for an autoresearch cycle."
    )
    parser.add_argument("--name", required=True, help="Short human-readable run name.")
    parser.add_argument(
        "--feature-dir",
        help="Optional relative feature-pack directory to snapshot into the run.",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "run"


def get_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def ensure_relative_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError(f"Path must be relative to the repository root: {relative_path}")

    resolved = (ROOT / path).resolve()
    if ROOT.resolve() not in resolved.parents and resolved != ROOT.resolve():
        raise ValueError(f"Path escapes repository root: {relative_path}")
    return resolved


def snapshot_files(run_dir: Path, feature_dir: str | None = None) -> list[str]:
    snapshot_dir = run_dir / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        ROOT / "spec" / "feature.md",
        ROOT / "spec" / "change-constraints.md",
        ROOT / "evals" / "task.md",
        ROOT / "evals" / "checklist.md",
        ROOT / "tests" / "dev",
        ROOT / "tests" / "holdout",
        ROOT / "prompts" / "base.prompt.md",
        ROOT / "prompts" / "change-constraints.md",
        ROOT / "data" / "benchmarks" / "dev.jsonl",
        ROOT / "data" / "holdout" / "holdout.jsonl",
    ]
    if feature_dir:
        files_to_copy.append(ensure_relative_path(feature_dir))

    copied: list[str] = []
    for source in files_to_copy:
        if source.exists():
            relative = source.relative_to(ROOT)
            target = snapshot_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target)
            copied.append(str(target.relative_to(ROOT)))
    return copied


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{slugify(args.name)}"

    run_dir = ROOT / "logs" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (ROOT / "artifacts" / run_id).mkdir(parents=True, exist_ok=False)

    metadata = {
        "run_id": run_id,
        "name": args.name,
        "created_at_utc": timestamp,
        "git_commit": get_git_commit(),
        "feature_dir": args.feature_dir,
        "snapshots": snapshot_files(run_dir, args.feature_dir),
    }
    write_json(run_dir / "metadata.json", metadata)
    (run_dir / "results.jsonl").write_text("", encoding="utf-8")
    (run_dir / "summary.md").write_text(
        "# Run Summary\n\n"
        f"- Run ID: `{run_id}`\n"
        f"- Name: `{args.name}`\n"
        "- Baseline development score: pending\n"
        "- Best candidate: pending\n"
        "- Holdout confirmation: pending\n",
        encoding="utf-8",
    )

    print(f"Created run: {run_id}")
    print(f"Run directory: {run_dir}")
    print(f"Artifact directory: {ROOT / 'artifacts' / run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
