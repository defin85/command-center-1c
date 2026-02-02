# Change: refactor-extensions-snapshot-trigger-operation-metadata

## Почему
Сейчас обновление `DatabaseExtensionsSnapshot` и запись `CommandResultSnapshot` зависят от того, как именно настроен `ui.action_catalog` *в момент* прихода события `worker completed`. Это приводит к хрупкости:

- tenant может иметь `published` override, а global значение отличается;
- action id может быть произвольным (или меняется в UI), из‑за чего snapshot-триггер может “не сработать” даже при успешном выполнении `infobase.extension.list`;
- получаем “completed + есть stdout” но `DatabaseExtensionsSnapshot`/`CommandResultSnapshot` не создаются.

Нужно сделать snapshot-поведение детерминированным и не зависящим от runtime settings на стадии completion.

## Что меняется
- При enqueue `BatchOperation` система будет ставить **маркер snapshot-поведения в `BatchOperation.metadata`** (операция становится self-contained для snapshot-триггера).
- Event-subscriber будет принимать решение об обновлении snapshot’ов и append-only `CommandResultSnapshot` **только по маркеру в `BatchOperation.metadata`**.
- Для extensions семантика “это list/sync для snapshot” будет задаваться через **явное поле `capability` в action catalog** (универсальный namespaced string), а не через `action.id`.

## Область изменений
- Orchestrator: enqueue `ibcmd_cli`, extensions plan/apply, event-subscriber snapshot logic.
- Спеки: `command-result-snapshots`, `extensions-action-catalog`, `extensions-plan-apply`.

## Не входит (out of scope)
- Перепроектирование всей модели “actions” (универсальная capability-система для всех доменов/драйверов).
- Новые UI-экраны/мастера для capability; достаточно Raw JSON редактора.

## Риски и миграция
- Нужна совместимость со старыми конфигами `ui.action_catalog`, где `capability` отсутствует.
- Маркер в `metadata` должен быть стабильным, расширяемым и безопасным (без секретов).
