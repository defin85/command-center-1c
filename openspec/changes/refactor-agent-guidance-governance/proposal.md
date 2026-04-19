# Change: Сжать и формализовать agent guidance governance для более дешёвого контекста

## Почему
Текущий agent-facing surface в репозитории уже сильный, но остаётся слишком плотным и частично самоконкурирующим:
- корневой `AGENTS.md` одновременно играет роль policy entry point, onboarding summary, workflow index, debug cheat sheet и completion contract;
- часть guidance повторяется между `AGENTS.md`, `docs/agent/*`, scoped `AGENTS.md`, skill routing и repo-local instruction blocks;
- task routing уже существует, но repo-level guidance всё ещё толкает агента к широкому чтению “первых 10 минут” даже для небольших и локальных задач;
- completion contract описан как один общий `done`, что подходит для merge-ready delivery, но перегружает analysis/review/doc-only задачи;
- правила ручной Hindsight memory описаны, но не сведены к строгому high-signal contract, поэтому банк легко деградирует в session log.

Проблема не в нехватке правил, а в стоимости их исполнения: агент тратит слишком много внимания на согласование layers и обязанностей между ними. Нужен отдельный governance-refactor, который сделает instruction surface компактнее, а маршрутизацию, completion policy и project memory более операциональными.

## Что меняется
- Корневой `AGENTS.md` переопределяется как компактный repo-wide invariant contract с явным разделением между `core rules` и routed/deeper guidance.
- В authoritative guidance вводится компактная precedence/conflict matrix, чтобы агент быстрее разрешал конфликты между root docs, scoped docs, OpenSpec surfaces и skills.
- Repository contract переходит от одного универсального `done` к task-class completion profiles как минимум для `analysis/review`, `local change`, `delivery`.
- `docs/agent/TASK_ROUTING.md` уточняется как bounded router с minimum-required read sets по task families, чтобы мелкие задачи не требовали чтения всего onboarding bundle.
- Для Hindsight/manual memory вводится checked-in policy с note taxonomy, recall/retain triggers и явным фильтром против session-noise.
- Doc freshness checks и agent-facing references приводятся к новой структуре, чтобы compact contract не начал незаметно расходиться с routed docs.

## Impact
- Affected specs:
  - `agent-repository-guidance`
  - `agent-onboarding-acceleration`
  - `agent-project-memory-governance` (new)
- Affected guidance/docs:
  - `AGENTS.md`
  - `docs/agent/INDEX.md`
  - `docs/agent/TASK_ROUTING.md`
  - `docs/agent/VERIFY.md`
  - `docs/agent/PLANS.md`
  - `docs/agent/code_review.md`
  - new `docs/agent/MEMORY.md` or equivalent stable path
- Affected tooling:
  - `scripts/dev/check-agent-doc-freshness.sh`
  - `scripts/dev/check-agent-doc-freshness.py`
- Non-goals:
  - не менять OpenSpec -> Beads delivery process;
  - не переписывать все scoped `AGENTS.md` без явной необходимости;
  - не заменять Markdown router отдельной DSL или новой внешней системой;
  - не менять product/runtime behavior вне agent-facing docs and validation.

