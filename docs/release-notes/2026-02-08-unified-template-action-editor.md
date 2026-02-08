# Release Notes — 2026-02-08

## refactor-unify-templates-action-editor-and-executor-model

### Что изменилось
- `/templates` и `/templates?surface=action_catalog` теперь используют единый tabbed editor shell:
  - `Basics`
  - `Executor`
  - `Params`
  - `Safety & Fixed`
  - `Preview`
- Для `Templates` удалена отдельная modal-ветка на `DriverCommandBuilder`.
- Для `Action Catalog` удалён ручной selector `driver` в editor.

### Contract / backend
- На write-path добавлена canonicalization `executor.kind`/`driver`:
  - `ibcmd_cli -> ibcmd`
  - `designer_cli -> cli`
  - `workflow -> driver not applicable`
- Добавлена fail-closed валидация конфликтных `kind/driver`.
- Fingerprint definition стабилизирован относительно redundant `driver` для canonical kinds.
- Добавлена миграция `0014_canonicalize_definition_executor_driver`:
  - нормализует совместимые записи;
  - для конфликтов создаёт diagnostics в `operation_migration_issues`.

### Breaking change
- Клиенты, которые ранее вручную отправляли `driver` как независимое поле, теперь должны учитывать canonical mapping и fail-closed поведение при mismatch.

