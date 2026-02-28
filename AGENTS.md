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

- Планы и спеки ведём на русском языке: OpenSpec (`openspec/specs/**`, `openspec/changes/**`) и описания задач/планов в процессе работы.
- Общепринятые термины, названия сущностей, API/эндпоинты, ключи настроек и code identifiers можно оставлять на английском, но общий смысл должен быть понятен без перевода.

# Unified Workflow

We operate in a cycle: **OpenSpec (What) → Beads (How) → Code (Implementation)**.

## 1. Intent Formation

The user initiates with:
`/openspec-proposal "Add 2FA authentication"`

OpenSpec creates a change folder (`openspec/changes/<change-id>/`) containing:

- `proposal.md`: Business value and scope.
- `tasks.md`: High-level task list.
- `design.md`: Technical design (optional).
- `specs/.../spec.md`: Requirements and acceptance criteria.

**Agent Goal**: Edit these files until they represent a signable contract.

**DO NOT proceed to step 2 until you are explicitly told the keyword "Go!" in English.**

## 2. Task Transformation

Once the change is approved, execute the agent command:
`/openspec-to-beads <change-id>`

The agent must:

1.  Read the change files.
2.  Create a Beads Epic for the feature. Include a short description summarizing the intent and referencing the change folder (e.g., "See openspec/changes/<change-id>/").
3.  Create Beads Tasks for each item in `tasks.md`. Include a brief description for each task to provide context (why this issue exists and what needs to be done).
4.  Set dependencies (e.g., Infra blocks Backend blocks Frontend).

Result: A **live task graph in `.beads/`**, not just text.

## 3. Execution

Work loop:

- `bd ready`: Check actionable tasks
- `bd show <task-id>`: Get task context
- Implement code
- `bd close <task-id>`: Complete task
- `bd sync`: Sync state

**Rule**: For code changes, only work on tasks listed in `bd ready`.

If the user requests a code change that is not tracked in Beads yet:

- Create an ad-hoc issue with `bd create ...`
- Make sure it becomes actionable
- Continue implementation from `bd ready`

For non-code requests (analysis, explanations, review without code edits, research), Beads tracking is recommended but not mandatory.

## 4. Fixation

When all tasks are complete, execute the agent commands:

- `/openspec-apply <change-id>`: Verify code meets specs.
- Then, when ready,
- `/openspec-archive <change-id>`: Archive the change.

---

## Agent Mental Checklist

1.  **Start**: Is there an active OpenSpec change?
    - No? → Create one (`/openspec-proposal`).
    - Yes? → Read `proposal.md` and `tasks.md`.
2.  **Plan**: Are tasks tracked in Beads?
    - No? → Generate graph (`/openspec-to-beads`).
    - Yes? → Work from `bd ready`.
3.  **Align**: Keep OpenSpec (Intent) ↔ Beads (Plan) ↔ Code (Reality) in sync.

---

## Landing the Plane (Session Completion)

**When ending a work session with commits in this repository**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   - `git pull --rebase`
   - `bd sync`
   - `git push`
   - `git status` - MUST show "up to date with origin"
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**

- Work is NOT complete until `git push` succeeds (for sessions with commits in this repository)
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
- If push is blocked by an external constraint (no access/permissions, remote outage, or explicit user restriction), report the blocker explicitly and stop

## Issue Tracking

This project uses **bd (beads)** for issue tracking.
Run `bd prime` for workflow context.

**Quick reference:**

- `bd ready` - Find unblocked work
- `bd create "Title" --type task --priority 2 --description "..."` - Create ad-hoc issue
- `bd close <task-id>` - Complete work
- `bd sync` - Sync with git (run at session end)

For full workflow details: `bd prime`

### Beads sync-branch: “постоянно меняется .beads/issues.jsonl”

В этом репозитории Beads работает в режиме sync-branch (по умолчанию `sync-branch: beads-sync` в `.beads/config.yaml`).
В таком режиме `.beads/*.jsonl` часто меняются из-за daemon/auto-flush и **не должны** постоянно “грязнить” рабочее дерево
на ветках с кодом.

Если после коммита у вас регулярно появляется `M .beads/issues.jsonl`:

- Рекомендовано: `bd doctor --fix` (исправляет git index flags для Beads файлов).
- Быстрый ручной фикс (локально):
  - `git update-index --skip-worktree .beads/issues.jsonl .beads/interactions.jsonl .beads/config.yaml .beads/metadata.json`
- Откатить (если нужно снова видеть изменения):
  - `git update-index --no-skip-worktree .beads/issues.jsonl .beads/interactions.jsonl .beads/config.yaml .beads/metadata.json`

## Семантический поиск (claude-context / ast-index)

При поиске по коду использовать следующий порядок:

1. `mcp__claude-context__search_code` (семантический поиск, основной путь)
2. `ast-index search "<query>"` (второй вариант: локальный AST-поиск, если `claude-context` недоступен или даёт шум)
3. `rg` (точечная верификация по найденным путям)

Чек-лист для эффективного поиска:

1. Формулировать запрос как `объект + действие + контекст` (например: `action catalog fixed schema save payload`).
2. Первый проход делать с `limit: 6-10`.
3. Сразу задавать `extensionFilter` под задачу:
   - backend: `.py`
   - frontend: `.ts`, `.tsx`
4. Для `ast-index` перед первым поиском в репозитории выполнять `ast-index rebuild` из корня репо.
5. Если в топе много шума, переформулировать запрос через конкретные сущности (`ActionCatalogEditorModal`, `get_action_catalog_editor_hints`, `executor.fixed`).
6. После семантического поиска подтверждать факт в коде через `rg`/чтение файлов.
7. Проверять минимум 2-3 источника: код + тест + контракт/spec.
8. Не считать checklist/status доказательством реализации без проверки исходников.
9. Для API-контрактов в `contracts/**/*.yaml` сначала пробовать семпоиск, но при пустой/шумной выдаче сразу переходить к `rg` по endpoint/schema.

## Индексация (уменьшение шума)

При ручной переиндексации использовать `force=true`.
Игнор-паттерны для индексации задаются централизованно в `.codex/config.toml`.

Важно: для `claude-context` использовать один и тот же канонический абсолютный путь с завершающим `/`.

- Рекомендованный корень в этом репозитории: `/home/egor/code/command-center-1c/`
- Использовать этот путь одинаково во всех командах:
  - `mcp__claude-context__index_codebase`
  - `mcp__claude-context__get_indexing_status`
  - `mcp__claude-context__clear_index`
  - `mcp__claude-context__search_code`
- Не смешивать варианты с `/` и без `/`: инструмент может воспринимать их как разные индексные ключи.

## Локальная отладка (autonomous-feedback-loop)

Практические команды runtime-debugging собраны в `DEBUG.md`:
- inventory: `./debug/runtime-inventory.sh`
- probes: `./debug/probe.sh all`
- restart+probe: `./debug/restart-runtime.sh <runtime>`
- django eval: `./debug/eval-django.sh "<python code>"`
- frontend eval: `./debug/eval-frontend.sh "<js expression>"`
