# Задачи: refactor-extensions-snapshot-trigger-operation-metadata

## 1. Спеки и контракты
- [x] Добавить/обновить delta specs: `command-result-snapshots`, `extensions-action-catalog`, `extensions-plan-apply`.
- [x] Уточнить формат маркера в `BatchOperation.metadata` (`snapshot_kinds` и допустимые значения).
- [x] Зафиксировать “реестр” зарезервированных `capability`, поддерживаемых backend (MVP: `extensions.list`, `extensions.sync`).

## 2. Runtime settings / action catalog
- [x] Расширить schema/validator `ui.action_catalog`: поддержать `extensions.actions[].capability` (необязательное).
- [x] Обновить effective action catalog filtering/validation (RBAC/unknown commands) так, чтобы `capability` не ломало валидацию.
- [x] Добавить update-time validation: запретить (fail-closed) дубликаты зарезервированных `capability` в `extensions.actions[]`.
- [x] Добавить legacy fallback: пока `capability` отсутствует, `id=="extensions.list|extensions.sync"` трактуются как соответствующие capability.

## 3. Enqueue path: установка маркера
- [x] В месте создания `BatchOperation` для `ibcmd_cli` вычислять `snapshot_kinds` по effective `ui.action_catalog` текущего tenant’а и `command_id` (через `capability` → executor binding).
- [x] Записывать маркер в `BatchOperation.metadata` при создании операции (без секретов).
- [x] (Опционально, для дебага) писать `metadata.action_capability`/`metadata.snapshot_source`.

## 4. Completion path: использование маркера
- [x] В event-subscriber обновлять `DatabaseExtensionsSnapshot` и писать `CommandResultSnapshot` только если `snapshot_kinds` содержит `"extensions"`.
- [x] Убрать зависимость completion path от чтения `ui.action_catalog`/`action.id`.

## 5. Extensions plan/apply
- [x] В `extensions_plan_apply` выбирать executors по `capability` (и legacy fallback по `id`).
- [x] Гарантировать, что операции preflight/apply получают корректный маркер snapshot (через общий enqueue path).

## 6. Тесты и валидация
- [x] Backend tests: enqueue выставляет маркер при совпадении `command_id` с extensions capability.
- [x] Backend tests: completion пишет snapshot при наличии маркера, даже если runtime settings менялись/отличаются от global.
- [x] Проверить регрессии парсинга драйверного ответа для extensions snapshot (stdout formats: json/kv/table).
- [x] Прогнать `./scripts/dev/pytest.sh` по затронутым тестам.

## 7. Документация
- [x] Коротко описать в docs/спеках, что `action.id` для extensions теперь произвольный, а semantics задаётся `capability`.
- [x] Обновить docs по staff editor: `capability` доступен в guided editor (опционально) + подсказки по поддерживаемым значениям.
