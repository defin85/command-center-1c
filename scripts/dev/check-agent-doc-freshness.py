#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

AUTHORITATIVE_DOCS = [
    ROOT / "AGENTS.md",
    ROOT / "openspec/project.md",
    ROOT / "frontend/AGENTS.md",
    ROOT / "orchestrator/AGENTS.md",
    ROOT / "go-services/AGENTS.md",
    ROOT / "docs/agent/INDEX.md",
    ROOT / "docs/agent/ARCHITECTURE_MAP.md",
    ROOT / "docs/agent/RUNBOOK.md",
    ROOT / "docs/agent/VERIFY.md",
    ROOT / "docs/agent/PLANS.md",
    ROOT / "docs/agent/code_review.md",
]

LEGACY_DOCS = [
    ROOT / "docs/START_HERE.md",
    ROOT / "docs/INDEX.md",
    ROOT / "docs/DEBUG_WITH_AI.md",
    ROOT / ".claude/README.md",
    ROOT / ".claude/rules/quick-start.md",
]

SUPPLEMENTAL_DOCS = [
    ROOT / "README.md",
    ROOT / "DEBUG.md",
    ROOT / "scripts/dev/README.md",
]

PACKAGE_SCRIPTS_REQUIRED = [
    "generate:api",
    "lint",
    "test:run",
    "test:browser:ui-platform",
    "validate:ui-platform",
]

REPO_PREFIXES = (
    "AGENTS.md",
    "README.md",
    "DEBUG.md",
    ".tool-versions",
    ".codex/",
    ".agents/",
    ".claude/",
    "docs/",
    "debug/",
    "scripts/",
    "frontend/",
    "orchestrator/",
    "go-services/",
    "openspec/",
    "contracts/",
)

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
CODE_RE = re.compile(r"`([^`\n]+)`")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_tool_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for raw_line in read(ROOT / ".tool-versions").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        tool, version = line.split(maxsplit=1)
        versions[tool] = version
    return versions


def load_inventory() -> list[dict[str, str]]:
    output = subprocess.check_output(
        [str(ROOT / "debug/runtime-inventory.sh"), "--json"],
        text=True,
    )
    return json.loads(output)


def load_package_scripts() -> dict[str, str]:
    package_json = json.loads(read(ROOT / "frontend/package.json"))
    return package_json["scripts"]


def normalize_local_path(raw: str, base_dir: Path, *, dot_relative_to_root: bool) -> Path | None:
    candidate = raw.strip()
    if not candidate:
        return None
    if candidate.startswith(("http://", "https://", "mailto:")):
        return None
    if candidate.startswith("@/"):
        candidate = candidate[2:]
    elif candidate.startswith("@"):
        return None
    if candidate.startswith("/") and not candidate.startswith(str(ROOT)):
        return None
    if "#" in candidate:
        candidate = candidate.split("#", 1)[0]
    candidate = candidate.strip()
    if not candidate or "*" in candidate or "<" in candidate or ">" in candidate:
        return None
    if " " in candidate and not candidate.startswith("docs/agent/"):
        return None
    if "->" in candidate:
        return None
    if "(" in candidate or ")" in candidate:
        return None
    if dot_relative_to_root and candidate.startswith("./"):
        return (ROOT / candidate[2:]).resolve()
    if candidate.startswith(("./", "../")):
        return (base_dir / candidate).resolve()
    if not candidate.startswith(REPO_PREFIXES):
        return None
    return ROOT / candidate


def collect_path_like_tokens(path: Path, text: str) -> set[Path]:
    found: set[Path] = set()
    for raw in LINK_RE.findall(text):
        normalized = normalize_local_path(raw, path.parent, dot_relative_to_root=False)
        if normalized is not None:
            found.add(normalized)
    for raw in CODE_RE.findall(text):
        normalized = normalize_local_path(raw, path.parent, dot_relative_to_root=True)
        if normalized is not None:
            found.add(normalized)
    return found


def require_contains(errors: list[str], text: str, needle: str, path: Path) -> None:
    if needle not in text:
        errors.append(f"{path.relative_to(ROOT)} must contain: {needle}")


def require_not_contains(errors: list[str], text: str, needle: str, path: Path) -> None:
    if needle in text:
        errors.append(f"{path.relative_to(ROOT)} must not contain: {needle}")


