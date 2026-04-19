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

## Core Contract

- Корневой `AGENTS.md` является компактным repo-wide invariant contract: здесь живут только общие инварианты, precedence, completion profiles и обязательные inline contracts.
- Для cold start, неоднозначной задачи или быстрой карты guidance surfaces открывай `docs/agent/INDEX.md`.
- Для bounded task route по подсистеме открывай `docs/agent/TASK_ROUTING.md`.
- Для product/domain context используй `docs/agent/DOMAIN_MAP.md`.
- Для validation profiles и canonical checks используй `docs/agent/VERIFY.md`.
- Для runtime start/restart/eval используй `docs/agent/RUNBOOK.md` и `DEBUG.md`.
- Для manual Hindsight workflow и note taxonomy используй `docs/agent/MEMORY.md`.
- Machine-readable entry points: `.codex/config.toml`, `./debug/runtime-inventory.sh --json`, `frontend/package.json`, `scripts/dev/*`.

## Precedence Matrix

| Surface | Основная роль | Когда этот слой решает конфликт |
|---|---|---|
| `AGENTS.md` | repo-wide invariants, completion profiles, inline contracts | когда правило относится ко всему репозиторию |
| `docs/agent/*` | routed workflow, verification, onboarding maps, memory policy | когда нужен procedural route или authoritative reference asset |
| scoped `AGENTS.md` | subtree-local deltas | когда задача уже находится внутри `frontend/`, `orchestrator/`, `go-services/` |
| `openspec/AGENTS.md` + `openspec/project.md` | OpenSpec/project conventions | когда работа идёт через spec/change lifecycle |
| checked-in repo skills | повторяемые repo-local workflows | когда routed docs отправляют в конкретный `.agents/skills/*` |
| shared user-level skills | user-level specialization | когда checked-in guidance явно маршрутизирует в shared skill или пользователь назвал его напрямую |

Conflict rules:
- Более специфичный checked-in слой имеет приоритет над более общим.
- Для одинаковой конкретности checked-in repo guidance имеет приоритет над user-level/shared surfaces.
- Если два checked-in слоя одного уровня противоречат друг другу, применяй fail-closed: выбирай более безопасное и более bounded указание и явно фиксируй конфликт в ответе.

## Completion Profiles

- `analysis/review`: findings, assumptions, evidence и минимально достаточные read-only checks; по умолчанию не требует Beads/commit/push.
- `local change`: scoped checked-in edit плюс минимально релевантная автоматическая проверка и краткий handoff по touched paths; delivery-grade git actions не являются default expectation.
- `delivery`: merge-ready или approved OpenSpec execution; требует релевантные checks, alignment Beads/OpenSpec и затем `git pull --rebase`, commit и `git push`.
- Approved OpenSpec change implementation по умолчанию идёт как `delivery`.
- Если класс задачи неочевиден, выбирай более строгий профиль или эскалируй ambiguity.

## Repo Snapshot

- `frontend/`: React/Vite UI и platform-owned page layer.
- `orchestrator/`: Django orchestration и domain logic.
- `go-services/`: API Gateway и Worker binaries.
- `contracts/`: OpenAPI contracts и generated client sources.
- `debug/`: runtime probes, eval helpers и inventory.
- `scripts/dev/`: canonical local build/run/lint/test entry points.
- `openspec/`: source of truth для intent и requirements.
- `.beads/`: live execution graph для approved work.

## OpenSpec -> Beads -> Code

- OpenSpec intent живёт в `openspec/changes/<change-id>/`.
- Явное одобрение для Stage 2/3: `Go!` или `/openspec-to-beads <change-id>`.
- Для approved code changes создай или переиспользуй Beads graph и работай от `bd ready`.
- Newly discovered work оформляй отдельным Beads issue с явной dependency.
- Перед coding по OpenSpec change собери execution matrix `Requirement -> target files -> checks`.
- Каждый mandatory requirement требует automated evidence или явно одобренное исключение.
- Если mandatory requirement нельзя доставить, остановись и эскалируй blocker с вариантами.
- Финальный delivery handoff обязан содержать `Requirement -> Code -> Test`.

## Search Order

1. `mcp__claude_context__search_code`
2. `ast-index search "<query>"`
3. `rg`
4. `rg --files`

Rules:
- В этом репозитории semantic/indexed search имеет приоритет над text-search fallback.
- Если semantic tooling недоступен, сразу переходи к `rg` / `rg --files` и фиксируй это при необходимости.
- Confirm implementation facts как минимум в двух источниках: code + tests/spec/docs.
- Treat `rlm-tools` as exploratory only; final facts подтверждай direct file evidence.

## Machine-Readable Surfaces

- Codex repo config: `.codex/config.toml`
- Runtime inventory: `./debug/runtime-inventory.sh --json`
- Local debug toolkit: `DEBUG.md`
- Frontend validation entry points: `frontend/package.json`
- Dev scripts: `scripts/dev/*`
- OpenSpec project context: `openspec/project.md`

## UI Platform Contract

- Основной UI stack проекта: `antd` + `@ant-design/pro-components` + project-owned thin design layer в `frontend/src/components/platform`.
- UI skill routing lives in `docs/agent/ui-skills.md`; для frontend/UI задач агент должен активно использовать минимальный релевантный набор shared UI skills из `/home/egor/.agents/skills/`.
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
