<!-- OPENSPEC:START -->

# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:

- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:

- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# Язык

- Планы, спеки и описания change ведём на русском языке.
- Общепринятые термины, названия сущностей, API/эндпоинты, ключи настроек и code identifiers можно оставлять на английском.

## Canonical Agent Surface

- Первый checked-in onboarding path для агента: `docs/agent/INDEX.md`.
- Authoritative agent guidance:
  - `AGENTS.md`
  - `docs/agent/*`
  - `frontend/AGENTS.md`
  - `orchestrator/AGENTS.md`
  - `go-services/AGENTS.md`
  - `openspec/project.md`
- Supplemental docs:
  - `README.md`
  - `DEBUG.md`
  - `scripts/dev/README.md`
- Legacy/non-authoritative onboarding layers:
  - `docs/START_HERE.md`
  - `docs/INDEX.md`
  - `docs/DEBUG_WITH_AI.md`
  - `CLAUDE.md`
  - `.claude/README.md`
  - `.claude/rules/**`

## Repo Snapshot

- `frontend/`: React/Vite UI.
- `orchestrator/`: Django orchestration and domain logic.
- `go-services/`: API Gateway and Worker binaries.
- `contracts/`: OpenAPI contracts and generated client sources.
- `debug/`: runtime probes and eval helpers.
- `scripts/dev/`: canonical local build, run, lint and test entry points.
- `openspec/`: source of truth for intent and requirements.
- `.beads/`: live execution graph for approved code changes.

Open these docs for the first 10 minutes of a task:
- `docs/agent/ARCHITECTURE_MAP.md`
- `docs/agent/RUNBOOK.md`
- `docs/agent/VERIFY.md`
- `docs/agent/PLANS.md`
- `docs/agent/code_review.md`
- `.agents/skills/*/SKILL.md`

## UI Platform Contract

- Основной UI stack проекта: `antd` + `@ant-design/pro-components` + project-owned thin design layer в `frontend/src/components/platform`.
- Для catalog/detail/authoring surfaces сначала использовать platform primitives:
  - `DashboardPage`
  - `WorkspacePage`
  - `PageHeader`
  - `MasterDetailShell`
  - `EntityList`
  - `EntityTable`
  - `EntityDetails`
  - `DrawerFormShell`
  - `ModalFormShell`
  - `StatusBadge`
  - `JsonBlock`
- `MasterDetail` на узких viewport обязан деградировать в `list + Drawer`; horizontal overflow как основной режим недопустим.
- `ModalFormShell` и `DrawerFormShell` являются canonical entry points для authoring/edit flows; raw `Modal`/inline page reflow не использовать как primary path.
- Для `/decisions` и `/pools/binding-profiles` page-level композиция должна идти через platform layer; обход raw `antd` containers на уровне route-page считается нарушением governance и ловится линтером.
- Blocking frontend gate для platform migrations: `npm run lint`, `npm run test:run`, `npm run test:browser:ui-platform`, затем production build.
- Не вводить вторую primary design system (`shadcn/ui`, `MUI`, Radix-first page shells и т.п.) без отдельного одобренного OpenSpec change.

## OpenSpec -> Beads -> Code

- OpenSpec describes intent in `openspec/changes/<change-id>/`.
- Explicit approval for Stage 2/3: `Go!` or `/openspec-to-beads <change-id>`.
- For approved code changes, create or reuse the Beads graph, then work from `bd ready`.
- Newly discovered work must become a separate Beads issue with an explicit dependency.
- When implementation is complete, run `/openspec-apply <change-id>` and `/openspec-archive <change-id>`.

## OpenSpec Delivery Contract

- Before coding for an OpenSpec change, build an execution matrix `Requirement -> target files -> tests/checks`.
- Every mandatory requirement or scenario needs automated evidence or an explicitly approved exception.
- If a mandatory requirement cannot be delivered, stop and escalate with blockers and options.
- Final delivery must include `Requirement -> Code -> Test` evidence with concrete file paths.

## Search Order

1. `mcp__claude-context__search_code`
2. `ast-index search "<query>"`
3. `rg`
4. `rg --files`

Rules:
- Confirm implementation facts in at least two sources: code + tests/spec/docs.
- Treat `rlm-tools` as exploratory only; confirm final facts via direct file evidence.
- Use the canonical repo root `/home/egor/code/command-center-1c/` for semantic indexing tools.

## Machine-Readable Surfaces

- Codex repo config: `.codex/config.toml`
- Runtime inventory: `./debug/runtime-inventory.sh --json`
- Local debug toolkit: `DEBUG.md`
- Frontend validation entry points: `frontend/package.json`
- Dev scripts: `scripts/dev/*`

## Verification And Done

- Use the smallest relevant validation set first, then widen only as needed.
- Canonical validation paths live in `docs/agent/VERIFY.md`.
- For docs and guidance changes, run `./scripts/dev/check-agent-doc-freshness.sh`.
- For OpenSpec changes, run `openspec validate <change-id> --strict --no-interactive`.
- Work is not complete until:
  - relevant checks pass
  - Beads statuses are updated
  - `git pull --rebase` succeeds
  - changes are committed and `git push` succeeds

## Local Debug

- Runtime commands and live-debug recipes: `docs/agent/RUNBOOK.md` and `DEBUG.md`
- Quick references:
  - `./debug/runtime-inventory.sh`
  - `./debug/probe.sh all`
  - `./debug/restart-runtime.sh <runtime>`
  - `./debug/eval-django.sh "<python code>"`
  - `./debug/eval-frontend.sh "<js expression>"`
