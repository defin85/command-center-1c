## 1. Repo-wide guidance contract
- [x] 1.1 Перестроить корневой `AGENTS.md` в компактный repo-wide invariant contract и вынести длинные procedural sections в routed docs.
- [x] 1.2 Явно описать precedence/conflict matrix для `AGENTS.md`, `docs/agent/*`, scoped `AGENTS.md`, `openspec/project.md` и skills.
- [x] 1.3 Обновить `docs/agent/INDEX.md`, чтобы он отражал новый core-vs-routed contract без конкурирующих кратких summary blocks.

## 2. Routing and completion profiles
- [x] 2.1 Уточнить `docs/agent/TASK_ROUTING.md` как bounded router с minimum-required read set и route-specific escalation points для каждой task family.
- [x] 2.2 Перевести completion policy из одного универсального `done` в task-class profiles как минимум для `analysis/review`, `local change`, `delivery`.
- [x] 2.3 Синхронизировать `docs/agent/VERIFY.md`, `docs/agent/PLANS.md` и `docs/agent/code_review.md` с новой task-class completion model.

## 3. Project memory governance
- [x] 3.1 Добавить stable checked-in memory policy для Hindsight/manual memory с recall/retain triggers и note taxonomy.
- [x] 3.2 Ограничить memory contract high-signal note types (`repo-fact`, `gotcha`, `verified-fix`, `active-change-note`) и запретить session-noise как default retain path.
- [x] 3.3 Обновить root/canonical guidance так, чтобы memory policy была discoverable, но не дублировалась во всех layers.

## 4. Freshness automation
- [x] 4.1 Расширить `check-agent-doc-freshness` на новую instruction structure и критичные references task-class/memory surfaces.
- [x] 4.2 Проверить, что compact root contract не конфликтует с routed docs и scoped guidance по source-of-truth ссылкам.

## 5. Validation
- [x] 5.1 Прогнать `./scripts/dev/check-agent-doc-freshness.sh`.
- [x] 5.2 Прогнать `openspec validate refactor-agent-guidance-governance --strict --no-interactive`.
