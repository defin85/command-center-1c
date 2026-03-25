#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLAUDE_RULE_DOCS = sorted((ROOT / ".claude/rules").glob("*.md"))

AUTHORITATIVE_DOCS = [
    ROOT / "AGENTS.md",
    ROOT / "openspec/project.md",
    ROOT / "frontend/AGENTS.md",
    ROOT / "orchestrator/AGENTS.md",
    ROOT / "go-services/AGENTS.md",
    ROOT / "docs/agent/INDEX.md",
    ROOT / "docs/agent/ARCHITECTURE_MAP.md",
    ROOT / "docs/agent/DOMAIN_MAP.md",
    ROOT / "docs/agent/RUNBOOK.md",
    ROOT / "docs/agent/VERIFY.md",
    ROOT / "docs/agent/TASK_ROUTING.md",
    ROOT / "docs/agent/PLANS.md",
    ROOT / "docs/agent/code_review.md",
]

LEGACY_DOCS = [
    ROOT / "CLAUDE.md",
    ROOT / "docs/START_HERE.md",
    ROOT / "docs/INDEX.md",
    ROOT / "docs/DEBUG_WITH_AI.md",
    ROOT / ".claude/README.md",
    *CLAUDE_RULE_DOCS,
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

FRONTEND_SMOKE_SCRIPTS = [
    "generate:api",
    "lint",
    "test:run",
    "test:browser:ui-platform",
    "validate:ui-platform",
]

FRONTEND_COMPOSITE_SMOKE_COMPONENTS = {
    "validate:ui-platform": (
        "generate:api",
        "lint",
        "test:run",
        "test:browser:ui-platform",
        "build:assets",
    ),
}

SHARED_SKILLS = [
    ROOT / ".agents/skills/runtime-debug/SKILL.md",
    ROOT / ".agents/skills/pool-run-verification/SKILL.md",
    ROOT / ".agents/skills/openspec-change-delivery/SKILL.md",
]

SKILL_REQUIRED_SECTIONS = [
    "## What This Skill Does",
    "## When To Use",
    "## Inputs",
    "## Outputs",
    "## Workflow",
    "## Success Criteria",
    "## Practical Job",
]

REPO_PREFIXES = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "DEBUG.md",
    ".tool-versions",
    ".beads/",
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


def get_runtime(inventory: list[dict[str, str]], runtime_name: str) -> dict[str, str]:
    for runtime in inventory:
        if runtime["runtime"] == runtime_name:
            return runtime
    raise KeyError(f"Runtime not found in inventory: {runtime_name}")


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
    if " " in candidate:
        leading = candidate.split(maxsplit=1)[0]
        if leading.startswith(("./", "../")) or leading.startswith(REPO_PREFIXES):
            candidate = leading
    if not candidate or "*" in candidate or "<" in candidate or ">" in candidate:
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


def require_line_with_tokens(
    errors: list[str],
    text: str,
    path: Path,
    description: str,
    tokens: tuple[str, ...],
) -> None:
    if any(all(token in line for token in tokens) for line in text.splitlines()):
        return

    joined = ", ".join(tokens)
    errors.append(
        f"{path.relative_to(ROOT)} missing semantic reference for {description}: {joined}"
    )


def require_section_contains(
    errors: list[str],
    section_text: str,
    path: Path,
    section_name: str,
    needle: str,
) -> None:
    if needle not in section_text:
        errors.append(
            f"{path.relative_to(ROOT)} section {section_name} must contain: {needle}"
        )


def extract_markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return ""

    start += len(marker)
    remainder = text[start:]
    next_heading = remainder.find("\n## ")
    if next_heading == -1:
        return remainder
    return remainder[:next_heading]


def require_command_success(
    errors: list[str],
    description: str,
    command: list[str],
    *,
    cwd: Path | None = None,
) -> None:
    result = subprocess.run(
        command,
        cwd=cwd or ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return

    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    detail = stderr or stdout or f"exit code {result.returncode}"
    first_line = detail.splitlines()[0]
    errors.append(f"{description} failed: {first_line}")


def build_frontend_smoke_command(script_name: str) -> list[str]:
    package_path = ROOT / "frontend/package.json"
    composite_scripts = FRONTEND_COMPOSITE_SMOKE_COMPONENTS.get(script_name)
    if composite_scripts is None:
        return [
            "npm",
            "--prefix",
            str(ROOT / "frontend"),
            "run",
            script_name,
            "--",
            "--help",
        ]

    python_program = """
import json
import sys
from pathlib import Path

package = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
script_name = sys.argv[2]
expected = sys.argv[3:]
script = package["scripts"][script_name]
parts = [part.strip() for part in script.split("&&")]
index = 0

for required in expected:
    target = f"npm run {required}"
    while index < len(parts) and parts[index] != target:
        index += 1
    if index == len(parts):
        raise SystemExit(
            f"missing {target} in composite frontend script {script_name}: {script}"
        )
    index += 1
""".strip()
    return [
        sys.executable,
        "-c",
        python_program,
        str(package_path),
        script_name,
        *composite_scripts,
    ]


def check_runtime_doc_semantics(
    errors: list[str],
    inventory: list[dict[str, str]],
    *,
    arch_map: str,
    runbook: str,
    verify: str,
) -> None:
    arch_map_path = ROOT / "docs/agent/ARCHITECTURE_MAP.md"
    runbook_path = ROOT / "docs/agent/RUNBOOK.md"
    verify_path = ROOT / "docs/agent/VERIFY.md"

    for runtime in inventory:
        runtime_token = f"`{runtime['runtime']}`"
        require_line_with_tokens(
            errors,
            arch_map,
            arch_map_path,
            f"architecture runtime row for {runtime['runtime']}",
            (runtime_token, runtime["stack"], runtime["entrypoint"]),
        )
        require_contains(errors, arch_map, runtime["health"], arch_map_path)
        require_line_with_tokens(
            errors,
            runbook,
            runbook_path,
            f"runbook runtime row for {runtime['runtime']}",
            (runtime_token, runtime["start"], runtime["health"]),
        )
        require_line_with_tokens(
            errors,
            verify,
            verify_path,
            f"verify runtime row for {runtime['runtime']}",
            (runtime_token, runtime["tests"]),
        )


def check_task_routing_semantics(
    errors: list[str],
    inventory: list[dict[str, str]],
    *,
    task_routing: str,
) -> None:
    task_routing_path = ROOT / "docs/agent/TASK_ROUTING.md"
    frontend_section = extract_markdown_section(task_routing, "Frontend work")
    orchestrator_section = extract_markdown_section(task_routing, "Orchestrator work")
    go_section = extract_markdown_section(task_routing, "Go services work")
    contracts_section = extract_markdown_section(task_routing, "Contracts и OpenSpec work")
    runtime_debug_section = extract_markdown_section(task_routing, "Runtime-debug и live verification")
    docs_section = extract_markdown_section(task_routing, "Agent docs и guidance work")

    frontend_runtime = get_runtime(inventory, "frontend")
    orchestrator_runtime = get_runtime(inventory, "orchestrator")
    api_gateway_runtime = get_runtime(inventory, "api-gateway")
    worker_runtime = get_runtime(inventory, "worker")

    require_section_contains(errors, frontend_section, task_routing_path, "Frontend work", frontend_runtime["entrypoint"])
    require_section_contains(errors, frontend_section, task_routing_path, "Frontend work", "frontend/src/App.tsx")
    require_section_contains(errors, frontend_section, task_routing_path, "Frontend work", "cd frontend && npm run generate:api")
    require_section_contains(errors, frontend_section, task_routing_path, "Frontend work", "cd frontend && npm run lint")
    require_section_contains(errors, frontend_section, task_routing_path, "Frontend work", frontend_runtime["tests"])
    require_section_contains(errors, frontend_section, task_routing_path, "Frontend work", "cd frontend && npm run test:browser:ui-platform")
    require_section_contains(errors, frontend_section, task_routing_path, "Frontend work", "frontend/package.json")
    require_section_contains(errors, frontend_section, task_routing_path, "Frontend work", "./debug/runtime-inventory.sh --json")

    require_section_contains(errors, orchestrator_section, task_routing_path, "Orchestrator work", orchestrator_runtime["entrypoint"])
    require_section_contains(errors, orchestrator_section, task_routing_path, "Orchestrator work", "./scripts/dev/lint.sh --python")
    require_section_contains(errors, orchestrator_section, task_routing_path, "Orchestrator work", orchestrator_runtime["tests"])
    require_section_contains(errors, orchestrator_section, task_routing_path, "Orchestrator work", "./debug/runtime-inventory.sh --json")

    require_section_contains(errors, go_section, task_routing_path, "Go services work", api_gateway_runtime["entrypoint"])
    require_section_contains(errors, go_section, task_routing_path, "Go services work", api_gateway_runtime["tests"])
    require_section_contains(errors, go_section, task_routing_path, "Go services work", worker_runtime["entrypoint"])
    require_section_contains(errors, go_section, task_routing_path, "Go services work", worker_runtime["tests"])
    require_section_contains(errors, go_section, task_routing_path, "Go services work", "./scripts/dev/lint.sh --go")
    require_section_contains(errors, go_section, task_routing_path, "Go services work", "./debug/runtime-inventory.sh --json")

    require_section_contains(errors, contracts_section, task_routing_path, "Contracts и OpenSpec work", "openspec validate <change-id> --strict --no-interactive")
    require_section_contains(errors, contracts_section, task_routing_path, "Contracts и OpenSpec work", "./scripts/dev/check-agent-doc-freshness.sh")
    require_section_contains(errors, contracts_section, task_routing_path, "Contracts и OpenSpec work", "openspec list")
    require_section_contains(errors, contracts_section, task_routing_path, "Contracts и OpenSpec work", "openspec list --specs")
    require_section_contains(errors, contracts_section, task_routing_path, "Contracts и OpenSpec work", "bd ready")

    require_section_contains(errors, runtime_debug_section, task_routing_path, "Runtime-debug и live verification", "./debug/runtime-inventory.sh --json")
    require_section_contains(errors, runtime_debug_section, task_routing_path, "Runtime-debug и live verification", "./scripts/dev/health-check.sh")
    require_section_contains(errors, runtime_debug_section, task_routing_path, "Runtime-debug и live verification", "./debug/probe.sh all")
    require_section_contains(errors, runtime_debug_section, task_routing_path, "Runtime-debug и live verification", "./debug/restart-runtime.sh <runtime>")

    require_section_contains(errors, docs_section, task_routing_path, "Agent docs и guidance work", "./scripts/dev/check-agent-doc-freshness.sh")
    require_section_contains(errors, docs_section, task_routing_path, "Agent docs и guidance work", "openspec validate <change-id> --strict --no-interactive")
    require_section_contains(errors, docs_section, task_routing_path, "Agent docs и guidance work", "frontend/package.json")
    require_section_contains(errors, docs_section, task_routing_path, "Agent docs и guidance work", "./debug/runtime-inventory.sh --json")
    require_section_contains(errors, docs_section, task_routing_path, "Agent docs и guidance work", ".codex/config.toml")


def main() -> int:
    errors: list[str] = []

    for path in AUTHORITATIVE_DOCS + LEGACY_DOCS + SUPPLEMENTAL_DOCS + SHARED_SKILLS:
        if not path.exists():
            errors.append(f"Missing required doc: {path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    texts = {path: read(path) for path in AUTHORITATIVE_DOCS + LEGACY_DOCS + SUPPLEMENTAL_DOCS + SHARED_SKILLS}
    versions = parse_tool_versions()
    inventory = load_inventory()
    package_scripts = load_package_scripts()
    codex_config = read(ROOT / ".codex/config.toml")

    root_agents = texts[ROOT / "AGENTS.md"]
    project_context = texts[ROOT / "openspec/project.md"]
    index_doc = texts[ROOT / "docs/agent/INDEX.md"]
    arch_map = texts[ROOT / "docs/agent/ARCHITECTURE_MAP.md"]
    domain_map = texts[ROOT / "docs/agent/DOMAIN_MAP.md"]
    runbook = texts[ROOT / "docs/agent/RUNBOOK.md"]
    verify = texts[ROOT / "docs/agent/VERIFY.md"]
    task_routing = texts[ROOT / "docs/agent/TASK_ROUTING.md"]
    readme = texts[ROOT / "README.md"]
    claude_readme = texts[ROOT / ".claude/README.md"]
    frontend_agents = texts[ROOT / "frontend/AGENTS.md"]
    orchestrator_agents = texts[ROOT / "orchestrator/AGENTS.md"]
    go_agents = texts[ROOT / "go-services/AGENTS.md"]

    require_contains(errors, root_agents, "docs/agent/INDEX.md", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, "docs/agent/DOMAIN_MAP.md", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, "docs/agent/RUNBOOK.md", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, "docs/agent/VERIFY.md", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, "docs/agent/TASK_ROUTING.md", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, ".codex/config.toml", ROOT / "AGENTS.md")
    require_contains(errors, root_agents, "./debug/runtime-inventory.sh --json", ROOT / "AGENTS.md")

    require_contains(errors, project_context, "docs/agent/INDEX.md", ROOT / "openspec/project.md")
    require_not_contains(errors, project_context, ".claude/rules/setup.md", ROOT / "openspec/project.md")
    require_not_contains(errors, project_context, ".claude/rules/testing.md", ROOT / "openspec/project.md")
    require_not_contains(errors, project_context, ".claude/rules/critical.md", ROOT / "openspec/project.md")

    require_contains(errors, index_doc, ".agents/skills/runtime-debug/SKILL.md", ROOT / "docs/agent/INDEX.md")
    require_contains(errors, index_doc, ".agents/skills/pool-run-verification/SKILL.md", ROOT / "docs/agent/INDEX.md")
    require_contains(errors, index_doc, ".agents/skills/openspec-change-delivery/SKILL.md", ROOT / "docs/agent/INDEX.md")
    require_contains(errors, index_doc, ".beads/", ROOT / "docs/agent/INDEX.md")
    require_contains(errors, index_doc, "DOMAIN_MAP.md", ROOT / "docs/agent/INDEX.md")
    require_contains(errors, index_doc, "TASK_ROUTING.md", ROOT / "docs/agent/INDEX.md")
    require_not_contains(errors, readme, "[CLAUDE.md]", ROOT / "README.md")
    require_not_contains(errors, claude_readme, "CLAUDE.md", ROOT / ".claude/README.md")

    require_contains(errors, domain_map, "frontend/src/App.tsx", ROOT / "docs/agent/DOMAIN_MAP.md")
    require_contains(errors, domain_map, "/operations", ROOT / "docs/agent/DOMAIN_MAP.md")
    require_contains(errors, domain_map, "/workflows", ROOT / "docs/agent/DOMAIN_MAP.md")
    require_contains(errors, domain_map, "/decisions", ROOT / "docs/agent/DOMAIN_MAP.md")
    require_contains(errors, domain_map, "/pools/catalog", ROOT / "docs/agent/DOMAIN_MAP.md")
    require_contains(errors, domain_map, "/pools/execution-packs", ROOT / "docs/agent/DOMAIN_MAP.md")
    require_contains(errors, domain_map, "openspec list", ROOT / "docs/agent/DOMAIN_MAP.md")
    require_contains(errors, domain_map, "openspec/changes/archive/", ROOT / "docs/agent/DOMAIN_MAP.md")

    require_contains(errors, task_routing, "## Вопросы про продукт и домен", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "## Frontend work", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "## Orchestrator work", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "## Go services work", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "## Contracts и OpenSpec work", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "## Runtime-debug и live verification", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "## Agent docs и guidance work", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "frontend/package.json", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "./debug/runtime-inventory.sh --json", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "./scripts/dev/check-agent-doc-freshness.sh", ROOT / "docs/agent/TASK_ROUTING.md")
    require_contains(errors, task_routing, "bd ready", ROOT / "docs/agent/TASK_ROUTING.md")

    require_contains(errors, runbook, f"Go {versions['go']}", ROOT / "docs/agent/RUNBOOK.md")
    require_contains(errors, runbook, f"Python {versions['python']}", ROOT / "docs/agent/RUNBOOK.md")
    require_contains(errors, runbook, f"Node.js {versions['nodejs']}", ROOT / "docs/agent/RUNBOOK.md")
    require_contains(errors, runbook, f"Java {versions['java']}", ROOT / "docs/agent/RUNBOOK.md")
    require_contains(errors, codex_config, f'nvm exec --silent {versions["nodejs"]}', ROOT / ".codex/config.toml")
    require_not_contains(errors, codex_config, "openspec/changes/**", ROOT / ".codex/config.toml")
    require_not_contains(errors, codex_config, "/home/egor/", ROOT / ".codex/config.toml")

    check_runtime_doc_semantics(
        errors,
        inventory,
        arch_map=arch_map,
        runbook=runbook,
        verify=verify,
    )
    check_task_routing_semantics(
        errors,
        inventory,
        task_routing=task_routing,
    )

    for script_name in PACKAGE_SCRIPTS_REQUIRED:
        if script_name not in package_scripts:
            errors.append(f"frontend/package.json is missing npm script: {script_name}")
        require_contains(
            errors,
            verify + root_agents,
            f"npm run {script_name}",
            ROOT / "docs/agent/VERIFY.md",
        )

    require_contains(errors, frontend_agents, "npm run lint", ROOT / "frontend/AGENTS.md")
    require_contains(errors, frontend_agents, "npm run test:run", ROOT / "frontend/AGENTS.md")
    require_contains(errors, frontend_agents, "npm run test:browser:ui-platform", ROOT / "frontend/AGENTS.md")
    require_contains(errors, frontend_agents, "npm run validate:ui-platform", ROOT / "frontend/AGENTS.md")
    require_contains(errors, frontend_agents, "docs/agent/INDEX.md", ROOT / "frontend/AGENTS.md")
    require_contains(errors, frontend_agents, "docs/agent/TASK_ROUTING.md", ROOT / "frontend/AGENTS.md")
    require_contains(errors, orchestrator_agents, "docs/agent/INDEX.md", ROOT / "orchestrator/AGENTS.md")
    require_contains(errors, orchestrator_agents, "./scripts/dev/lint.sh --python", ROOT / "orchestrator/AGENTS.md")
    require_contains(errors, orchestrator_agents, "./scripts/dev/pytest.sh -q <path>", ROOT / "orchestrator/AGENTS.md")
    require_contains(errors, orchestrator_agents, "docs/agent/TASK_ROUTING.md", ROOT / "orchestrator/AGENTS.md")
    require_contains(errors, go_agents, "docs/agent/INDEX.md", ROOT / "go-services/AGENTS.md")
    require_contains(errors, go_agents, "./scripts/dev/lint.sh --go", ROOT / "go-services/AGENTS.md")
    require_contains(errors, go_agents, "cd go-services/api-gateway && go test ./...", ROOT / "go-services/AGENTS.md")
    require_contains(errors, go_agents, "cd go-services/worker && go test ./...", ROOT / "go-services/AGENTS.md")
    require_contains(errors, go_agents, "docs/agent/TASK_ROUTING.md", ROOT / "go-services/AGENTS.md")

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

    for path in SHARED_SKILLS:
        text = texts[path]
        for section in SKILL_REQUIRED_SECTIONS:
            require_contains(errors, text, section, path)

    for path in AUTHORITATIVE_DOCS + SUPPLEMENTAL_DOCS + SHARED_SKILLS:
        for referenced in collect_path_like_tokens(path, texts[path]):
            if referenced == path:
                continue
            if not referenced.exists():
                errors.append(
                    f"{path.relative_to(ROOT)} references missing local path: {referenced.relative_to(ROOT)}"
                )

    require_command_success(
        errors,
        "bash syntax check for debug/runtime-inventory.sh",
        ["bash", "-n", str(ROOT / "debug/runtime-inventory.sh")],
    )
    require_command_success(
        errors,
        "bash syntax check for scripts/dev/check-agent-doc-freshness.sh",
        ["bash", "-n", str(ROOT / "scripts/dev/check-agent-doc-freshness.sh")],
    )
    require_command_success(
        errors,
        "python syntax check for scripts/dev/check-agent-doc-freshness.py",
        ["python3", "-m", "py_compile", str(ROOT / "scripts/dev/check-agent-doc-freshness.py")],
    )
    require_command_success(
        errors,
        "runtime inventory JSON smoke check",
        [str(ROOT / "debug/runtime-inventory.sh"), "--json"],
    )
    require_command_success(
        errors,
        "runtime inventory text smoke check",
        [str(ROOT / "debug/runtime-inventory.sh")],
    )
    require_command_success(
        errors,
        "openspec list smoke check",
        ["openspec", "list"],
    )
    require_command_success(
        errors,
        "openspec list --specs smoke check",
        ["openspec", "list", "--specs"],
    )
    require_command_success(
        errors,
        "openspec validate help smoke check",
        ["openspec", "validate", "--help"],
    )
    require_command_success(
        errors,
        "bd ready smoke check",
        ["bd", "ready"],
    )

    if (ROOT / "frontend/node_modules").exists():
        for script_name in FRONTEND_SMOKE_SCRIPTS:
            require_command_success(
                errors,
                f"frontend {script_name} help smoke check",
                build_frontend_smoke_command(script_name),
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
