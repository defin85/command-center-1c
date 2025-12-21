#!/usr/bin/env python3
"""
CommandCenter1C - Service Configuration Generator

Generates configuration files from config/services.json (Single Source of Truth):
- generated/.env.services - Environment variables for all services
- generated/ports.go - Go constants package
- generated/frontend.env - Vite environment variables (VITE_* prefixes)
- generated/docker-compose.ports.yml - Docker Compose port mappings
- docs/generated/PORTS.md - Auto-documentation

Usage:
    python scripts/config/generate.py --mode local   # Local development (default)
    python scripts/config/generate.py --mode docker  # Docker environment

Requirements:
    Python 3.11+ (stdlib only, no external dependencies)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# =============================================================================
# Constants
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "services.json"
SCHEMA_FILE = PROJECT_ROOT / "config" / "services.schema.json"
GENERATED_DIR = PROJECT_ROOT / "generated"
DOCS_GENERATED_DIR = PROJECT_ROOT / "docs" / "generated"
GO_PORTS_DIR = PROJECT_ROOT / "go-services" / "shared" / "ports"

HEADER_COMMENT = """# =============================================================================
# AUTO-GENERATED FILE - DO NOT EDIT MANUALLY
# =============================================================================
# Source: config/services.json
# Generated: {timestamp}
# Mode: {mode}
# Generator: scripts/config/generate.py
# =============================================================================
"""

GO_HEADER = """// =============================================================================
// AUTO-GENERATED FILE - DO NOT EDIT MANUALLY
// =============================================================================
// Source: config/services.json
// Generated: {timestamp}
// Mode: {mode}
// Generator: scripts/config/generate.py
// =============================================================================

