## Context

Проект уже прошёл foundational фазу agent-facing onboarding, но текущая система guidance теперь страдает от следующего слоя проблем:
- root `AGENTS.md` аккумулировал слишком много ролей и стал дорогим по вниманию;
- authoritative guidance корректна по содержанию, но не всегда экономна по маршруту чтения;
- один универсальный completion contract смешивает разные типы задач и делает fail-closed политику тяжелее, чем нужно;
- manual Hindsight memory описана как runbook, а не как строгая policy surface, поэтому банк уязвим к повторному засорению;
- при конфликте между instructions у агента есть общие precedence rules, но repo-local conflict resolution описан слишком распределённо.

Новый change не заменяет existing agent specs, а делает следующий governance pass: снижает стоимость входа и координации без удаления уже полезных checked-in surfaces.

## Goals / Non-Goals

- Goals:
  - Сократить контекстную стоимость root guidance.
  - Явно разделить repo-wide invariants и routed/deeper workflow docs.
  - Сделать routing минимально достаточным, а не универсально широким.
  - Развести completion expectations по классам задач.
  - Формализовать project memory как high-signal-only policy.
- Non-Goals:
  - Создавать новый workflow engine или внешний rule registry.
  - Менять OpenSpec/Beads approval gates.
  - Замещать существующие scoped `AGENTS.md` дублирующим repo-wide guidance.
  - Автоматически сохранять память без явного retain workflow.

## Decisions

### 1. Root `AGENTS.md` остаётся первой repository-level instruction surface, но только для repo-wide invariants

Root `AGENTS.md` по-прежнему нужен, потому что он является ближайшей checked-in repository instruction surface. Но его scope должен быть ограничен:
- precedence and source-of-truth rules;
- repo layout и core constraints;
- compact completion model;
- ссылки на routed docs и required inline contracts.

Он не должен снова становиться обязательным длинным onboarding bundle.

### 2. Routing должен быть minimum-sufficient, а не “прочитай всё на всякий случай”

Существующий task router уже полезен, но repo-local guidance всё ещё навязывает широкое чтение стартового набора. Это создаёт лишнюю стоимость даже там, где задача локальна и хорошо определена.

Принятое правило:
- каждый task family получает minimum-required read set;
- дополнительные docs и skills подключаются условно, а не по умолчанию;
- router явно говорит, когда можно остановить чтение и идти в код/валидацию.

### 3. Completion contract должен быть классом задачи, а не одной глобальной формулой

Фиксировать один `done` для всех задач полезно как safety net, но это смешивает analysis, review, docs-only updates и merge-ready delivery.

Принятое разделение:
- `analysis/review`: findings, assumptions, evidence, без commit/push expectations;
- `local change`: локальная валидация и изменение checked-in guidance/code без обязательного release-grade handoff;
- `delivery`: полный repo contract, включая verification, Beads/OpenSpec status alignment и git delivery expectations.

Такой профиль делает правила одновременно строже и дешевле.

### 4. Repo-local conflict resolution должен быть отдельным компактным артефактом, а не выводом “по памяти”

Общие precedence rules уже существуют, но агенту нужен именно repo-local operational matrix:
- root `AGENTS.md`;
- `docs/agent/*`;
- scoped `AGENTS.md`;
- `openspec/project.md` / `openspec/AGENTS.md`;
- checked-in repo skills;
- shared user-level skills.

Это должно быть выражено коротко и явно, чтобы конфликт не требовал повторного анализа длинных текстов.

### 5. Project memory должна описываться как policy с note taxonomy

Hindsight полезен только пока хранит устойчивые технические факты. Без checked-in schema банк быстро наполняется:
- session status;
- user-request paraphrases;
- промежуточными шагами плана;
- повторами того, что уже есть в repo docs.

Принятое правило:
- recall обязателен перед нетривиальной работой;
- retain делается только после verified discovery или verified fix;
- default note types ограничены `repo-fact`, `gotcha`, `verified-fix`, `active-change-note`;
- session-noise запрещён как normal-case retain content.

### 6. Отдельный machine-readable router откладывается

Можно было бы сразу вводить YAML/JSON routing manifest, но это добавит ещё один source of truth и новый слой поддержки.

Для этого change выбирается более дешёвый путь:
- оставить router в checked-in Markdown;
- привести его к компактной и проверяемой структуре;
- при необходимости позже добавить machine-readable overlay отдельным change.

## Risks / Trade-offs

- Более короткий root `AGENTS.md` может скрыть часть полезного контекста от агента, который не пойдёт по routed docs.
  - Mitigation: сохранить только repo-wide invariants и inline contracts, а не произвольно сокращать важные rules.
- Task-class completion profiles могут быть интерпретированы слишком свободно.
  - Mitigation: зафиксировать минимальный обязательный output/verification per class и привязать это к `VERIFY.md`.
- Memory policy без дисциплины retain всё равно может деградировать.
  - Mitigation: описать не только note types, но и явные negative examples для session-noise.
- Freshness automation может начать проверять слишком много структурных деталей и стать хрупкой.
  - Mitigation: валидировать только stable paths, ключевые section anchors и source-of-truth references.

## Migration Plan

1. Переписать root guidance contract и зафиксировать precedence matrix.
2. Уточнить task router и completion profiles.
3. Добавить stable memory policy surface и встроить её в authoritative guidance.
4. Обновить freshness checks под новую структуру.
5. Провести guidance validation и strict OpenSpec validation.

## Open Questions

- Должен ли `delivery` profile оставаться единственным классом, который требует `git pull --rebase`, commit и push, или часть этих шагов нужна и для `local change`.
- Нужен ли отдельный stable path вроде `docs/agent/MEMORY.md`, или memory policy лучше держать как короткий раздел в `docs/agent/INDEX.md` + root `AGENTS.md`.
- Стоит ли в этом же change ужесточать repo-local instructions про “open these docs for the first 10 minutes”, или достаточно переписать router и root contract.

