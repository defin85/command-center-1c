## TEMPLATE_DRIFT Runbook

Цель: быстро локализовать и устранить fail-closed ошибки `TEMPLATE_DRIFT` при выполнении workflow/template операций после перехода на `OperationExposure + OperationDefinition`.

### Когда применять

- В timeline/логе операции есть `TEMPLATE_DRIFT`.
- Internal template resolve (`/api/v2/internal/get-template`, `/api/v2/internal/render-template`) возвращает `400` с `TEMPLATE_DRIFT`.
- Workflow operation node с `binding_mode=pinned_exposure` не enqueue'ит операцию из-за mismatch revision.

### Что означает ошибка

`TEMPLATE_DRIFT` означает, что ожидаемая pinned-версия template (`template_exposure_revision`) не совпала с текущей revision exposure/definition в runtime.

### Быстрая проверка (5 минут)

1. Найти проблемную операцию и её metadata (`template_id`, `template_exposure_id`, `template_exposure_revision`) в details API.
2. Проверить internal resolve тем же reference:

```bash
curl -sS -H "X-Internal-Token: $INTERNAL_API_TOKEN" \
  "http://localhost:8200/api/v2/internal/get-template?template_exposure_id=<EXPOSURE_ID>&template_exposure_revision=<REVISION>"
```

3. Если вернулся `TEMPLATE_DRIFT`, получить текущее состояние exposure:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8200/api/v2/operation-catalog/exposures/?surface=template&alias=<TEMPLATE_ALIAS>&limit=1&offset=0"
```

Сравнить:
- metadata `template_exposure_id` vs актуальный exposure id,
- metadata `template_exposure_revision` vs актуальный `template_exposure_revision`.

### Типовые причины

- Шаблон (definition payload / contract version) был изменён после сохранения workflow или после enqueue операции.
- Workflow использует `pinned_exposure`, но ссылка устарела (старый revision).
- Ручная правка/миграция оставила несогласованные значения в metadata.

### Восстановление

1. Для новых запусков:
- открыть workflow/template в UI,
- пересохранить с актуальным `operation_ref` (обновится pinned reference/revision),
- повторить запуск.

2. Для уже заqueued операций:
- отменить проблемные операции,
- перезапустить из актуального workflow/template.

3. Если требуется временная совместимость:
- проверить runtime setting `workflows.operation_binding.enforce_pinned`.
- при необходимости временно ослабить политику (только по change window и с подтверждением владельца сервиса).

### Проверка после фикса

- Повторный запуск проходит без `TEMPLATE_DRIFT`.
- Internal `get-template` с pinned reference возвращает `200`.
- В `/templates` list видны ожидаемые provenance-поля: alias, `executor_kind`, `executor_command_id`, `template_exposure_id`, `template_exposure_revision`, status.

### Эскалация

Эскалировать к backend owner, если:
- `template_exposure_revision` не монотонен,
- drift возникает массово для неизменённых template,
- есть расхождение между `/operation-catalog/exposures` и internal `get-template` при одинаковом reference.
