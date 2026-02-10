# Manual Operations (templates-only) — инструкция для операторов

Этот гайд описывает актуальную модель запуска ручных операций после decommission Action Catalog.

## Ключевая модель

- Источник исполнения: только `template` exposure.
- Запуск ручной операции:
  - выбрать `manual_operation` (`extensions.sync` или `extensions.set_flags`);
  - выбрать `template_id` явно, либо использовать tenant preferred binding.
- Если binding отсутствует/устарел, API возвращает fail-closed ошибку `MISSING_TEMPLATE_BINDING`.

## Preferred Template Bindings

API:
- `GET /api/v2/extensions/manual-operation-bindings/`
- `PUT /api/v2/extensions/manual-operation-bindings/{manual_operation}/`
- `DELETE /api/v2/extensions/manual-operation-bindings/{manual_operation}/`

Правила:
- binding хранит alias шаблона (`template_id`);
- rename/delete alias не обновляет binding автоматически;
- stale binding после rename/delete приводит к `MISSING_TEMPLATE_BINDING`.

## Планирование и запуск

### Планирование
`POST /api/v2/extensions/plan/`

Обязательные поля:
- `database_ids`
- `manual_operation`

Дополнительно:
- `template_id` (override preferred binding)
- для `extensions.set_flags`:
  - `extension_name`
  - `flags_values`
  - `apply_mask`

### Применение
`POST /api/v2/extensions/apply/`

Обязательное поле:
- `plan_id`

Важно:
- legacy планы action-catalog формата отклоняются с `PLAN_INVALID_LEGACY`;
- apply использует metadata из плана (`result_contract`, `mapping_spec_ref`) как pinned-contract.

## Деактивация legacy Action Catalog

- `GET /api/v2/ui/action-catalog/` возвращает `404` (`error.code=NOT_FOUND`).
- Route `/templates?surface=action_catalog` не используется в рабочем сценарии.
- Все новые настройки и тесты должны опираться на templates-only contracts.
