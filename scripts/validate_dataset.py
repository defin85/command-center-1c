from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate development and holdout JSONL case manifests."
    )
    parser.add_argument("--dev", required=True, help="Path to the development JSONL file.")
    parser.add_argument(
        "--holdout", required=True, help="Path to the holdout JSONL file."
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{lineno}: each line must be a JSON object")
            validate_record(record, path, lineno)
            records.append(record)

    if not records:
        raise ValueError(f"{path}: no records found")
    return records


def validate_record(record: dict[str, Any], path: Path, lineno: int) -> None:
    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id.strip():
        raise ValueError(f"{path}:{lineno}: 'id' must be a non-empty string")

    has_io_keys = "input" in record or "expected" in record
    has_feature_keys = (
        "task" in record or "verification" in record or "allowed_paths" in record
    )

    if not has_io_keys and not has_feature_keys:
        raise ValueError(
            f"{path}:{lineno}: each record must define either "
            "'input'/'expected' or 'task'/'verification'"
        )

    if has_io_keys:
        if "input" not in record or record["input"] is None:
            raise ValueError(f"{path}:{lineno}: missing non-null 'input'")
        if "expected" not in record or record["expected"] is None:
            raise ValueError(f"{path}:{lineno}: missing non-null 'expected'")

    if has_feature_keys:
        if not isinstance(record.get("task"), str) or not record["task"].strip():
            raise ValueError(f"{path}:{lineno}: 'task' must be a non-empty string")
        validate_verification(record.get("verification"), path, lineno)
        validate_allowed_paths(record.get("allowed_paths"), path, lineno)


def validate_verification(value: Any, path: Path, lineno: int) -> None:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError(f"{path}:{lineno}: 'verification' must not be empty")
        return

    if isinstance(value, list) and value:
        for index, command in enumerate(value, start=1):
            if not isinstance(command, str) or not command.strip():
                raise ValueError(
                    f"{path}:{lineno}: verification command #{index} must be a "
                    "non-empty string"
                )
        return

    raise ValueError(
        f"{path}:{lineno}: 'verification' must be a non-empty string or list of strings"
    )


def validate_allowed_paths(value: Any, path: Path, lineno: int) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        raise ValueError(f"{path}:{lineno}: 'allowed_paths' must be a list of strings")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"{path}:{lineno}: allowed_paths item #{index} must be a non-empty string"
            )


def collect_ids(records: list[dict[str, Any]], label: str) -> set[str]:
    ids: set[str] = set()
    duplicates: list[str] = []
    for record in records:
        record_id = record["id"]
        if record_id in ids:
            duplicates.append(record_id)
        ids.add(record_id)
    if duplicates:
        duplicate_list = ", ".join(sorted(set(duplicates)))
        raise ValueError(f"{label}: duplicate ids found: {duplicate_list}")
    return ids


def print_summary(dev_count: int, holdout_count: int) -> None:
    total = dev_count + holdout_count
    ratio = holdout_count / total if total else 0.0
    print(f"Development records: {dev_count}")
    print(f"Holdout records: {holdout_count}")
    print(f"Holdout share: {ratio:.1%}")
    if total >= 5 and not 0.2 <= ratio <= 0.3:
        print(
            "Warning: holdout share is outside the usual 20-30% range. "
            "This is allowed, but review the split on purpose."
        )


def main() -> int:
    args = parse_args()
    dev_path = Path(args.dev)
    holdout_path = Path(args.holdout)

    dev_records = load_jsonl(dev_path)
    holdout_records = load_jsonl(holdout_path)

    dev_ids = collect_ids(dev_records, "development")
    holdout_ids = collect_ids(holdout_records, "holdout")
    overlap = dev_ids & holdout_ids
    if overlap:
        overlap_list = ", ".join(sorted(overlap))
        raise ValueError(f"overlap between development and holdout ids: {overlap_list}")

    print_summary(len(dev_records), len(holdout_records))
    print("Case manifest validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
