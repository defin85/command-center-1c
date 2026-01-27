#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Config:
  default_limit: int
  default_top: int
  include_extensions: tuple[str, ...]
  include_tests: bool
  exclude_prefixes: tuple[str, ...]
  exclude_path_contains: tuple[str, ...]
  scopes: dict[str, tuple[str, ...]]


def load_config(repo_root: pathlib.Path) -> Config:
  config_path = repo_root / "scripts/dev/file-size-report.config.json"
  with config_path.open("r", encoding="utf-8") as fh:
    raw = json.load(fh)

  scopes = {k: tuple(v) for k, v in raw.get("scopes", {}).items()}
  return Config(
    default_limit=int(raw["default_limit"]),
    default_top=int(raw["default_top"]),
    include_extensions=tuple(raw["include_extensions"]),
    include_tests=bool(raw.get("include_tests", True)),
    exclude_prefixes=tuple(raw.get("exclude_prefixes", [])),
    exclude_path_contains=tuple(raw.get("exclude_path_contains", [])),
    scopes=scopes,
  )


def git_ls_files(repo_root: pathlib.Path) -> list[str]:
  proc = subprocess.run(
    ["git", "ls-files", "-z"],
    cwd=str(repo_root),
    check=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
  )
  return [p for p in proc.stdout.decode("utf-8", errors="replace").split("\0") if p]


def is_excluded(path: str, config: Config) -> bool:
  for prefix in config.exclude_prefixes:
    if path.startswith(prefix):
      return True
  for needle in config.exclude_path_contains:
    if needle in path:
      return True
  return False


def in_scope(path: str, scope_prefixes: tuple[str, ...]) -> bool:
  if not scope_prefixes:
    return True
  return any(path.startswith(prefix) for prefix in scope_prefixes)


def iter_included_paths(paths: Iterable[str], config: Config, scope: str) -> list[str]:
  scope_prefixes = config.scopes.get(scope)
  if scope_prefixes is None:
    raise ValueError(f"Unknown scope: {scope}")

  result: list[str] = []
  for p in paths:
    if not p.endswith(config.include_extensions):
      continue
    if not in_scope(p, scope_prefixes):
      continue
    if is_excluded(p, config):
      continue
    result.append(p)
  return result


def count_lines(path: pathlib.Path) -> int:
  try:
    with path.open("rb") as fh:
      # Match `wc -l`: count newline characters.
      return fh.read().count(b"\n")
  except FileNotFoundError:
    return 0


def format_table(rows: list[tuple[int, str]]) -> str:
  if not rows:
    return ""
  width = max(len(str(lines)) for lines, _ in rows)
  return "\n".join(f"{lines:>{width}}  {path}" for lines, path in rows)


def main(argv: list[str]) -> int:
  parser = argparse.ArgumentParser(
    prog="file-size-report",
    description="Soft report of oversized source files (by line count).",
  )
  parser.add_argument(
    "--scope",
    default=os.environ.get("SCOPE", "all"),
    help="Scope: all|frontend|orchestrator|go-services (default: all)",
  )
  parser.add_argument(
    "--limit",
    type=int,
    default=None,
    help="Line limit (default: from config, usually 700)",
  )
  parser.add_argument(
    "--top",
    type=int,
    default=None,
    help="Show top N offenders (default: from config)",
  )
  parser.add_argument(
    "--all",
    action="store_true",
    help="Show all offenders instead of top N",
  )
  args = parser.parse_args(argv)

  repo_root = pathlib.Path(__file__).resolve().parents[2]
  config = load_config(repo_root)
  limit = int(args.limit) if args.limit is not None else config.default_limit
  top_n = int(args.top) if args.top is not None else config.default_top

  tracked = git_ls_files(repo_root)
  included = iter_included_paths(tracked, config, args.scope)

  counts: list[tuple[int, str]] = []
  for rel in included:
    lines = count_lines(repo_root / rel)
    counts.append((lines, rel))

  offenders = sorted((r for r in counts if r[0] > limit), key=lambda x: (-x[0], x[1]))
  shown = offenders if args.all else offenders[:top_n]

  print("file-size-report")
  print(f"scope: {args.scope}")
  print(f"limit: {limit}")
  print(f"included: {len(included)} files")
  print(f"offenders: {len(offenders)} files (> {limit})")
  if shown:
    print("")
    print(format_table(shown))

  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))
