## Context

В репозитории уже есть полезные артефакты для агентной работы, но они распределены неравномерно:
- `openspec/project.md` хорошо объясняет, что это за система и из каких технологий она состоит;
- `DEBUG.md`, `debug/runtime-inventory.sh`, `scripts/dev/*` и `frontend/package.json` дают рабочие run/test/verify маршруты;
- корневой `AGENTS.md` содержит важные policy rules, но одновременно выполняет роль onboarding, workflow policy, search playbook и локального debug checklist;
- рядом продолжают жить более старые onboarding layers (`docs/START_HERE.md`, `docs/INDEX.md`, `.claude/*`, `docs/DEBUG_WITH_AI.md`, части `README.md` и `Makefile`), которые могут расходиться с реальным runtime contract.

Проблема не в отсутствии документации, а в отсутствии явного контракта:
- что новый агент должен читать первым;
- какие документы authoritative;
- какие команды считаются canonical для запуска/проверки;
- где должны жить длинные workflow rules, чтобы не перегружать корневой `AGENTS.md`;
- как автоматически ловить drift, когда runtime/scripts уже изменились, а agent-facing docs ещё нет.

## Goals / Non-Goals

- Goals:
  - Сократить время первого входа нового агента в репозиторий.
  - Сделать source-of-truth для agent-facing guidance явным и проверяемым.
  - Разделить short repo map, local subsystem guidance и long-running workflow assets.
  - Сделать machine-readable repo tooling discoverable через docs, а не только через “знание по памяти”.
  - Ввести freshness checks, которые ловят doc drift по действительно важным полям.
- Non-goals:
  - Мигрировать весь docs corpus проекта в новый формат за один change.
  - Перепридумывать OpenSpec/Beads workflow.
  - Менять domain behavior продукта.
  - Убирать из репозитория все historical materials без отдельного решения по archival policy.

## Decisions

### 1. Корневой `AGENTS.md` остаётся policy entry point, но перестаёт быть “всем сразу”

Корневой `AGENTS.md` должен остаться первой repository-level instruction точкой, потому что Codex автоматически подгружает именно этот слой. Но он не должен быть единственным местом для длинных процедурных описаний.

Принятое разделение:
- root `AGENTS.md` = краткая repo map + обязательные инварианты + ссылки на deeper docs;
- nested `AGENTS.md` = локальные правила подсистем;
- `docs/agent/*` = system of record для onboarding/runbook/verification/long-running workflow assets.

Это соответствует цели “короткий, практичный `AGENTS.md` плюс deeper task-specific docs”, не ломая текущий instruction chain.

### 2. Обязательные inline contracts в root `AGENTS.md` сохраняются

В репозитории уже есть existing capability `ui-frontend-governance`, который требует явный UI platform contract в `AGENTS.md`. Поэтому root file нельзя превратить в “голую ссылку на docs”.

Компромисс:
- root `AGENTS.md` держит обязательные inline contracts, которые нужны агенту без дополнительных переходов;
- procedural detail, examples, long checklists и subsystem-specific runbooks выносятся в deeper docs.

### 3. Canonical agent docs surface должен быть стабильным и отделённым от legacy docs

Новый агент не должен угадывать, authoritative ли `docs/START_HERE.md` или `.claude/README.md`.

Поэтому change вводит явный stable path `docs/agent/*` для agent docs и требует маркировать остальные onboarding-like документы как:
- authoritative;
- supplemental;
- legacy/non-authoritative.

Это дешевле и безопаснее, чем полная немедленная перепись всего исторического docs corpus.

### 4. Reference artifacts должны покрывать первые 10 минут работы агента

Новый agent-facing surface должен закрывать четыре вопроса:
- что это за проект;
- как он структурирован;
- где entry points;
- как запустить, проверить и верифицировать изменение.

Из этого следуют обязательные артефакты:
- `docs/agent/INDEX.md`;
- `docs/agent/ARCHITECTURE_MAP.md`;
- `docs/agent/RUNBOOK.md`;
- `docs/agent/VERIFY.md`.

`openspec/project.md` тоже должен быть синхронизирован с этой поверхностью, чтобы OpenSpec project context не отправлял нового агента в устаревшие onboarding layers.

### 5. Long-running work оформляется отдельными workflow assets

Для multi-step задач и review нельзя продолжать полагаться только на длинный root `AGENTS.md`.

Поэтому change вводит отдельные assets:
- `PLANS.md` или эквивалентный execution-plan template;
- `code_review.md` или эквивалентный review checklist;
- shared skills для действительно повторяемых workflows.

Skills нужны только там, где репозиторий уже доказал повторяемость процесса. Это ограничивает scope и не превращает `.agents/skills` в dump folder.

### 6. Freshness checks должны сравнивать docs не с “идеалом”, а с реальными source-of-truth inputs

Полезный doc lint для этого репозитория — не общий markdown style lint, а проверки, которые отвечают на конкретный вопрос: “authoritative agent docs всё ещё соответствуют реальному проекту?”

Минимальные inputs для такой проверки:
- `.tool-versions` для версий инструментов;
- `debug/runtime-inventory.sh --json` для runtime/entrypoint/start/test surfaces;
- `scripts/dev/*` для фактических script paths;
- `frontend/package.json` для frontend validation commands;
- checked-in file paths, на которые ссылаются authoritative docs.

### 7. Legacy agent layers не должны silently compete с canonical surface

Старые `.claude/*` и historical docs сами по себе могут быть полезны как архивный контекст, но они не должны выглядеть как равноправный современный onboarding path.

Принятое правило:
- либо явная маркировка `legacy/non-authoritative`;
- либо archival move в отдельный path, если документ больше не нужен в активном контуре.

## Risks / Trade-offs

- Больше checked-in agent docs означает больше точек сопровождения.
  - Mitigation: делать root `AGENTS.md` коротким, а deeper docs строить вокруг реально используемых workflows.
- Слишком Codex-specific wording может ухудшить полезность артефактов для других агентов.
  - Mitigation: capability формулируется как agent-facing, а Codex-специфика добавляется там, где это связано с `.codex/`, `AGENTS.md`, skills и workflow assets.
- Добавление nested `AGENTS.md` может породить дублирование с root guidance.
  - Mitigation: root отвечает за repo-wide rules, nested files только за local deltas.
- Freshness automation может стать слишком дорогой, если пытаться автоматически валидировать весь docs corpus.
  - Mitigation: checks распространяются только на authoritative agent-facing surface.

## Migration Plan

1. Объявить canonical agent-facing surface и отделить его от legacy onboarding docs.
2. Синхронизировать `openspec/project.md` с новым canonical path.
3. Перестроить root/nested guidance layering.
4. Добавить reference artifacts для architecture/run/verify.
5. Добавить workflow assets и shared skills.
6. Добавить machine-checkable freshness checks и встроить их в validation path.

## Open Questions

- Ограничиться ли явной маркировкой legacy docs на первом этапе, или часть из них лучше сразу архивировать.
- Какой минимальный initial skill set даёт наибольшую пользу без избыточного скопа: только runtime/debug + verification, или сразу включать OpenSpec/change-execution workflow.
