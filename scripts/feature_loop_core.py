from __future__ import annotations

from fnmatch import fnmatch
import json
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IGNORED_AUDIT_PREFIXES = (
    "logs/",
    "artifacts/",
    ".pytest_cache/",
    ".venv/",
    "outputs/generated/",
)

IGNORED_COPY_NAMES = {
    ".git",
    ".venv",
    ".pytest_cache",
    "logs",
    "artifacts",
}

IGNORED_COPY_NESTED_NAMES = {
    "__pycache__",
}


def load_copy_ignore_patterns(root: Path) -> list[str]:
    config_path = root / ".autoresearch-copyignore"
    if not config_path.exists():
        return []

    patterns: list[str] = []
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line.rstrip("/"))
    return patterns


def matches_copy_ignore(root: Path, path: Path, patterns: list[str]) -> bool:
    if not patterns:
        return False

    try:
        relative = path.relative_to(root).as_posix().rstrip("/")
    except ValueError:
        relative = path.name

    for pattern in patterns:
        if fnmatch(relative, pattern) or fnmatch(path.name, pattern):
            return True
    return False


@dataclass(frozen=True)
class LoopPaths:
    run_dir: Path
    artifact_dir: Path
    metadata: Path
    summary: Path
    results: Path
    state: Path
    best_snapshot: Path
    evaluations: Path


@dataclass(frozen=True)
class LoopRuntime:
    root: Path
    python_bin: str
    adapter_script: str | None
    paths: LoopPaths


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def resolve_loop_paths(root: Path, run_id: str) -> LoopPaths:
    run_dir = root / "logs" / "runs" / run_id
    if not run_dir.exists():
        raise ValueError(f"Run directory not found: {run_dir}")

    artifact_dir = root / "artifacts" / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    return LoopPaths(
        run_dir=run_dir,
        artifact_dir=artifact_dir,
        metadata=run_dir / "metadata.json",
        summary=run_dir / "summary.md",
        results=run_dir / "results.jsonl",
        state=run_dir / "loop-state.json",
        best_snapshot=artifact_dir / "best-state",
        evaluations=artifact_dir / "evaluations",
    )


def resolve_repo_path(root: Path, value: str, *, allow_external: bool = False) -> Path:
    path = Path(value)
    if path.is_absolute():
        resolved = path.resolve()
        if allow_external:
            return resolved
        raise ValueError(f"Path must stay inside the repository: {value}")

    resolved = (root / path).resolve()
    if root.resolve() not in resolved.parents and resolved != root.resolve():
        raise ValueError(f"Path escapes repository root: {value}")
    return resolved


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def load_cases(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        raise ValueError(f"Manifest not found: {manifest_path}")

    cases: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for lineno, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{manifest_path}:{lineno}: case must be a JSON object")
            cases.append(record)
    if not cases:
        raise ValueError(f"Manifest is empty: {manifest_path}")
    return cases


def normalize_commands(case: dict[str, Any], manifest_path: Path) -> list[str]:
    verification = case.get("verification")
    if isinstance(verification, str) and verification.strip():
        return [verification]
    if isinstance(verification, list) and verification:
        commands = [cmd for cmd in verification if isinstance(cmd, str) and cmd.strip()]
        if len(commands) == len(verification):
            return commands
    raise ValueError(
        f"{manifest_path}: case '{case.get('id', '<unknown>')}' does not define "
        "executable verification commands"
    )


def collect_allowed_paths(
    root: Path, cases: list[dict[str, Any]], extra_paths: list[str] | None = None
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for case in cases:
        for item in case.get("allowed_paths", []):
            if isinstance(item, str) and item.strip() and item not in seen:
                resolve_repo_path(root, item)
                ordered.append(item)
                seen.add(item)
    for item in extra_paths or []:
        if item not in seen:
            resolve_repo_path(root, item)
            ordered.append(item)
            seen.add(item)
    if not ordered:
        raise ValueError("No allowed paths were found. Add 'allowed_paths' to the manifest.")
    return ordered


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def snapshot_allowed_paths(root: Path, allowed_paths: list[str], snapshot_root: Path) -> None:
    remove_path(snapshot_root)
    snapshot_root.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    for relative_path in allowed_paths:
        source = root / relative_path
        target = snapshot_root / relative_path
        if not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
        saved.append(relative_path)

    write_json(
        snapshot_root / "manifest.json",
        {
            "allowed_paths": allowed_paths,
            "saved_paths": saved,
        },
    )


def restore_snapshot(root: Path, snapshot_root: Path) -> list[str]:
    manifest_path = snapshot_root / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"Snapshot manifest not found: {manifest_path}")

    manifest = read_json(manifest_path)
    restored: list[str] = []
    for relative_path in manifest["allowed_paths"]:
        current = root / relative_path
        source = snapshot_root / relative_path
        if current.exists():
            remove_path(current)
        if source.exists():
            current.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, current, dirs_exist_ok=True)
            else:
                shutil.copy2(source, current)
        restored.append(relative_path)
    return restored


