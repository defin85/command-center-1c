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
Frontend:15173 → API Gateway:8180 → Orchestrator:8200 → Redis:6379
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

---

**Version:** 4.0
**Updated:** 2025-12-10

**Changes v4.0:**
- Migrated to modular `.claude/rules/` structure
- Reduced main CLAUDE.md from ~512 to ~60 lines
- Added path-specific rules for contracts
