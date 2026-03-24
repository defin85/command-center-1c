# Claude Rules Directory

> Статус: legacy/non-authoritative Claude rules index.
> Для текущего agent-facing onboarding используйте [../../docs/agent/INDEX.md](../../docs/agent/INDEX.md).

> Модульные правила для AI-агентов. Автоматически загружаются Claude Code.

## Structure

```
.claude/rules/
├── critical.md        # Always loaded: status, constraints, ports
├── quick-start.md     # Commands, endpoints, monitoring
├── development.md     # Dev rules, monorepo structure, tech stack
├── shell-rules.md     # Shell rules for AI (WSL/Arch specific)
├── api-contracts.md   # OpenAPI workflow (paths: contracts/**)
├── testing.md         # Testing & linting requirements
├── setup.md           # Initial setup & troubleshooting
├── documentation.md   # Documentation links
└── README.md          # This file
```

## Path-Specific Rules

Some rules use `paths:` frontmatter to load only when working with specific files:

| File | Paths | Description |
|------|-------|-------------|
| `api-contracts.md` | `contracts/**/*.yaml` | Loads when editing OpenAPI specs |

## Adding New Rules

1. Create `.md` file in this directory
2. Optionally add `paths:` frontmatter for conditional loading:

```markdown
---
paths: frontend/**/*.tsx
---

# React Component Rules
...
```

## Priority Order

1. Enterprise policy (if configured)
2. Project rules (`.claude/rules/*.md`)
3. Project memory (`CLAUDE.md`)
4. User memory (`~/.claude/CLAUDE.md`)

## Check Loaded Rules

Use `/memory` command in Claude Code to see which rules are currently loaded.
