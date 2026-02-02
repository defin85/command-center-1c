# Дизайн: refactor-extensions-snapshot-trigger-operation-metadata

## Цели
- Детерминированно обновлять `DatabaseExtensionsSnapshot` и сохранять `CommandResultSnapshot` для “snapshot-producing” команд.
- Убрать зависимость от `ui.action_catalog` на стадии `worker completed` (completion path).
- Убрать зависимость от `action.id` как носителя семантики.

## Наблюдения (текущее поведение)
- `extensions_plan_apply` и UI ожидают зарезервированные `action.id`: `extensions.list` / `extensions.sync`.
- completion path (event-subscriber) вычисляет “нужно ли писать snapshot” через чтение action catalog и фильтрацию по `action.id`, что ломается при tenant overrides / произвольных id.

## Предлагаемое решение

### 1) Маркер snapshot-поведения в `BatchOperation.metadata`
Добавить в `BatchOperation.metadata` поле (минимальный формат):

```json
{
  "snapshot_kinds": ["extensions"]
}
```

Гарантии:
- Маркер выставляется **при создании операции** (enqueue path), когда у нас есть tenant context и resolved executor.
- completion path не читает runtime settings для решения “писать/не писать snapshot”.
- Маркер не содержит секретов (только enum’ы).

Почему `snapshot_kinds`, а не “один флаг”:
- это расширяемо: позже можно добавить, например, `clusters_inventory`, `dbms_inventory` и т.п.

### 2) Где выставлять маркер
Маркер выставляется в месте, где создаётся `BatchOperation` для `ibcmd_cli`.

Правило для MVP (extensions):
- Если команда `command_id` соответствует executor’у action с `capability in {"extensions.list","extensions.sync"}` в effective `ui.action_catalog` текущего tenant’а,
  то `metadata.snapshot_kinds` включает `"extensions"`.

Пояснение:
- UI при запуске действия расширений передаёт только `command_id` (без action id).
- Поэтому на enqueue мы определяем “это extensions snapshot-producing” по конфигурации tenant’а (effective catalog) и `command_id`.
- Даже если `ui.action_catalog` изменится после enqueue, completion уже использует маркер и корректно обновит snapshot.

### 3) `capability` в action catalog (extensions)
Добавить в `extensions.actions[]` необязательное поле:
- `capability: "extensions.list" | "extensions.sync"`

Семантика:
- `id` — идентификатор/ключ UI и редактора (произвольный).
- `capability` — зарезервированная семантика, которую использует backend (plan/apply и snapshot-marking).

Совместимость:
- Если `capability` отсутствует, backend временно поддерживает legacy-режим: действия с `id == "extensions.list"`/`"extensions.sync"` считаются соответствующими capability.

## Альтернативы (не выбранные)
- “Всегда snapshot при `command_id in {"infobase.extension.list","infobase.extension.sync"}`”: проще, но жёстко хардкодит semantics по командным id и не позволяет tenant’у менять команду/алиасы без кода.
- “Передавать action_id в execute-ibcmd-cli”: даёт контекст, но всё равно требует server-side проверки и расширяет контракт API.

## Открытые вопросы
- Нужен ли отдельный маркер для append-only `CommandResultSnapshot` vs `DatabaseExtensionsSnapshot` (или это всегда вместе для `extensions`)?
- Нужно ли включать в metadata источник (например, `snapshot_source="ui.action_catalog"`), чтобы проще дебажить?