def main() -> int:
    errors: list[str] = []

    for path in AUTHORITATIVE_DOCS + LEGACY_DOCS + SUPPLEMENTAL_DOCS:
        if not path.exists():
            errors.append(f"Missing required doc: {path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    texts = {path: read(path) for path in AUTHORITATIVE_DOCS + LEGACY_DOCS + SUPPLEMENTAL_DOCS}
    versions = parse_tool_versions()
    inventory = load_inventory()
    package_scripts = load_package_scripts()

    root_agents = texts[ROOT / "AGENTS.md"]
    require_contains(errors, root_agents, "docs/agent/INDEX.md", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, "docs/agent/RUNBOOK.md", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, "docs/agent/VERIFY.md", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, ".codex/config.toml", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, "./debug/runtime-inventory.sh --json", ROOT / "AGENTS.md")

    project_context = texts[ROOT / "openspec/project.md"]
    require_contains(errors, project_context, "docs/agent/INDEX.md", ROOT / "openspec/project.md")
    runbook = texts[ROOT / "docs/agent/RUNBOOK.md"]
    arch_map = texts[ROOT / "docs/agent/ARCHITECTURE_MAP.md"]
    verify = texts[ROOT / "docs/agent/VERIFY.md"]
    index_doc = texts[ROOT / "docs/agent/INDEX.md"]

    require_contains(errors, index_doc, ".agents/skills/runtime-debug/SKILL.md", ROOT / "docs/agent/INDEX.md")
    require_contains(errors, index_doc, ".agents/skills/pool-run-verification/SKILL.md", ROOT / "docs/agent/INDEX.md")
    require_contains(errors, index_doc, ".agents/skills/openspec-change-delivery/SKILL.md", ROOT / "docs/agent/INDEX.md")

    require_contains(errors, runbook, f"Go {versions['go']}", ROOT / "docs/agent/RUNBOOK.md")
    require_contains(errors, runbook, f"Python {versions['python']}", ROOT / "docs/agent/RUNBOOK.md")
    require_contains(errors, runbook, f"Node.js {versions['nodejs']}", ROOT / "docs/agent/RUNBOOK.md")
    require_contains(errors, runbook, f"Java {versions['java']}", ROOT / "docs/agent/RUNBOOK.md")

    for runtime in inventory:
        require_contains(errors, arch_map, runtime["entrypoint"], ROOT / "docs/agent/ARCHITECTURE_MAP.md")
        require_contains(errors, runbook, runtime["start"], ROOT / "docs/agent/RUNBOOK.md")
        require_contains(errors, runbook, runtime["health"], ROOT / "docs/agent/RUNBOOK.md")
        require_contains(errors, verify, runtime["tests"], ROOT / "docs/agent/VERIFY.md")

    for script_name in PACKAGE_SCRIPTS_REQUIRED:
        if script_name not in package_scripts:
            errors.append(f"frontend/package.json is missing npm script: {script_name}")
        require_contains(
            errors,
            verify + root_agents,
            f"npm run {script_name}",
            ROOT / "docs/agent/VERIFY.md",
        )

    for path in LEGACY_DOCS:
        text = texts[path]
        if "legacy/non-authoritative" not in text:
            errors.append(f"{path.relative_to(ROOT)} must declare legacy/non-authoritative status")
        if "docs/agent/INDEX.md" not in text:
            errors.append(f"{path.relative_to(ROOT)} must point to docs/agent/INDEX.md")

    for path in SUPPLEMENTAL_DOCS:
        text = texts[path]
        if "supplemental" not in text:
            errors.append(f"{path.relative_to(ROOT)} must declare supplemental status")
        if "docs/agent/INDEX.md" not in text:
            errors.append(f"{path.relative_to(ROOT)} must point to docs/agent/INDEX.md")

    for path in AUTHORITATIVE_DOCS:
        for referenced in collect_path_like_tokens(path, texts[path]):
            if referenced == path:
                continue
            if not referenced.exists():
                errors.append(
                    f"{path.relative_to(ROOT)} references missing local path: {referenced.relative_to(ROOT)}"
                )

    if errors:
        print("Agent doc freshness check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Agent doc freshness check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