def score_tuple(score: dict[str, Any]) -> tuple[float, int]:
    return (float(score["ratio"]), int(score["passed"]))


def build_adapter_command(root: Path, python_bin: str, adapter_script: str | None) -> list[str] | None:
    script_value = adapter_script or "scripts/feature_loop_adapter.py"
    script_path = resolve_repo_path(root, script_value)
    if not script_path.exists():
        if adapter_script:
            raise ValueError(f"Adapter script not found: {script_path}")
        return None
    if script_path.suffix == ".py":
        return [python_bin, str(script_path), "evaluate-case"]
    return [str(script_path), "evaluate-case"]


def sanitize_case_id(value: str) -> str:
    sanitized = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in value
    ).strip("-")
    return sanitized or "case"


def evaluate_command_case(root: Path, case: dict[str, Any], commands: list[str]) -> tuple[bool, list[dict[str, Any]]]:
    command_results: list[dict[str, Any]] = []
    case_passed = True
    for command in commands:
        command_started = time.perf_counter()
        result = subprocess.run(
            command,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
        )
        duration_ms = round((time.perf_counter() - command_started) * 1000, 2)
        if result.returncode != 0:
            case_passed = False
        command_results.append(
            {
                "command": command,
                "returncode": result.returncode,
                "duration_ms": duration_ms,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            }
        )
    return case_passed, command_results


