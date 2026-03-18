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

# Язык (важно)

- Планы, спеки и описания change ведём на русском языке.
- Общепринятые термины, названия сущностей, API/эндпоинты, ключи настроек и code identifiers можно оставлять на английском.

## UI Platform Contract

- Основной UI stack проекта: `antd` + `@ant-design/pro-components` + project-owned thin design layer в `frontend/src/components/platform`.
- Для catalog/detail/authoring surfaces сначала использовать platform primitives:
  - `WorkspacePage`
  - `PageHeader`
  - `MasterDetailShell`
  - `EntityTable`
  - `EntityDetails`
  - `DrawerFormShell`
  - `StatusBadge`
  - `JsonBlock`
- `MasterDetail` на узких viewport обязан деградировать в `list + Drawer`; horizontal overflow как основной режим недопустим.
- Для `/decisions` и `/pools/binding-profiles` page-level композиция должна идти через platform layer; обход raw `antd` containers на уровне route-page считается нарушением governance и ловится линтером.
- Не вводить вторую primary design system (`shadcn/ui`, `MUI`, Radix-first page shells и т.п.) без отдельного одобренного OpenSpec change.

# Unified Workflow

We operate in a cycle: **OpenSpec (What) → Beads (How) → Code (Implementation)**.

## 1. Intent Formation

OpenSpec creates a change folder (`openspec/changes/<change-id>/`) containing:

- `proposal.md`: business value and scope
- `tasks.md`: high-level task list
- `design.md`: technical design (optional)
- `specs/.../spec.md`: requirements and acceptance criteria

**Agent Goal**: edit these files until they represent a signable contract.

**DO NOT proceed to step 2 until approval is explicit.**
Explicit approval can be either:
- the keyword `Go!` in English; or
- a direct invocation of `/openspec-to-beads <change-id>`.

## 2. Task Transformation

Once the change is approved, execute:
`/openspec-to-beads <change-id>`

The agent must:

1. Read the change files.
2. Create a Beads Epic for the feature and reference `openspec/changes/<change-id>/`.
3. Create Beads Tasks for each item in `tasks.md`.
4. Set dependencies.

Result: a **live task graph in `.beads/`**, not just text.

## 3. Execution

Work loop:

- `bd ready`
- `bd show <task-id>`
- implement code
- `bd close <task-id>`
- `bd vc status`
- `bd vc commit -m "..."`

**Rules:**
- For code changes, only work on tasks listed in `bd ready`.
- For non-code requests (analysis, review, research without code edits), Beads tracking is recommended but not mandatory.
- Newly discovered work must be tracked as a separate issue with dependency `discovered-from:<parent-id>`.

## 4. Fixation

When all tasks are complete, execute:

- `/openspec-apply <change-id>`
- `/openspec-archive <change-id>`

## Agent Mental Checklist

1. Is there an active OpenSpec change?
   - No → create one
   - Yes → read `proposal.md` and `tasks.md`
2. Are tasks tracked in Beads?
   - No → generate graph
   - Yes → work from `bd ready`
3. Keep OpenSpec (Intent) ↔ Beads (Plan) ↔ Code (Reality) in sync.

## OpenSpec Delivery Contract (Mandatory)

- Before coding for an OpenSpec change, build an execution matrix from `spec.md` requirements/scenarios to target files and tests.
- Every MUST/Requirement/Scenario must have automated evidence (`test`) or an explicitly approved exception from the user.
- Statuses `partially implemented` or `not implemented` for mandatory requirements block task completion and hand-off.
- If any mandatory requirement cannot be delivered now, stop and escalate with concrete blockers and options.
- Final delivery report must include `Requirement -> Code -> Test` evidence with concrete file paths.

## Issue Tracking

This project uses **bd (beads)** for issue tracking.
Run `bd prime` for workflow context.

**Rules:**
- Use `bd` as the source of truth for code-change tracking.
- Do not use markdown TODO lists as a parallel tracker.
- Prefer `--json` in programmatic/agent flows.
- Use `bd vc status` / `bd vc commit` for Beads VC.
- `bd sync` is deprecated/no-op and must not be used as a sync step.
- In repositories with `dolt_mode: "server"`, do not use `bd dolt pull/push`.
- Check `bd ready` before starting code work.

## Search Playbook

Search order:

