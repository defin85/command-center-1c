# Change: refactor-extensions-snapshot-trigger-operation-metadata

## Почему
Сейчас обновление `DatabaseExtensionsSnapshot` и запись `CommandResultSnapshot` зависят от того, как именно настроен `ui.action_catalog` *в момент* прихода события `worker completed`. Это приводит к хрупкости:

- tenant может иметь `published` override, а global значение отличается;
- action id может быть произвольным (или меняется в UI), из‑за чего snapshot-триггер может “не сработать” даже при успешном выполнении `infobase.extension.list`;
- получаем “completed + есть stdout” но `DatabaseExtensionsSnapshot`/`CommandResultSnapshot` не создаются.

Нужно сделать snapshot-поведение детерминированным и не зависящим от runtime settings на стадии completion.

## Почему это важно для UI (уже реализованная автогенерация)
В проекте уже есть цепочка “ответ драйвера → нормализация → отображение”:
- worker возвращает `stdout`/структурированные данные по расширениям;
- backend нормализует ответ в стабильный список `extensions[]` (best-effort парсинг нескольких форматов);
- UI использует snapshot-эндпоинты для отображения списка расширений:
  - `/api/v2/databases/get-extensions-snapshot/` (drawer на `/databases`);
  - `/api/v2/extensions/overview/` (агрегированный экран `/extensions`).

Если snapshot-триггер не срабатывает, UI видит “успешно выполнено”, но список расширений не обновился.

## Что меняется
- Для extensions семантика “что это за действие” будет задаваться через **явное поле `capability` в action catalog** (универсальный namespaced string), а не через `action.id`.
  - `id` становится UI-ключом и может быть произвольным/переименовываемым.
  - `capability` — стабильный “контракт” (backend-understood), который определяет семантику (plan/apply, snapshot-marking, guardrails).
- При enqueue `BatchOperation` система будет ставить **маркер snapshot-поведения в `BatchOperation.metadata`** (операция становится self-contained для snapshot-триггера).
  - Маркер вычисляется в enqueue path на основании effective `ui.action_catalog` *текущего tenant’а* и `command_id`/executor binding.
  - Маркер не содержит секретов и предназначен для стабильной обработки completion.
- Event-subscriber будет принимать решение об обновлении snapshot’ов и append-only `CommandResultSnapshot` **только по маркеру в `BatchOperation.metadata`** (completion path не читает runtime settings).

## Принципиальное решение (про “хардкод”)
Backend всё равно должен “понимать” некоторые семантики. Мы намеренно “хардкодим” **не `command_id`, а список зарезервированных `capability`**, который backend поддерживает.

Для MVP:
- поддерживаем `capability in {"extensions.list","extensions.sync"}`;
- tenant может привязать эти capability к разным `executor.*` (включая разные драйверы и разные `command_id`) без изменения кода.

## UI/UX (согласованность с существующей автогенерацией)
В проекте уже есть pattern “UI подстраивается под backend-каталоги/списки” (например driver catalogs для выбора `command_id`).
Этот change следует тому же принципу:
- guided editor для `ui.action_catalog` ДОЛЖЕН позволять задавать `action.capability` (без необходимости уходить в Raw JSON);
- UI ДОЛЖЕН показывать подсказки/варианты для **поддерживаемых backend capability** (curated list), но сохранять возможность ручного ввода строки.

## Правила детерминизма (fail-closed там, где важно)
- Для каждого tenant effective action catalog ДОЛЖЕН быть однозначным для “зарезервированных capability” (не более одного action на capability).
- Если конфигурация нарушает это правило, обновление `ui.action_catalog` ДОЛЖНО быть отвергнуто на этапе update-time validation (staff UI / API).
- Unknown `capability` допустимы в schema (для будущих расширений), но backend НЕ ДОЛЖЕН приписывать им особую семантику, пока явно не поддержит.

## Область изменений
- Orchestrator: enqueue `ibcmd_cli`, extensions plan/apply, event-subscriber snapshot logic.
- Спеки: `command-result-snapshots`, `extensions-action-catalog`, `extensions-plan-apply`.

## Не входит (out of scope)
- Перепроектирование всей модели “actions” (универсальная capability-система для всех доменов/драйверов).
- Новые отдельные UI-экраны/мастера для capability; достаточно расширить существующий guided editor + Raw JSON.

## Риски и миграция
- Нужна совместимость со старыми конфигами `ui.action_catalog`, где `capability` отсутствует.
- Маркер в `metadata` должен быть стабильным, расширяемым и безопасным (без секретов).
