## Context
В текущей реализации у домена extensions есть архитектурное расслоение:
- `templates` используются для workflow/части execution-контуров,
- `action_catalog` используется как runtime-контур ручных запусков в отдельных UI.

Это создаёт конфликт runtime source of truth и сложности в поддержке API/UX.

## Goals
- Сделать `templates` единым runtime source of truth атомарных операций в домене extensions.
- Полностью убрать runtime execution path для `extensions.*` через `action_catalog`.
- Перевести `/extensions` и `/databases` на единый template-based execution path.
- Сохранить fail-closed validation и прозрачный preview/provenance.
- Зафиксировать одномоментный запуск новой модели: без compatibility adapters, fallback path и этапного rollout.

## Non-Goals
- Удалять action catalog для всех доменов в рамках этого change.
- Переписывать workflow engine.
- Проектировать универсальный framework manual contracts для всех capability.

## Decision
### 1. Source of Truth Matrix
- Атомарные операции extensions ДОЛЖНЫ резолвиться из `operation_exposure(surface=template)`.
- Workflow nodes используют `template_id`.
- Direct execution path в UI использует `template_id` + runtime input.
- `action_catalog` НЕ используется как runtime source для `extensions.*` в `/extensions` и `/databases`.

### 2. Template-Based Plan/Apply Contract
Для запуска `extensions.set_flags` `POST /api/v2/extensions/plan/` принимает:
- `capability=extensions.set_flags`,
- `template_id`,
- `flags_values`,
- `apply_mask`,
- `extension_name`.

Backend:
- валидирует published template,
- fail-closed при несовместимости template и capability,
- строит effective params только из runtime input.

### 3. UI Model
- `/extensions`:
  - запуск extensions-операций через template-based path,
  - preview перед запуском и confirm,
  - отображение результата в контексте текущего экрана.
- `/databases`:
  - не запускает `extensions.*` через `action_catalog`,
  - использует тот же template-based execution path.

### 4. Cutover Strategy (Single Step)
1. В одном релизе включается templates-only runtime path для `extensions.*`.
2. Старый `action_catalog` runtime path отключается сразу, без transition режима.
3. Запросы по legacy `action_id`-контракту отклоняются fail-closed.
4. `/extensions` и `/databases` используют template-based path как единственный runtime-вариант.
5. Документация и UI копирайт сразу отражают новую модель как единственную.

## Risks / Trade-offs
- Риск несовместимых существующих template payload shape.
- Риск регрессии на экранах, где ранее использовался `ui/action-catalog` для `extensions.*`.

## Mitigations
- Жёсткая backend-валидация template/capability compatibility + понятные ошибки.
- Переиспользование общего preview/provenance компонента и e2e regression тестов.

## Open Questions
- Отсутствуют.
