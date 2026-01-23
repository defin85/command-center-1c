# Change: Добавить Execution Plan + Binding Provenance (без хранения секретов)

## Why
Сейчас пользователь (и даже staff) не видит прозрачного ответа на вопросы:
- **Что именно будет выполнено** (какая команда/argv или какой workflow + какой input)?
- **Откуда берутся значения** (UI, action catalog, driver schema, Database connection, RuntimeSetting, env/secret store)?
- **Что система подставляет автоматически и почему** (нормализация argv, allowlist-инъекции, runtime-only значения)?

Из-за этого:
- отладка ошибок исполнения затруднена (пример: невалидные флаги `--user/--password` для конкретной команды);
- поведение выглядит “магическим” и не воспроизводится при ручном повторе;
- сложно безопасно логировать и объяснять итоговое выполнение, не раскрывая секретов.

## What Changes
- Вводим явные сущности **Execution Plan** и **Binding Provenance**:
  - Execution Plan описывает “что будет выполнено” в безопасном виде (например `argv_masked[]`).
  - Binding Provenance описывает “откуда что берётся и где подставляется” без хранения секретов.
- Расширяем UI для staff:
  - `/operations` (details): показывает plan + provenance для операций и workflow executions.
  - `/databases` (drawer запуска): staff видит preview plan + provenance до запуска.
  - `/settings/action-catalog` (editor): staff видит preview plan + provenance для выбранного action.
- По умолчанию plan/provenance видимы **только staff**, с заделом на расширение через RBAC (отдельное разрешение/роль).
- Система логирует plan/provenance безопасно: без raw значений секретов, только masked и метаданные источников/статусов.

## Impact
- Спеки:
  - **Новая capability:** `execution-plan-binding-provenance`
  - **Модификации:** `command-schemas-driver-options`, `ui-action-catalog-editor`, `extensions-action-catalog`
- Код (будет затронуто на этапе реализации):
  - Orchestrator: сборка/хранение plan+bindings, API/serializers, audit/logging, preview endpoints
  - Worker: репорт runtime-only биндингов (applied/skipped + reason), безопасная доставка в результат/таймлайн
  - Frontend: отображение plan+provenance в 3 точках, роль-based гейтинг
  - Contracts/OpenAPI: добавление полей/эндпоинтов (additive)