def evaluate_input_output_case(
    runtime: LoopRuntime,
    *,
    case: dict[str, Any],
    phase: str,
    iteration: int,
) -> tuple[bool, dict[str, Any]]:
    adapter_command = build_adapter_command(
        runtime.root, runtime.python_bin, runtime.adapter_script
    )
    if adapter_command is None:
        raise ValueError(
            "Pure input/expected cases require a repo-owned adapter script at "
            "'scripts/feature_loop_adapter.py' or an explicit adapter override."
        )

    case_id = sanitize_case_id(str(case.get("id", "case")))
    case_file = runtime.paths.artifact_dir / "case-inputs" / f"{phase}-{iteration:03d}-{case_id}.json"
    write_json(case_file, case)

    command_started = time.perf_counter()
    result = subprocess.run(
        [
            *adapter_command,
            "--case-file",
            str(case_file),
            "--phase",
            phase,
            "--iteration",
            str(iteration),
        ],
        cwd=runtime.root,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = round((time.perf_counter() - command_started) * 1000, 2)

    payload: dict[str, Any]
    parse_error = ""
    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        payload = {}
        parse_error = str(exc)

    passed = bool(payload.get("passed")) if result.returncode == 0 and not parse_error else False
    details = {
        "command": " ".join(adapter_command),
        "case_file": display_path(runtime.root, case_file),
        "returncode": result.returncode,
        "duration_ms": duration_ms,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
        "actual": payload.get("actual"),
        "expected": case.get("expected"),
        "details": payload.get("details"),
    }
    if parse_error:
        details["parse_error"] = parse_error
    return passed, details


def evaluate_manifest(
    runtime: LoopRuntime,
    *,
    manifest_path: Path,
    phase: str,
    iteration: int,
) -> dict[str, Any]:
    cases = load_cases(manifest_path)
    case_results: list[dict[str, Any]] = []
    passed = 0
    started = time.perf_counter()

    for case in cases:
        if "verification" in case:
            commands = normalize_commands(case, manifest_path)
            case_passed, command_results = evaluate_command_case(runtime.root, case, commands)
            case_result = {
                "mode": "command",
                "commands": command_results,
            }
        elif "input" in case and "expected" in case:
            case_passed, io_result = evaluate_input_output_case(
                runtime,
                case=case,
                phase=phase,
                iteration=iteration,
            )
            case_result = {
                "mode": "input-output",
                "adapter": io_result,
            }
        else:
            raise ValueError(
                f"{manifest_path}: case '{case.get('id', '<unknown>')}' does not define "
                "either verification commands or input/expected payloads"
            )

        if case_passed:
            passed += 1

        case_results.append(
            {
                "id": case["id"],
                "task": case.get("task"),
                "passed": case_passed,
                "allowed_paths": case.get("allowed_paths", []),
                **case_result,
            }
        )

    total = len(cases)
    score = {
        "passed": passed,
        "total": total,
        "ratio": round(passed / total, 6),
    }
    duration_ms = round((time.perf_counter() - started) * 1000, 2)

    runtime.paths.evaluations.mkdir(parents=True, exist_ok=True)
    artifact_path = runtime.paths.evaluations / f"{phase}-{iteration:03d}.json"
    payload = {
        "run_id": runtime.paths.run_dir.name,
        "phase": phase,
        "iteration": iteration,
        "manifest": display_path(runtime.root, manifest_path),
        "score": score,
        "duration_ms": duration_ms,
        "cases": case_results,
    }
    write_json(artifact_path, payload)
    payload["artifact"] = display_path(runtime.root, artifact_path)
    return payload


def collect_dirty_paths(root: Path) -> dict[str, Any]:
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return {
            "mode": "unsupported",
            "current_dirty_paths": [],
        }

    commands = [
        ["git", "diff", "--name-only", "--relative"],
        ["git", "diff", "--cached", "--name-only", "--relative"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    dirty_paths: set[str] = set()
    for command in commands:
        result = subprocess.run(
            command,
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            path = line.strip()
            if path:
                dirty_paths.add(path)

    return {
        "mode": "git",
        "current_dirty_paths": sorted(dirty_paths),
    }


def path_matches_prefix(path: str, prefix: str) -> bool:
    normalized = prefix.rstrip("/")
    return path == normalized or path.startswith(normalized + "/")


def is_ignored_audit_path(path: str) -> bool:
    if any(segment == "__pycache__" for segment in path.split("/")):
        return True
    return any(path_matches_prefix(path, prefix) for prefix in IGNORED_AUDIT_PREFIXES)


def audit_write_scope(
    root: Path,
    *,
    allowed_paths: list[str],
    baseline_dirty_paths: list[str],
) -> dict[str, Any]:
    status = collect_dirty_paths(root)
    if status["mode"] != "git":
        return {
            **status,
            "new_dirty_paths": [],
            "unexpected_dirty_paths": [],
            "passed": True,
        }

    current_dirty_paths = status["current_dirty_paths"]
    new_dirty_paths = sorted(
        path for path in current_dirty_paths if path not in set(baseline_dirty_paths)
    )
    unexpected_dirty_paths = sorted(
        path
        for path in new_dirty_paths
        if not is_ignored_audit_path(path)
        and not any(path_matches_prefix(path, allowed) for allowed in allowed_paths)
    )
    return {
        "mode": "git",
        "current_dirty_paths": current_dirty_paths,
        "new_dirty_paths": new_dirty_paths,
        "unexpected_dirty_paths": unexpected_dirty_paths,
        "passed": not unexpected_dirty_paths,
    }


def load_state_or_fail(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        raise ValueError(
            f"Loop state not found: {state_path}. Run the baseline command first."
        )
    return read_json(state_path)


def update_summary(paths: LoopPaths, state: dict[str, Any]) -> None:
    metadata = read_json(paths.metadata) if paths.metadata.exists() else {}
    best_score = state["best_score"]
    holdout = state.get("holdout")

    holdout_text = "pending"
    if holdout:
        holdout_text = (
            f"{holdout['score']['passed']}/{holdout['score']['total']} "
            f"({holdout['score']['ratio']:.1%}) at iteration {holdout['iteration']}"
        )

    lines = [
        "# Run Summary",
        "",
        f"- Run ID: `{state['run_id']}`",
        f"- Name: `{metadata.get('name', state['run_id'])}`",
        (
            f"- Baseline development score: {state['baseline_score']['passed']}/"
            f"{state['baseline_score']['total']} "
            f"({state['baseline_score']['ratio']:.1%})"
        ),
        (
            f"- Best candidate: iteration {state['best_iteration']} with "
            f"{best_score['passed']}/{best_score['total']} "
            f"({best_score['ratio']:.1%})"
        ),
        f"- Holdout confirmation: {holdout_text}",
        f"- Allowed paths: `{', '.join(state['allowed_paths'])}`",
        f"- Latest iteration: {state['latest_iteration']}",
        f"- Adapter script: `{state.get('adapter_script') or 'scripts/feature_loop_adapter.py'}`",
    ]
    if state.get("baseline_dirty_paths"):
        lines.append(
            f"- Baseline dirty paths preserved: {len(state['baseline_dirty_paths'])}"
        )
    paths.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")


def record_result(
    paths: LoopPaths,
    *,
    phase: str,
    iteration: int,
    decision: str,
    evaluation: dict[str, Any],
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase": phase,
        "iteration": iteration,
        "decision": decision,
        "score": evaluation["score"],
        "artifact": evaluation["artifact"],
    }
    if note:
        entry["note"] = note
    if extra:
        entry.update(extra)
    append_jsonl(paths.results, entry)


def build_runtime(root: Path, run_id: str, adapter_script: str | None = None) -> LoopRuntime:
    return LoopRuntime(
        root=root.resolve(),
        python_bin=sys.executable,
        adapter_script=adapter_script,
        paths=resolve_loop_paths(root.resolve(), run_id),
    )


def run_baseline(
    runtime: LoopRuntime,
    *,
    dev_manifest: str,
    holdout_manifest: str,
    extra_allowed_paths: list[str] | None = None,
) -> int:
    if runtime.paths.state.exists():
        raise ValueError(f"Loop state already exists: {runtime.paths.state}")

    manifest_path = resolve_repo_path(runtime.root, dev_manifest)
    cases = load_cases(manifest_path)
    allowed_paths = collect_allowed_paths(runtime.root, cases, extra_allowed_paths)
    evaluation = evaluate_manifest(
        runtime,
        manifest_path=manifest_path,
        phase="dev-baseline",
        iteration=0,
    )
    snapshot_allowed_paths(runtime.root, allowed_paths, runtime.paths.best_snapshot)
    baseline_audit = collect_dirty_paths(runtime.root)

    state = {
        "run_id": runtime.paths.run_dir.name,
        "dev_manifest": dev_manifest,
        "holdout_manifest": holdout_manifest,
        "allowed_paths": allowed_paths,
        "adapter_script": runtime.adapter_script,
        "baseline_score": evaluation["score"],
        "best_score": evaluation["score"],
        "best_iteration": 0,
        "latest_iteration": 0,
        "best_artifact": evaluation["artifact"],
        "baseline_dirty_paths": baseline_audit.get("current_dirty_paths", []),
        "audit_mode": baseline_audit.get("mode"),
    }
    write_json(runtime.paths.state, state)
    record_result(
        runtime.paths,
        phase="dev",
        iteration=0,
        decision="keep",
        evaluation=evaluation,
        extra={"audit": baseline_audit},
    )
    update_summary(runtime.paths, state)
    print(
        f"Baseline recorded: {evaluation['score']['passed']}/"
        f"{evaluation['score']['total']} ({evaluation['score']['ratio']:.1%})"
    )
    return 0


def run_iteration(
    runtime: LoopRuntime,
    *,
    auto_revert: bool,
    keep_equal: bool,
    label: str,
) -> int:
    state = load_state_or_fail(runtime.paths.state)
    runtime = LoopRuntime(
        root=runtime.root,
        python_bin=runtime.python_bin,
        adapter_script=state.get("adapter_script"),
        paths=runtime.paths,
    )
    manifest_path = resolve_repo_path(runtime.root, state["dev_manifest"])
    iteration = int(state["latest_iteration"]) + 1

    evaluation = evaluate_manifest(
        runtime,
        manifest_path=manifest_path,
        phase="dev-iteration",
        iteration=iteration,
    )
    audit = audit_write_scope(
        runtime.root,
        allowed_paths=state["allowed_paths"],
        baseline_dirty_paths=state.get("baseline_dirty_paths", []),
    )

    if not audit["passed"]:
        extra: dict[str, Any] = {"audit": audit}
        decision = "audit-violation"
        note = label or "unexpected writes outside allowed_paths"
        if auto_revert:
            restored_paths = restore_snapshot(runtime.root, runtime.paths.best_snapshot)
            post_audit = audit_write_scope(
                runtime.root,
                allowed_paths=state["allowed_paths"],
                baseline_dirty_paths=state.get("baseline_dirty_paths", []),
            )
            extra["restored_paths"] = restored_paths
            extra["post_revert_audit"] = post_audit
        state["latest_iteration"] = iteration
        write_json(runtime.paths.state, state)
        record_result(
            runtime.paths,
            phase="dev",
            iteration=iteration,
            decision=decision,
            evaluation=evaluation,
            note=note,
            extra=extra,
        )
        update_summary(runtime.paths, state)
        print(
            "Audit violation: writes outside allowed_paths detected: "
            + ", ".join(audit["unexpected_dirty_paths"])
        )
        return 1

    current_score = evaluation["score"]
    best_score = state["best_score"]
    improved = score_tuple(current_score) > score_tuple(best_score)
    tied = score_tuple(current_score) == score_tuple(best_score)
    keep = improved or (keep_equal and tied)

    extra: dict[str, Any] = {"audit": audit}
    if keep:
        snapshot_allowed_paths(runtime.root, state["allowed_paths"], runtime.paths.best_snapshot)
        state["best_score"] = current_score
        state["best_iteration"] = iteration
        state["best_artifact"] = evaluation["artifact"]
        decision = "keep"
        note = label or "development score improved"
    else:
        decision = "revert" if auto_revert else "discard"
        note = label or "development score did not improve"
        if auto_revert:
            restored_paths = restore_snapshot(runtime.root, runtime.paths.best_snapshot)
            revert_eval = evaluate_manifest(
                runtime,
                manifest_path=manifest_path,
                phase="dev-post-revert",
                iteration=iteration,
            )
            post_audit = audit_write_scope(
                runtime.root,
                allowed_paths=state["allowed_paths"],
                baseline_dirty_paths=state.get("baseline_dirty_paths", []),
            )
            extra.update(
                {
                    "restored_paths": restored_paths,
                    "post_revert_artifact": revert_eval["artifact"],
                    "post_revert_score": revert_eval["score"],
                    "post_revert_audit": post_audit,
                }
            )

    state["latest_iteration"] = iteration
    write_json(runtime.paths.state, state)
    record_result(
        runtime.paths,
        phase="dev",
        iteration=iteration,
        decision=decision,
        evaluation=evaluation,
        note=note,
        extra=extra,
    )
    update_summary(runtime.paths, state)
    print(
        f"Iteration {iteration}: {decision} "
        f"({current_score['passed']}/{current_score['total']}, {current_score['ratio']:.1%})"
    )
    return 0


def run_holdout(runtime: LoopRuntime, *, holdout_manifest: str | None = None) -> int:
    state = load_state_or_fail(runtime.paths.state)
    runtime = LoopRuntime(
        root=runtime.root,
        python_bin=runtime.python_bin,
        adapter_script=state.get("adapter_script"),
        paths=runtime.paths,
    )
    manifest_value = holdout_manifest or state["holdout_manifest"]
    manifest_path = resolve_repo_path(runtime.root, manifest_value, allow_external=True)
    iteration = int(state["best_iteration"])

    evaluation = evaluate_manifest(
        runtime,
        manifest_path=manifest_path,
        phase="holdout",
        iteration=iteration,
    )
    state["holdout"] = {
        "iteration": iteration,
        "score": evaluation["score"],
        "artifact": evaluation["artifact"],
        "manifest": display_path(runtime.root, manifest_path),
    }
    write_json(runtime.paths.state, state)
    record_result(
        runtime.paths,
        phase="holdout",
        iteration=iteration,
        decision="observe",
        evaluation=evaluation,
        note="holdout confirmation",
    )
    update_summary(runtime.paths, state)
    print(
        f"Holdout: {evaluation['score']['passed']}/"
        f"{evaluation['score']['total']} ({evaluation['score']['ratio']:.1%})"
    )
    return 0


def run_revert(runtime: LoopRuntime, *, verify: bool) -> int:
    state = load_state_or_fail(runtime.paths.state)
    runtime = LoopRuntime(
        root=runtime.root,
        python_bin=runtime.python_bin,
        adapter_script=state.get("adapter_script"),
        paths=runtime.paths,
    )
    restored_paths = restore_snapshot(runtime.root, runtime.paths.best_snapshot)
    iteration = int(state["latest_iteration"])

    extra: dict[str, Any] = {"restored_paths": restored_paths}
    placeholder_evaluation = {
        "score": state["best_score"],
        "artifact": state["best_artifact"],
    }

    if verify:
        manifest_path = resolve_repo_path(runtime.root, state["dev_manifest"])
        verification = evaluate_manifest(
            runtime,
            manifest_path=manifest_path,
            phase="dev-manual-revert",
            iteration=iteration,
        )
        post_audit = audit_write_scope(
            runtime.root,
            allowed_paths=state["allowed_paths"],
            baseline_dirty_paths=state.get("baseline_dirty_paths", []),
        )
        extra["post_revert_artifact"] = verification["artifact"]
        extra["post_revert_score"] = verification["score"]
        extra["post_revert_audit"] = post_audit

    record_result(
        runtime.paths,
        phase="revert",
        iteration=iteration,
        decision="restore",
        evaluation=placeholder_evaluation,
        note="manual revert to last kept snapshot",
        extra=extra,
    )
    update_summary(runtime.paths, state)
    print(f"Restored paths: {', '.join(restored_paths)}")
    return 0


def copy_repo_tree(root: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    copy_ignore_patterns = load_copy_ignore_patterns(root)

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            candidate = Path(directory) / name
            try:
                mode = candidate.lstat().st_mode
            except OSError:
                ignored.add(name)
                continue
            if name in IGNORED_COPY_NESTED_NAMES:
                ignored.add(name)
                continue
            if matches_copy_ignore(root, candidate, copy_ignore_patterns):
                ignored.add(name)
                continue
            if stat.S_ISSOCK(mode) or stat.S_ISFIFO(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
                ignored.add(name)
        return ignored

    for item in root.iterdir():
        if item.name in IGNORED_COPY_NAMES:
            continue
        if matches_copy_ignore(root, item, copy_ignore_patterns):
            continue
        try:
            mode = item.lstat().st_mode
        except OSError:
            continue
        if stat.S_ISSOCK(mode) or stat.S_ISFIFO(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                target,
                ignore=ignore,
                dirs_exist_ok=True,
                symlinks=True,
            )
        else:
            shutil.copy2(item, target)


def run_ci_replay(runtime: LoopRuntime, *, phase: str, keep_temp: bool) -> int:
    state = load_state_or_fail(runtime.paths.state)
    runtime = LoopRuntime(
        root=runtime.root,
        python_bin=runtime.python_bin,
        adapter_script=state.get("adapter_script"),
        paths=runtime.paths,
    )

    replay_root = runtime.paths.artifact_dir / "ci-replay" / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    copy_repo_tree(runtime.root, replay_root)
    restore_snapshot(replay_root, runtime.paths.best_snapshot)

    replay_paths = LoopPaths(
        run_dir=runtime.paths.run_dir,
        artifact_dir=runtime.paths.artifact_dir / "ci-replay",
        metadata=runtime.paths.metadata,
        summary=runtime.paths.summary,
        results=runtime.paths.results,
        state=runtime.paths.state,
        best_snapshot=runtime.paths.best_snapshot,
        evaluations=runtime.paths.artifact_dir / "ci-replay" / "evaluations",
    )
    replay_runtime = LoopRuntime(
        root=replay_root,
        python_bin=runtime.python_bin,
        adapter_script=state.get("adapter_script"),
        paths=replay_paths,
    )
    replay_runtime.paths.evaluations.mkdir(parents=True, exist_ok=True)

    iterations: list[dict[str, Any]] = []
    if phase in {"dev", "both"}:
        dev_manifest = resolve_repo_path(replay_root, state["dev_manifest"])
        iterations.append(
            evaluate_manifest(
                replay_runtime,
                manifest_path=dev_manifest,
                phase="ci-dev",
                iteration=int(state["best_iteration"]),
            )
        )
    if phase in {"holdout", "both"}:
        holdout_manifest = resolve_repo_path(
            replay_root, state["holdout_manifest"], allow_external=True
        )
        iterations.append(
            evaluate_manifest(
                replay_runtime,
                manifest_path=holdout_manifest,
                phase="ci-holdout",
                iteration=int(state["best_iteration"]),
            )
        )

    payload = {
        "phase": phase,
        "working_copy": display_path(runtime.root, replay_root),
        "results": [
            {
                "phase": item["phase"],
                "score": item["score"],
                "artifact": display_path(runtime.root, replay_root / item["artifact"])
                if not Path(item["artifact"]).is_absolute()
                else item["artifact"],
            }
            for item in iterations
        ],
    }
    write_json(runtime.paths.artifact_dir / "ci-replay" / "summary.json", payload)

    placeholder_evaluation = {
        "score": state["best_score"],
        "artifact": state["best_artifact"],
    }
    record_result(
        runtime.paths,
        phase="ci-replay",
        iteration=int(state["best_iteration"]),
        decision="observe",
        evaluation=placeholder_evaluation,
        note=f"ci replay phase={phase}",
        extra=payload,
    )

    if not keep_temp:
        remove_path(replay_root)
        payload["working_copy"] = "<removed>"
        write_json(runtime.paths.artifact_dir / "ci-replay" / "summary.json", payload)

    print(f"CI replay completed for phase={phase}")
    return 0
