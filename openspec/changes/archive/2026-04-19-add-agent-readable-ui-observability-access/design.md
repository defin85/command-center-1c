## Контекст

Сейчас в проекте уже существуют:
- backend-side observability stack (`Prometheus`, `Grafana`, `Jaeger`);
- gateway trace proxy;
- frontend trace viewer для server-side execution traces;
- local debug toolkit (`eval-frontend`, Chrome CDP).

При этом отсутствует canonical agent-facing contract, который делает UI инциденты machine-readable для LLM/агента и на dev, и на prod.

Отдельный change `05-add-ui-action-journal-and-error-correlation` уже закрывает нижний слой: bounded UI journal, `request_id` / `ui_action_id`, redaction policy и debug export path. Новый change должен не дублировать этот слой, а зафиксировать, как именно агент его читает и что обязано быть доступно на production surface.

## Goals

- Дать агенту/LLM штатный способ читать UI observability signals без прямого доступа к пользовательскому браузеру.
- Унифицировать dev и prod path поверх machine-readable telemetry.
- Явно зафиксировать, что для minimal useful agent monitoring достаточно traces/errors/actions без visual replay.
- Сохранить vendor-neutral основу и совместимость с существующим Jaeger/Grafana path.

## Non-Goals

- Не требовать session replay как mandatory contract.
- Не делать новый rich operator-facing UI screen специально для LLM.
- Не открывать агенту произвольный доступ к Grafana/Jaeger/admin shell без дополнительного control layer.

## Основное решение

### 1. Machine-readable telemetry is the primary substrate

Default agent monitoring path строится поверх:
- semantic UI journal events;
- correlated identifiers (`trace_id`, `request_id`, `ui_action_id`);
- route/build/release/runtime metadata;
- backend trace lookup.

Это значит:
- visual replay НЕ нужен как обязательный контракт;
- replay МОЖЕТ (MAY) появиться позже как optional forensic layer;
- current minimum value для LLM достигается уже на machine-readable signals.

### 2. Dev и prod должны иметь разные access surfaces

#### Dev/local
- агент получает session bundle через existing debug/export toolkit;
- допустим richer forensic output;
- manual reproduce -> export JSON bundle -> agent analysis.

#### Prod
- агент получает только read-only redacted diagnostics surface;
- query path должен возвращать recent incidents, counters, summaries и correlation identifiers;
- никакого raw browser attach и никакого unbounded replay payload.

### 3. Agent-facing access должен быть нормализованным, а не прямым vendor UI

Даже если underlying backend использует Jaeger/Grafana, canonical contract для агента не должен зависеть от прямого screen scraping этих UI. Правильнее:
- internal API / structured export;
- explicit schema;
- RBAC/redaction/sampling/retention policy.

### 4. Dependency management

Новый change зависит от `05-add-ui-action-journal-and-error-correlation`, потому что без него нет stable source-of-truth для frontend journal и correlation identifiers.

`01-expand-ui-frontend-governance-coverage` и route-level UI governance остаются orthogonal prerequisites: они улучшают perimeter discipline, но не заменяют observability access.

## Alternatives

### A. Опираться только на Playwright trace
Отклонено. Хорошо для dev/CI, недостаточно для production monitoring и непрерывного агентного анализа.

### B. Сразу требовать session replay
Отклонено. Усложняет privacy, sampling и storage policy, а для minimal useful monitoring не требуется.

### C. Давать агенту прямой доступ к Jaeger/Grafana UI
Отклонено как primary design. Это плохо контролируется, хуже для schema stability и хуже для RBAC/redaction.

## Rollout

1. Завершить UI journal/correlation source capability.
2. Зафиксировать agent-readable schema и access surface.
3. Реализовать dev export path и prod query path.
4. Добавить RBAC/redaction/sampling/retention checks.
5. Обновить docs/runbook и acceptance validation.

## Риски

- Если journal/correlation change не доставлен, этот change останется без базового telemetry substrate.
- Если prod path будет слишком сырым и vendor-shaped, агентный contract станет хрупким.
- Если не зафиксировать redaction/sampling upfront, можно случайно превратить UI observability в privacy risk.
