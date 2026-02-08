## Context
В проекте уже есть unified persistence (`operation_definition` + `operation_exposure`) и единый route `/templates`.
Но UI и контракт редактирования ещё неоднородны:
- для templates используется отдельный modal-UX на `DriverCommandBuilder`;
- для actions используется action-style editor с tab-структурой;
- в формах присутствуют и `executor.kind`, и `driver`, что дублирует семантику для текущих executor kinds.

В результате оператору приходится держать в голове две похожие, но разные модели настройки, а команда поддерживает две ветки editor-логики.

## Goals / Non-Goals
- Goals:
  - Единый operator editor UX для surfaces `template` и `action_catalog` в `/templates`.
  - Единый frontend pipeline сериализации/валидации execution payload.
  - Устранение пользовательского дублирования `executor.kind`/`driver` для canonical kinds.
  - Нормализация/миграция существующих unified records в canonical executor shape.
- Non-Goals:
  - Редизайн consumer UX в `/databases` (выполнение actions/runtime view).
  - Полная переделка Operations Wizard (там `DriverCommandBuilder` может оставаться отдельным до отдельного change).
  - Изменение бизнес-семантики capability (`extensions.set_flags`, `extensions.list`, `extensions.sync`).

## Decisions
- Decision 1: Единый modal editor shell для двух surfaces
  - В `/templates` и `Templates`, и `Action Catalog` используют единый tabbed shell: `Basics`, `Executor`, `Params`, `Safety & Fixed`, `Preview`.
  - Surface-specific поля остаются, но размещаются внутри единого каркаса и единой state-модели.

- Decision 2: Canonical mapping `executor.kind -> runtime driver`
  - Для `ibcmd_cli` driver всегда `ibcmd`.
  - Для `designer_cli` driver всегда `cli`.
  - Для `workflow` driver отсутствует.
  - UI не запрашивает у оператора отдельный `driver` для этих kinds.

- Decision 3: Backend normalization и fail-closed валидация mismatch
  - На write-path backend нормализует payload к canonical виду и не создаёт разные fingerprints из-за избыточного `driver`.
  - Конфликтные состояния (`kind=ibcmd_cli`, `driver=cli` и т.п.) получают fail-closed валидацию.
  - Для уже существующих legacy записей добавляется миграция/скрипт нормализации + diagnostics.

- Decision 4: Пошаговая доставка без временных fallback UI
  - Сначала внедряется shared editor на `/templates`.
  - Затем удаляется шаблонная ветка modal на `DriverCommandBuilder` в templates surface.
  - После этого закрепляется canonical executor contract в тестах/документации.

## Data & API Considerations
- Unified persistent модель остаётся (`operation_definition`/`operation_exposure`), но canonical shape execution payload уточняется.
- Если wire-контракт API меняется (например, `driver` больше не ожидается от UI для canonical kinds), обновляются OpenAPI/typed clients.
- Dedup definition fingerprint должен быть стабильным относительно устранения redundant `driver`.

## Migration Plan
1. Обновить OpenSpec-дельты и зафиксировать breaking notes.
2. Внедрить shared editor shell для `template` и `action_catalog` в `/templates`.
3. Добавить backend normalization + validation для canonical mapping kind/driver.
4. Выполнить data migration/normalization существующих unified records.
5. Обновить тесты (frontend e2e + backend contract/validation + migration cases).
6. Обновить docs операторов и release notes.

## Risks / Trade-offs
- Риск: конфликтные legacy payloads с нестандартным `driver`.
  - Митигация: fail-closed + migration issues + явный отчёт по конфликтам.
- Риск: регрессии в template editing при переходе на новый shell.
  - Митигация: e2e-сценарии create/edit/delete template + parity snapshot тесты сериализации.
- Риск: частичная унификация только на `/templates`, но не в Operations Wizard.
  - Митигация: явно оставить это как отдельный follow-up change.

## Open Questions
- Нужна ли жёсткая серверная очистка поля `driver` в persisted payload для canonical kinds, или допускаем хранение как вычислимого/игнорируемого legacy поля на переходный период? (по умолчанию в этом change предполагается жёсткая нормализация)