"""


# =============================================================================
# Validation
# =============================================================================

def validate_schema(config: dict, schema: dict) -> list[str]:
    """
    Basic JSON Schema validation (stdlib only, no jsonschema dependency).
    Returns list of validation errors.
    """
    errors = []

    # Check required top-level fields
    for field in ["version", "services", "infrastructure"]:
        if field not in config:
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors

    # Check version format
    version = config.get("version", "")
    if not isinstance(version, str) or not version:
        errors.append("version must be a non-empty string")

    # Check services
    services = config.get("services", {})
    required_services = [
        "frontend",
        "api-gateway",
        "orchestrator",
        "worker",
    ]
    for svc in required_services:
        if svc not in services:
            errors.append(f"Missing required service: {svc}")
        else:
            svc_errors = validate_service(svc, services[svc])
            errors.extend(svc_errors)

    # Check infrastructure
    infrastructure = config.get("infrastructure", {})
    required_infra = ["postgresql", "redis", "prometheus", "grafana", "jaeger", "ras"]
    for infra in required_infra:
        if infra not in infrastructure:
            errors.append(f"Missing required infrastructure: {infra}")
        else:
            infra_errors = validate_service(infra, infrastructure[infra], is_infra=True)
            errors.extend(infra_errors)

    # Check for duplicate ports
    errors.extend(validate_unique_ports(config))

    return errors


def validate_service(name: str, svc: dict, is_infra: bool = False) -> list[str]:
    """Validate a single service definition."""
    errors = []

    # Check port
    port = svc.get("port")
    if not isinstance(port, int) or port < 1 or port > 65535:
        errors.append(f"{name}: port must be integer 1-65535, got {port}")

    # Check host
    host = svc.get("host")
    if not isinstance(host, dict):
        errors.append(f"{name}: host must be an object")
    else:
        if "docker" not in host or not isinstance(host["docker"], str):
            errors.append(f"{name}: host.docker must be a string")
        if "local" not in host or not isinstance(host["local"], str):
            errors.append(f"{name}: host.local must be a string")

    # Check health_path (required for services, optional for infra)
    if not is_infra and "health_path" not in svc:
        errors.append(f"{name}: health_path is required")

    # Check description
    if "description" not in svc or not isinstance(svc.get("description"), str):
        errors.append(f"{name}: description is required and must be a string")

    return errors


def validate_unique_ports(config: dict) -> list[str]:
    """Validate that all ports are unique across services and infrastructure."""
    errors = []
    ports = {}

    # Check services
    for name, svc in config.get("services", {}).items():
        port = svc.get("port")
        if port in ports:
            errors.append(f"Port {port} conflict: '{name}' and '{ports[port]}'")
        else:
            ports[port] = name

    # Check infrastructure
    for name, infra in config.get("infrastructure", {}).items():
        port = infra.get("port")
        if port in ports:
            errors.append(f"Port {port} conflict: '{name}' and '{ports[port]}'")
        else:
            ports[port] = name

    return errors


# =============================================================================
# Generators
# =============================================================================

def generate_env_services(config: dict, mode: str, timestamp: str) -> str:
    """Generate .env.services file content."""
    lines = [HEADER_COMMENT.format(timestamp=timestamp, mode=mode)]

    host_key = mode  # "local" or "docker"

    # Service URLs
    lines.append("")
    lines.append("# =============================================================================")
    lines.append("# Service URLs")
    lines.append("# =============================================================================")

    for name, svc in config["services"].items():
        host = svc["host"][host_key]
        port = svc["port"]
        var_name = name.upper().replace("-", "_") + "_URL"
        lines.append(f"{var_name}=http://{host}:{port}")

    # Service Ports
    lines.append("")
    lines.append("# =============================================================================")
    lines.append("# Service Ports")
    lines.append("# =============================================================================")

    for name, svc in config["services"].items():
        port = svc["port"]
        env_var = svc.get("env_var", name.upper().replace("-", "_") + "_PORT")
        lines.append(f"{env_var}={port}")

    # Infrastructure Ports
    lines.append("")
    lines.append("# =============================================================================")
    lines.append("# Infrastructure Ports")
    lines.append("# =============================================================================")

    for name, infra in config["infrastructure"].items():
        port = infra["port"]
        env_var = infra.get("env_var", name.upper().replace("-", "_") + "_PORT")
        host = infra["host"][host_key]
        lines.append(f"{env_var}={port}")
        # Also add HOST variable for infrastructure
        host_var = name.upper().replace("-", "_") + "_HOST"
        lines.append(f"{host_var}={host}")

    lines.append("")
    return "\n".join(lines)


def generate_ports_go(config: dict, mode: str, timestamp: str) -> str:
    """Generate ports.go file content."""
    lines = [GO_HEADER.format(timestamp=timestamp, mode=mode)]
    lines.append("package ports")
    lines.append("")
    lines.append('import "fmt"')
    lines.append("")

    # Port constants
    lines.append("// Service ports")
    lines.append("const (")

    for name, svc in config["services"].items():
        const_name = to_go_const(name)
        lines.append(f"\t{const_name} = {svc['port']}")

    lines.append(")")
    lines.append("")

    # Infrastructure ports
    lines.append("// Infrastructure ports")
    lines.append("const (")

    for name, infra in config["infrastructure"].items():
        const_name = to_go_const(name)
        lines.append(f"\t{const_name} = {infra['port']}")

    lines.append(")")
    lines.append("")

    # Host key for mode
    host_key = mode

    # Default URLs constants
    lines.append("// Default service URLs (for config fallbacks)")
    lines.append("const (")

    default_url_services = [
        "frontend",
        "api-gateway",
        "orchestrator",
        "worker",
    ]
    for name in default_url_services:
        if name in config["services"]:
            svc = config["services"][name]
            const_name = "Default" + to_go_const(name) + "URL"
            host = svc["host"][host_key]
            port = svc["port"]
            lines.append(f'\t{const_name} = "http://{host}:{port}"')

    lines.append(")")
    lines.append("")

    # ServiceURLs map
    lines.append("// ServiceURLs maps service names to their URLs")
    lines.append("var ServiceURLs = map[string]string{")

    for name, svc in config["services"].items():
        host = svc["host"][host_key]
        port = svc["port"]
        lines.append(f'\t"{name}": "http://{host}:{port}",')

    lines.append("}")
    lines.append("")

    # ServiceHealthPaths map
    lines.append("// ServiceHealthPaths maps service names to their health check paths")
    lines.append("var ServiceHealthPaths = map[string]string{")

    for name, svc in config["services"].items():
        health_path = svc.get("health_path")
        if health_path:
            lines.append(f'\t"{name}": "{health_path}",')

    lines.append("}")
    lines.append("")

    # Address builder functions
    lines.append("// Address builders for http.ListenAndServe")

    addr_services = [
        "frontend",
        "api-gateway",
        "orchestrator",
        "worker",
    ]
    for name in addr_services:
        if name in config["services"]:
            func_name = to_go_const(name) + "Addr"
            const_name = to_go_const(name)
            lines.append(f'func {func_name}() string {{ return fmt.Sprintf(":%d", {const_name}) }}')

    lines.append("")

    return "\n".join(lines)


def generate_frontend_env(config: dict, mode: str, timestamp: str) -> str:
    """Generate frontend.env file content for Vite."""
    lines = [HEADER_COMMENT.format(timestamp=timestamp, mode=mode)]

    host_key = mode

    # API Gateway URL for frontend
    api_gateway = config["services"]["api-gateway"]
    api_host = api_gateway["host"][host_key]
    api_port = api_gateway["port"]

    lines.append("")
    lines.append("# API Gateway URL (for REST API calls)")
    lines.append(f"VITE_API_URL=http://{api_host}:{api_port}/api/v2")
    lines.append("")

    # WebSocket host (Orchestrator for real-time updates)
    orchestrator = config["services"]["orchestrator"]
    ws_host = orchestrator["host"][host_key]
    ws_port = orchestrator["port"]

    lines.append("# WebSocket host (for real-time updates)")
    lines.append(f"VITE_WS_HOST={ws_host}:{ws_port}")
    lines.append("")

    # All service URLs (for debugging/admin panels)
    lines.append("# Service URLs (for debugging/admin)")
    for name, svc in config["services"].items():
        host = svc["host"][host_key]
        port = svc["port"]
        var_name = "VITE_" + name.upper().replace("-", "_") + "_URL"
        lines.append(f"{var_name}=http://{host}:{port}")

    lines.append("")
    return "\n".join(lines)


def generate_docker_compose_ports(config: dict, mode: str, timestamp: str) -> str:
    """Generate docker-compose.ports.yml file content."""
    lines = [HEADER_COMMENT.format(timestamp=timestamp, mode=mode).replace("#", "# ")]

    lines.append("")
    lines.append("# Use this file with: docker-compose -f docker-compose.yml -f generated/docker-compose.ports.yml up")
    lines.append("")
    lines.append("version: '3.8'")
    lines.append("")
    lines.append("services:")

    # Application services
    for name, svc in config["services"].items():
        port = svc["port"]
        docker_name = name
        lines.append(f"  {docker_name}:")
        lines.append(f"    ports:")
        lines.append(f'      - "{port}:{port}"')
        lines.append("")

    # Infrastructure services
    for name, infra in config["infrastructure"].items():
        port = infra["port"]
        docker_name = infra["host"]["docker"]
        lines.append(f"  {docker_name}:")
        lines.append(f"    ports:")
        lines.append(f'      - "{port}:{port}"')
        lines.append("")

    return "\n".join(lines)


def generate_ports_md(config: dict, mode: str, timestamp: str) -> str:
    """Generate PORTS.md documentation file."""
    lines = [
        "# CommandCenter1C - Port Configuration",
        "",
        "> **AUTO-GENERATED FILE - DO NOT EDIT MANUALLY**",
        f"> Source: `config/services.json`",
        f"> Generated: {timestamp}",
        "",
        "## Application Services",
        "",
        "| Service | Port | Health Check | Description |",
        "|---------|------|--------------|-------------|",
    ]

    for name, svc in config["services"].items():
        port = svc["port"]
        health = svc.get("health_path") or "-"
        desc = svc.get("description", "")
        lines.append(f"| {name} | {port} | `{health}` | {desc} |")

    lines.extend([
        "",
        "## Infrastructure Services",
        "",
        "| Service | Port | Host (Docker) | Host (Local) | Description |",
        "|---------|------|---------------|--------------|-------------|",
    ])

    for name, infra in config["infrastructure"].items():
        port = infra["port"]
        docker_host = infra["host"]["docker"]
        local_host = infra["host"]["local"]
        desc = infra.get("description", "")
        lines.append(f"| {name} | {port} | {docker_host} | {local_host} | {desc} |")

    lines.extend([
        "",
        "## Environment Variables",
        "",
        "### Service Ports",
        "",
        "```bash",
    ])

    for name, svc in config["services"].items():
        env_var = svc.get("env_var", name.upper().replace("-", "_") + "_PORT")
        lines.append(f"{env_var}={svc['port']}")

    lines.extend([
        "```",
        "",
        "### Infrastructure",
        "",
        "```bash",
    ])

    for name, infra in config["infrastructure"].items():
        env_var = infra.get("env_var", name.upper().replace("-", "_") + "_PORT")
        lines.append(f"{env_var}={infra['port']}")

    lines.extend([
        "```",
        "",
        "## Quick Reference",
        "",
        "### Local Development URLs",
        "",
        "```",
    ])

    for name, svc in config["services"].items():
        port = svc["port"]
        health = svc.get("health_path")
        url = f"http://localhost:{port}"
        if health:
            url += health
        lines.append(f"{name}: {url}")

    lines.extend([
        "```",
        "",
        "---",
        "",
        "*This file is auto-generated. To update, modify `config/services.json` and run:*",
        "",
        "```bash",
        "python scripts/config/generate.py --mode local",
        "```",
        "",
    ])

    return "\n".join(lines)


# =============================================================================
# Helpers
# =============================================================================

def to_go_const(name: str) -> str:
    """Convert service name to Go constant name (PascalCase)."""
    parts = name.split("-")
    return "".join(part.capitalize() for part in parts)


def ensure_dir(path: Path) -> None:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def normalize_content(content: str) -> str:
    """Remove timestamp from content for comparison."""
    # Matches patterns like "Generated: 2025-12-07 09:50:16" or "> Generated: ..."
    return re.sub(r"(>?\s*Generated:\s*)\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", r"\1TIMESTAMP", content)


def write_file(path: Path, content: str, verbose: bool = False) -> None:
    """Write content to file only if it changed (ignoring timestamp)."""
    ensure_dir(path.parent)

    # Check if file exists and content is the same (ignoring timestamp)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if normalize_content(existing) == normalize_content(content):
            if verbose:
                print(f"  [SKIP] {path.relative_to(PROJECT_ROOT)} (unchanged)")
            return

    path.write_text(content, encoding="utf-8")
    if verbose:
        print(f"  [OK] {path.relative_to(PROJECT_ROOT)}")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate configuration files from config/services.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/config/generate.py --mode local   # Local development
  python scripts/config/generate.py --mode docker  # Docker environment
  python scripts/config/generate.py --verbose      # Show detailed output
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["local", "docker"],
        default="local",
        help="Target environment mode (default: local)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate config, don't generate files",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("CommandCenter1C - Service Configuration Generator")
    print("=" * 60)
    print(f"Mode: {args.mode}")
    print(f"Config: {CONFIG_FILE.relative_to(PROJECT_ROOT)}")
    print()

    # Load config
    if not CONFIG_FILE.exists():
        print(f"[ERROR] Config file not found: {CONFIG_FILE}")
        sys.exit(1)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in config file: {e}")
        sys.exit(1)

    # Load schema (optional, for future validation)
    schema = None
    if SCHEMA_FILE.exists():
        try:
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                schema = json.load(f)
        except json.JSONDecodeError:
            print("[WARN] Could not load schema file, skipping advanced validation")

    # Validate
    print("[1/2] Validating configuration...")
    errors = validate_schema(config, schema or {})

    if errors:
        print("[ERROR] Validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print("  [OK] Configuration is valid")
    print()

    if args.validate_only:
        print("[OK] Validation complete (--validate-only mode)")
        sys.exit(0)

    # Generate files
    print("[2/2] Generating files...")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = args.mode
    verbose = args.verbose

    # Ensure directories exist
    ensure_dir(GENERATED_DIR)
    ensure_dir(DOCS_GENERATED_DIR)
    ensure_dir(GO_PORTS_DIR)

    # Generate all files
    files_to_generate = [
        (GENERATED_DIR / ".env.services", generate_env_services(config, mode, timestamp)),
        (GO_PORTS_DIR / "ports.go", generate_ports_go(config, mode, timestamp)),
        (GENERATED_DIR / "frontend.env", generate_frontend_env(config, mode, timestamp)),
        (GENERATED_DIR / "docker-compose.ports.yml", generate_docker_compose_ports(config, mode, timestamp)),
        (DOCS_GENERATED_DIR / "PORTS.md", generate_ports_md(config, mode, timestamp)),
    ]

    for path, content in files_to_generate:
        write_file(path, content, verbose)
        if not verbose:
            print(f"  [OK] {path.relative_to(PROJECT_ROOT)}")

    print()
    print("=" * 60)
    print("[OK] Generation complete!")
    print("=" * 60)
    print()
    print("Generated files:")
    for path, _ in files_to_generate:
        print(f"  - {path.relative_to(PROJECT_ROOT)}")
    print()
    print("Usage:")
    print("  # Source environment variables:")
    print("  source generated/.env.services")
    print()
    print("  # Copy to frontend:")
    print("  cp generated/frontend.env frontend/.env.local")
    print()


if __name__ == "__main__":
    main()
