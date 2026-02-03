# Дизайн: refactor-extensions-snapshot-trigger-operation-metadata

## Цели
- Детерминированно обновлять `DatabaseExtensionsSnapshot` и сохранять `CommandResultSnapshot` для “snapshot-producing” команд.
- Убрать зависимость от `ui.action_catalog` на стадии `worker completed` (completion path).
- Убрать зависимость от `action.id` как носителя семантики.

## Наблюдения (текущее поведение)
- `extensions_plan_apply` и UI ожидают зарезервированные `action.id`: `extensions.list` / `extensions.sync`.
- completion path (event-subscriber) вычисляет “нужно ли писать snapshot” через чтение action catalog и фильтрацию по `action.id`, что ломается при tenant overrides / произвольных id.

## Предлагаемое решение

### 0) Capability как контракт (а не `command_id`)
Мы неизбежно “хардкодим” часть семантики в backend, но корректная точка для этого хардкода — **`capability`**, а не конкретный `command_id` конкретного драйвера.

Это позволяет:
- tenant’у заменить драйвер и/или `executor.command_id`, сохранив семантику `extensions.list|extensions.sync`;
- в будущем добавлять новые типы действий (новые capability и новые snapshot kinds), не завязываясь на UI `id`.

### 0.1) Уже существующая “автогенерация списка расширений”
Список расширений в UI уже “автогенерируется” из результата драйвера через backend:
- worker result → best-effort парсинг stdout/структуры → `normalized_snapshot.extensions[]`;
- далее (опционально) применяется deterministic mapping в `extensions_inventory` (на сегодня близок к identity);
- UI читает эти данные через snapshot/overview endpoints.

Этот change не меняет формат snapshot’ов, а делает их обновление детерминированным (чтобы UI стабильно видел актуальные данные).

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
- Backend имеет список **зарезервированных capability**, которые он понимает: `{"extensions.list","extensions.sync"}`.
- На enqueue мы вычисляем, что операция является snapshot-producing для extensions, если:
  - операция `ibcmd_cli` и имеет `command_id`;
  - и `command_id` совпадает с `executor.command_id` какого-либо action в effective `ui.action_catalog` текущего tenant’а,
  - где `action.capability in {"extensions.list","extensions.sync"}` и `executor.kind == "ibcmd_cli"`.

Если правило выполнено, то:
- `metadata.snapshot_kinds` включает `"extensions"`.

Рекомендуемые (debug-only) поля в metadata:
- `metadata.action_capability` — если удалось однозначно определить capability (например `extensions.list`).
- `metadata.snapshot_source = "ui.action_catalog"` — чтобы было проще дебажить происхождение маркера.

Пояснение:
- UI при запуске действия расширений передаёт только `command_id` (без action id).
- Поэтому на enqueue мы определяем “это extensions snapshot-producing” по конфигурации tenant’а (effective catalog) и `command_id`.
- Даже если `ui.action_catalog` изменится после enqueue, completion уже использует маркер и корректно обновит snapshot.

### 3) `capability` в action catalog (универсальный формат)
Добавить в `extensions.actions[]` необязательное поле:
- `capability: string`

Формат строки (универсальный, namespaced):
- `"<namespace>.<name>"`
- где `namespace` и `name`:
  - ASCII
  - lowercase
  - разделители: `.` между сегментами; внутри сегмента допустимы `a-z0-9_-`
  - рекомендуется 2-3 сегмента для читаемости (например `extensions.list`, `extensions.sync`, `db.health.check`)

Важно:
- система не пытается “понимать” capability как схему флагов; это именно маркер семантики для backend (plan/apply, snapshot-marking, guardrails).

Семантика:
- `id` — идентификатор/ключ UI и редактора (произвольный).
- `capability` — зарезервированная семантика, которую использует backend (plan/apply и snapshot-marking).

Примечание о терминах:
- `capability` в этом change — “action semantics marker”.
- Это НЕ про RBAC capability permissions (права доступа). Поле хранится внутри `ui.action_catalog.extensions.actions[]`.

### 4) Правила валидности для зарезервированных capability
Чтобы mapping был детерминированным и безопасным:
- Для effective action catalog ДОЛЖНО быть не более одного action на каждую capability из реестра backend (например `extensions.list`, `extensions.sync`).
- Если в payload присутствуют дубликаты (две записи с одинаковой `capability` из реестра) — обновление `ui.action_catalog` ДОЛЖНО быть отвергнуто (fail-closed).
- Для legacy-схемы допускаем временный fallback (пока `capability` отсутствует): `id=="extensions.list|extensions.sync"` эквивалентны соответствующим capability.

Unknown `capability` (не из реестра) допустимы, но:
- backend не обязан придавать им смысл и не должен включать для них особые side effects без явной поддержки.

### 5) UI редактор action catalog (guided)
В проекте уже есть опыт “подсказок из backend-каталогов” (например выбор `command_id` по driver catalog). Для `action.capability` применяем тот же подход:
- guided editor должен показывать поле `capability` (опциональное);
- UI должен уметь предложить curated список поддерживаемых capability (MVP: `extensions.list`, `extensions.sync`), но позволять ручной ввод;
- ошибки update-time validation (например “duplicate capability”) должны подсвечиваться на уровне action (как и прочие ошибки сохранения).

Совместимость:
- Если `capability` отсутствует, backend временно поддерживает legacy-режим: действия с `id == "extensions.list"`/`"extensions.sync"` считаются соответствующими capability.

## Альтернативы (не выбранные)
- “Всегда snapshot при `command_id in {"infobase.extension.list","infobase.extension.sync"}`”: проще, но жёстко хардкодит semantics по командным id и не позволяет tenant’у менять команду/алиасы без кода.
- “Передавать action_id в execute-ibcmd-cli”: даёт контекст, но всё равно требует server-side проверки и расширяет контракт API.

## Открытые вопросы
- Нужен ли отдельный маркер для append-only `CommandResultSnapshot` vs `DatabaseExtensionsSnapshot` (или это всегда вместе для `extensions`)?
- Нужно ли включать в metadata источник (например, `snapshot_source="ui.action_catalog"`), чтобы проще дебажить?
