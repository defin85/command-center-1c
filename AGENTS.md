Отвечай только на русском языке.

# CommandCenter1C - AI Agent Instructions

> Микросервисная платформа для централизованного управления 700+ базами 1С

---

## Project Status

| Field | Value |
|-------|-------|
| **Phase** | Phase 2 - Extended Functionality |
| **Celery** | REMOVED - Go Worker единственный engine |
| **Dev Mode** | Native WSL (USE_DOCKER=false) |
| **API** | v2 (action-based) - `/api/v2/*` |
| **Roadmap** | Balanced (14-16 weeks) - `docs/ROADMAP.md` |

## Quick Commands

```bash
./scripts/dev/start-all.sh      # Start all services
./scripts/dev/health-check.sh   # Check health
./scripts/dev/lint.sh           # Lint all (--fix for auto-fix)
```

## Critical Constraints

- **1C Transactions < 15 seconds** - CRITICAL!
- **OData batch:** 100-500 records/batch
- **Coverage:** > 70%

## Architecture

```
Frontend:5173 → API Gateway:8180 → Orchestrator:8200 → Redis:6379
                                                        ↓
                                                   Go Worker → OData/RAS → 1C
```

## Rules

Detailed rules in `.claude/rules/`:

| File | Description |
|------|-------------|
| `critical.md` | Status, constraints, ports |
| `quick-start.md` | Commands, endpoints |
| `development.md` | Dev rules, monorepo structure |
| `shell-rules.md` | Shell rules for AI agents |
| `api-contracts.md` | OpenAPI workflow (paths: contracts/**) |
| `testing.md` | Testing & linting |
| `setup.md` | Setup & troubleshooting |
| `documentation.md` | Documentation links |

## LSP Tool (lspctl)

CLI for LSP JSON-RPC with JSON output: `tools/lspctl/lspctl.py`.

One-shot:

```bash
python tools/lspctl/lspctl.py definition --file path/to/file.go --line 10 --col 5
```

Daemon (recommended):

```bash
python tools/lspctl/lspctl.py serve --socket /tmp/lspctl.sock
python tools/lspctl/lspctl.py call hover --file path/to/file.go --line 10 --col 5 --socket /tmp/lspctl.sock
python tools/lspctl/lspctl.py shutdown --socket /tmp/lspctl.sock
```

Notes:
- All commands return JSON: `{"result": ...}` or `{"error": "..."}`.
- Use `--lang` if file extension is not supported or when using `workspaceSymbol`.

---

**Version:** 4.0
**Updated:** 2025-12-10

**Changes v4.0:**
- Migrated to modular `.claude/rules/` structure
- Reduced main CLAUDE.md from ~512 to ~60 lines
- Added path-specific rules for contracts
