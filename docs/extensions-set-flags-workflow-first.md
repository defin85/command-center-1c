# extensions.set_flags: workflow-first migration guide

Документ описывает переход на модель, где источник значений флагов для `extensions.set_flags` задаётся только во время запуска (`flags_values` + `apply_mask`), а не в Action Catalog preset.

## Что изменилось (breaking)

- `POST /api/v2/extensions/plan/` для `capability=extensions.set_flags` теперь требует:
  - `action_id`
  - `extension_name`
  - `flags_values`
  - `apply_mask`
- Preset `apply_mask` в action/exposure запрещён:
  - `definition.executor_payload.fixed.apply_mask`
  - `capability_config.apply_mask`
  - `capability_config.fixed.apply_mask`
- Для `extensions.set_flags` в action editor показываются только transport/binding/safety поля.

## UI-путь для оператора

Основной путь:
- `/extensions` → открыть расширение → выбрать action `extensions.set_flags`.
- Указать runtime значения (`Active`, `Safe mode`, `Unsafe action protection`) и mask.
- Запустить rollout. Прогресс отслеживать в `/operations`.

Fallback путь:
- в том же `/extensions` выбрать конкретную базу (drawer filter `Database`) и запустить точечно.
- Использовать только для аварийных/индивидуальных кейсов.

## Требования к action `extensions.set_flags`

- Executor должен быть params-based (`executor.params`).
- В выбранных флагах должны использоваться только runtime-токены:
  - `active -> $flags.active`
  - `safe_mode -> $flags.safe_mode`
  - `unsafe_action_protection -> $flags.unsafe_action_protection`
- `target_binding.extension_name_param` обязателен и должен указывать на существующий param команды.

## Миграционный отчёт (до включения/проверки rollout)

Проверить опубликованные exposures:

```bash
cd orchestrator
python manage.py report_set_flags_apply_mask_presets
```

Проверить все статусы и получить JSON:

```bash
cd orchestrator
python manage.py report_set_flags_apply_mask_presets --all-statuses --json
```

Записать findings в `operation_migration_issues`:

```bash
cd orchestrator
python manage.py report_set_flags_apply_mask_presets --all-statuses --write-issues
```

Провалить CI/job, если есть findings:

```bash
cd orchestrator
python manage.py report_set_flags_apply_mask_presets --all-statuses --fail-on-findings
```

## Как исправлять finding

1. Открыть templates-only editor в `/templates` и выбрать template, привязанный к `extensions.set_flags`.
2. Удалить любой preset `apply_mask` из `fixed`/capability-config (если остался в legacy данных).
3. Проверить `target_binding.extension_name_param`.
4. Проверить `executor.params` и `$flags.*` mapping.
5. Сохранить и опубликовать template exposure.

После исправления повторно запустить report-команду и убедиться, что findings = 0.
