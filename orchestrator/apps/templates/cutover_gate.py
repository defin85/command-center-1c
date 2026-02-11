from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_SWITCH_CONTOUR_PATHS = [
    "orchestrator/apps/templates/workflow/handlers/operation.py",
    "orchestrator/apps/api_internal/views_templates.py",
    "orchestrator/apps/api_v2/views/rbac/operation_templates.py",
    "orchestrator/apps/api_v2/views/rbac/effective_access.py",
    "orchestrator/apps/templates/rbac.py",
    "orchestrator/apps/operations/factory.py",
    "orchestrator/apps/operations/services/operations_service/message.py",
]

FORBIDDEN_TOKENS = [
    "OperationTemplate",
    "OperationTemplatePermission",
    "OperationTemplateGroupPermission",
]


@dataclass(frozen=True)
class GateViolation:
    path: str
    line: int
    token: str
    snippet: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "token": self.token,
            "snippet": self.snippet,
        }


def _resolve_paths(paths: Iterable[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in paths:
        candidate = Path(str(raw))
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        resolved.append(candidate.resolve())
    return resolved


def run_operation_template_reference_gate(
    *,
    paths: list[str] | None = None,
) -> dict[str, object]:
    selected = list(paths or DEFAULT_SWITCH_CONTOUR_PATHS)
    resolved_paths = _resolve_paths(selected)

    violations: list[GateViolation] = []
    missing_paths: list[str] = []
    scanned_files = 0

    for file_path in resolved_paths:
        if not file_path.exists():
            missing_paths.append(str(file_path))
            continue
        if file_path.is_dir():
            missing_paths.append(str(file_path))
            continue
        scanned_files += 1
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = file_path.read_text(encoding="latin-1").splitlines()
        for idx, line in enumerate(lines, start=1):
            for token in FORBIDDEN_TOKENS:
                if token not in line:
                    continue
                snippet = line.strip()
                if len(snippet) > 200:
                    snippet = snippet[:200]
                violations.append(
                    GateViolation(
                        path=str(file_path),
                        line=idx,
                        token=token,
                        snippet=snippet,
                    )
                )

    return {
        "scope": "runtime_internal_rbac_switch",
        "scanned_files": scanned_files,
        "checked_paths": [str(path) for path in resolved_paths],
        "missing_paths": missing_paths,
        "forbidden_tokens": list(FORBIDDEN_TOKENS),
        "violations": [item.to_dict() for item in violations],
        "violation_count": len(violations),
        "status": "pass" if not violations and not missing_paths else "fail",
    }

