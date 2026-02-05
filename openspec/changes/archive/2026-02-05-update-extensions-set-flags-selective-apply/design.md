# Design: Selective apply для extensions.set_flags

## Контекст
Существующая реализация `extensions.set_flags` работает как “apply policy целиком”:
- policy хранится tenant-scoped (`extensions-flags-policy`);
- plan/apply резолвит `$policy.*` и запускает configured action из `ui.action_catalog`.

Новая потребность: одна кнопка Apply, но возможность выбрать **какие флаги применять** и **какие значения** задать в этом же flow.

## Ключевое решение: apply_mask + param-based executor
Selective apply должен гарантировать, что невыбранные флаги **не будут изменены**. Самый надёжный способ — исключить их из executor params, а не пытаться “пропустить” значения в `additional_args`.

### Почему не additional_args
`additional_args` — это линейный список токенов, и “снять пару” (`--flag VALUE`) без формального синтаксиса приводит к эвристикам (опасно и недетерминированно).

### Стандартизация executor для reserved capability
Для capability `extensions.set_flags` вводим требование:
- executor ДОЛЖЕН (SHALL) задавать значения флагов через `executor.params` (object), а не через `additional_args`.
- `executor.params` должен содержать ключи:
  - `extension_name`
  - `active`
  - `safe_mode`
  - `unsafe_action_protection`
  (конкретная привязка параметров к CLI флагам остаётся обязанностью driver catalog/schema).

Backend при plan/apply:
- вычисляет `apply_mask` (по умолчанию: все true),
- удаляет из `executor.params` те ключи флагов, где mask=false,
- валидирует, что для mask=true соответствующие ключи присутствуют (fail-closed).

Если action catalog сконфигурирован иначе (например, флаги в additional_args), selective apply **fail-closed** с ошибкой конфигурации (оператору нужно поправить `ui.action_catalog`).

## UI flow (single Apply button)
В drawer расширения:
- отображается форма на 3 флага:
  - checkbox “Apply”
  - switch “Value”
- switch disabled, если checkbox выключен (чтобы не было “псевдо-значений”).
- дефолты:
  - checkbox включён только если текущий policy для флага задан (не null); иначе выключен.
  - switch инициализируется текущим policy значением (true/false); если policy null — дефолт false, но switch disabled до включения checkbox.

При Apply:
1) UI upsert'ит policy для выбранных флагов (и только для них), используя `PUT/PATCH /api/v2/extensions/flags-policy/{extension_name}/`.
   - Для невыбранных флагов policy не меняется.
2) UI вызывает `POST /api/v2/extensions/plan/` с `capability="extensions.set_flags"`, `extension_name`, `database_ids` и `apply_mask`.
3) UI вызывает `POST /api/v2/extensions/apply/`.

## Безопасность и RBAC
Сохраняем текущие guardrails:
- mutating операции (policy upsert, plan/apply set_flags) требуют `manage_database`;
- staff mutating требуют явный `X-CC1C-Tenant-ID` (fail-closed).

## Обновление snapshot после set_flags
Сохраняем B1: apply для set_flags должен fail-closed, если `extensions.sync` не настроен, и должен гарантировать follow-up refresh (post-completion sync).