1. `mcp__claude-context__search_code`
2. `ast-index search "<query>"` if the repository uses `ast-index` or semantic search is noisy
3. `rg`
4. `rg --files`

Optional sidecar: `rlm-tools`

- Use `rlm-tools` for low-context exploration when broad `grep`/file reads would dump too much raw text into the conversation.
- Start with `rlm_start(path, query)`, then use `rlm_execute(session_id, code)` to batch 3-5 related operations in one call: `grep/glob -> read top matches -> aggregate -> print only the conclusion`.
- Prefer local helpers only: `read_file`, `read_files`, `grep`, `grep_summary`, `grep_read`, `glob_files`, `tree`.
- Do not use `llm_query` / `llm_query_batched` by default. They require an external API and are not local-only exploration.
- Treat `rlm-tools` output as exploratory evidence, not final proof. Confirm final facts with direct code evidence via `rg` and targeted file reads.
- Always close the session with `rlm_end(session_id)` when the exploration thread is complete.

Checklist:

1. Formulate the query as `component + action + context`.
2. First pass: `limit: 6-10`.
3. Set `extensionFilter` immediately.
4. If results are noisy, rephrase using concrete entities.
5. Confirm facts in at least 2 sources: code + test/spec/README.
6. Do not treat TODO/checklists/status files as proof of implementation.

## Indexing

- For manual reindexing, use `force=true`.
- Use one canonical absolute repo path with trailing `/`.
- Use the same path for `index/status/clear/search`.
- If mixed path keys were used before, clear old keys once and continue only with the canonical path.

## Landing the Plane (Session Completion)

**When ending a work session, work is NOT complete until `git push` succeeds.**

Mandatory workflow:

1. File issues for remaining work
2. Run quality gates (if code changed)
3. Update issue status
4. `git pull --rebase`
5. `bd vc status`
6. if needed: `bd vc commit -m "..."`
7. `git push`
8. `git status` must show “up to date with origin”
9. Clean up and hand off

**Critical rules:**
- Never stop before push succeeds
- Never leave work stranded locally
- If push fails, resolve and retry until it succeeds
- If push is blocked by an external constraint or explicit user restriction, report the blocker explicitly and stop

## Project Overlay

### Поиск по коду
Использовать следующий порядок:

1. `mcp__claude-context__search_code`
2. `ast-index search "<query>"`
3. `rg`

Дополнительно допускается `rlm-tools` как sidecar для low-context exploration, когда широкий `grep`/чтение файлов создаёт слишком много сырого вывода.
- Типовой сценарий: `rlm_start` на корне репо -> 1-3 вызова `rlm_execute` с батчем `grep/read/summary` -> подтверждение фактов через `rg` и точечное чтение файлов -> `rlm_end`.
- `rlm-tools` не считать источником истины: итоговые утверждения подтверждать прямыми ссылками на код.
- `llm_query` и `llm_query_batched` по умолчанию не использовать.

### Чек-лист поиска
1. Формулировать запрос как `объект + действие + контекст`.
2. Первый проход делать с `limit: 6-10`.
3. Сразу задавать `extensionFilter`:
   - backend: `.py`
   - frontend: `.ts`, `.tsx`
4. Для `ast-index` перед первым поиском выполнять `ast-index rebuild` из корня репо.
5. Если в топе много шума, переформулировать запрос через конкретные сущности.
6. После семантического поиска подтверждать факт в коде через `rg`/чтение файлов.
7. Проверять минимум 2-3 источника: код + тест + контракт/spec.
8. Не считать checklist/status доказательством реализации без проверки исходников.
9. Для API-контрактов в `contracts/**/*.yaml` при шуме сразу переходить к `rg`.

### Индексация
- Игнор-паттерны задаются централизованно в `.codex/config.toml`.
- Канонический корень: `/home/egor/code/command-center-1c/`
- Использовать его одинаково для:
  - `mcp__claude-context__index_codebase`
  - `mcp__claude-context__get_indexing_status`
  - `mcp__claude-context__clear_index`
  - `mcp__claude-context__search_code`

### Локальная отладка
Практические runtime-команды собраны в `DEBUG.md`:
- `./debug/runtime-inventory.sh`
- `./debug/probe.sh all`
- `./debug/restart-runtime.sh <runtime>`
- `./debug/eval-django.sh "<python code>"`
- `./debug/eval-frontend.sh "<js expression>"`
