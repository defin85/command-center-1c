# Agent Guidance Index

Статус: authoritative agent-facing guidance.

Этот каталог является canonical onboarding surface для cold start, неоднозначных задач и проверки source-of-truth слоёв. Для bounded task сначала прочитай root `AGENTS.md`, затем открывай `TASK_ROUTING.md`.

## Core Vs Routed Contract

- `AGENTS.md` — компактный repo-wide invariant contract: precedence, completion profiles, repo snapshot, inline UI contract.
- `TASK_ROUTING.md` — minimum-required route по task families и route-specific escalation points.
- `VERIFY.md` — canonical validation paths и task-class completion profiles.
- `RUNBOOK.md` — runtime start/restart/eval flows и debug entry points.
- `MEMORY.md` — manual Hindsight policy, recall/retain triggers и note taxonomy.
- `PLANS.md` и `code_review.md` — routed assets для multi-step execution и review/acceptance.

## Cold-Start Bundle

1. [ARCHITECTURE_MAP.md](./ARCHITECTURE_MAP.md) — runtime topology, entry points и allowed call graph.
2. [DOMAIN_MAP.md](./DOMAIN_MAP.md) — product purpose, operator outcomes и domain entities.
3. [TASK_ROUTING.md](./TASK_ROUTING.md) — bounded route к docs/code/checks.
4. [VERIFY.md](./VERIFY.md) — completion profiles и canonical validation paths.
5. [RUNBOOK.md](./RUNBOOK.md) — start/restart/eval flows.
6. [MEMORY.md](./MEMORY.md) — manual project memory policy.
7. [ui-skills.md](./ui-skills.md) — только когда задача касается frontend/UI/UX/browser verification.
8. [PLANS.md](./PLANS.md) — когда работа multi-step или неоднозначна.
9. [code_review.md](./code_review.md) — когда нужен review/acceptance mindset.

## Guidance Layers

### Authoritative

- `AGENTS.md`
- `docs/agent/*`
- `frontend/AGENTS.md`
- `orchestrator/AGENTS.md`
- `go-services/AGENTS.md`
- `openspec/project.md`

### Supplemental

- `README.md`
- `DEBUG.md`
- `scripts/dev/README.md`

### Legacy / Non-Authoritative

- `docs/START_HERE.md`
- `docs/INDEX.md`
- `docs/DEBUG_WITH_AI.md`
- `CLAUDE.md`
- `.claude/README.md`
- `.claude/rules/**`

Legacy documents могут сохранять полезный контекст, но не конкурируют с authoritative guidance. При конфликте источником истины остаются root `AGENTS.md`, `docs/agent/*` и scoped `AGENTS.md`.

## Machine-Readable Surfaces

- Codex repo config: `.codex/config.toml`
- Runtime inventory: `./debug/runtime-inventory.sh --json`
- Runtime probes and eval helpers: `./debug/probe.sh all`, `./debug/eval-django.sh`, `./debug/eval-frontend.sh`
- Frontend validation scripts: `frontend/package.json`
- Dev scripts: `scripts/dev/*`

## Scoped Guidance

- `frontend/AGENTS.md`
- `orchestrator/AGENTS.md`
- `go-services/AGENTS.md`
- `docs/agent/ui-skills.md` для frontend/UI/UX/browser tasks

## Skills Surfaces

Открывай конкретный `SKILL.md` только когда routed task совпадает с его workflow.

### Repo-Local Skills

- `runtime-debug` — `.agents/skills/runtime-debug/SKILL.md`
- `pool-run-verification` — `.agents/skills/pool-run-verification/SKILL.md`
- `openspec-change-delivery` — `.agents/skills/openspec-change-delivery/SKILL.md`
- `ui-action-observability` — `.agents/skills/ui-action-observability/SKILL.md`

### Shared User-Level Skills

Если routed workflow ссылается на общий skill, которого нет в checked-in `.agents/skills/`, ищи его в user-level каталоге `/home/egor/.agents/skills/`.

- UI skill routing для этого repo описан в [ui-skills.md](./ui-skills.md).
- Для frontend/UI задач default expectation: агент proactively выбирает минимальный релевантный набор shared UI skills, а не ждёт явного запроса пользователя.

- `frontend-design` — `/home/egor/.agents/skills/frontend-design/SKILL.md`
- `dogfood` — `/home/egor/.agents/skills/dogfood/SKILL.md`
- `critique` — `/home/egor/.agents/skills/critique/SKILL.md`
- `adapt` — `/home/egor/.agents/skills/adapt/SKILL.md`
- `harden` — `/home/egor/.agents/skills/harden/SKILL.md`
- `polish` — `/home/egor/.agents/skills/polish/SKILL.md`
- `normalize` — `/home/egor/.agents/skills/normalize/SKILL.md`
- `audit` — `/home/egor/.agents/skills/audit/SKILL.md`
- `openspec-architecture-plan-and-audit` — `/home/egor/.agents/skills/openspec-architecture-plan-and-audit/SKILL.md`
- `openspec-proposal` — `/home/egor/.agents/skills/openspec-proposal/SKILL.md`
- `openspec-apply` — `/home/egor/.agents/skills/openspec-apply/SKILL.md`
- `openspec-archive` — `/home/egor/.agents/skills/openspec-archive/SKILL.md`
- `openspec-finish-to-100` — `/home/egor/.agents/skills/openspec-finish-to-100/SKILL.md`
- `openspec-review-impl-vs-plan` — `/home/egor/.agents/skills/openspec-review-impl-vs-plan/SKILL.md`
- `openspec-review-impl-vs-plan-compact` — `/home/egor/.agents/skills/openspec-review-impl-vs-plan-compact/SKILL.md`
- `openspec-to-beads` — `/home/egor/.agents/skills/openspec-to-beads/SKILL.md`

## OpenSpec And Beads

- OpenSpec intent: `openspec/changes/<change-id>/`
- Active change list: `openspec list`
- Existing specs: `openspec list --specs`
- Execution graph: `.beads/`, `bd ready`, `bd show <id>`
