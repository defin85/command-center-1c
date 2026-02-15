## 1. Контракт и backend API для полного UI pool lifecycle
- [ ] 1.1 Добавить контрактные endpoint'ы для mutating-операций пула и топологии (pool metadata upsert + topology snapshot upsert) с tenant-boundary и доменной валидацией.
- [ ] 1.2 Расширить контракт создания run direction-specific полем `run_input` и задать обязательность полей по направлению (`top_down`/`bottom_up`).
- [ ] 1.3 Обеспечить сохранение `run_input` в run-state, включение в idempotency fingerprint и передачу в workflow input_context.
- [ ] 1.4 Удалить `source_hash` из публичного create-run контракта и idempotency формулы; удалить legacy-путь из backend/front API.
- [ ] 1.5 Зафиксировать read-контракт historical runs: `run_input` (nullable), `input_contract_version`, без публичного `source_hash`.
- [ ] 1.6 Зафиксировать и реализовать deterministic canonicalization profile для `run_input` (stable key order + decimal normalization).
- [ ] 1.7 Унифицировать error payload новых mutating/create-run endpoint'ов на `application/problem+json` с machine-readable `code`.
- [ ] 1.8 Обновить OpenAPI (`contracts/orchestrator/openapi.yaml`) и regenerated client/types для frontend.
- [ ] 1.9 Подготовить migration guidance/release notes для breaking удаления `source_hash` в create-run API.

## 2. UI каталога пулов и топологии
- [ ] 2.1 Расширить `/pools/catalog`: добавить раздел управления пулами (создание/редактирование/деактивация) в текущем tenant context.
- [ ] 2.2 Реализовать UI-редактор topology snapshot (узлы/рёбра, effective dates, root marker, weight/min/max) с preflight-валидацией обязательных полей.
- [ ] 2.3 Добавить отображение backend validation errors topology в operator-friendly виде без потери введённых данных.
- [ ] 2.4 Добавить optimistic concurrency для topology snapshot update (обязательный `version` token + понятный конфликт в UI).
- [ ] 2.5 Сохранить read-only preview графа по дате как контроль результата после mutating-операций.
- [ ] 2.6 Обеспечить round-trip `version`: UI получает текущий token из read endpoint и передаёт его в mutating update.

## 3. UI запуска и контроля распределений
- [ ] 3.1 Расширить форму `/pools/runs`: direction-specific input, включая обязательную стартовую сумму для `top_down`.
- [ ] 3.2 Добавить UI для `bottom_up` входа (выбор шаблона и загрузка/ввод source payload) без ручного API-клиента.
- [ ] 3.3 Обеспечить end-to-end safe flow в UI: запуск, pre-publish обзор, `confirm-publication`, `abort-publication`, retry failed.
- [ ] 3.4 Обновить таблицу/детали run, чтобы явно показывать `run_input` и связанный provenance.

## 4. Тесты и валидация
- [ ] 4.1 Добавить backend тесты для новых pool/topology mutating endpoint'ов, валидации DAG и direction-specific `run_input`.
- [ ] 4.2 Добавить backend тесты удаления `source_hash` (контракт не принимает поле), idempotency на canonicalized `run_input` и конфликтов optimistic concurrency.
- [ ] 4.3 Добавить backend тесты read-контракта historical runs (`run_input=null`, `input_contract_version=legacy_pre_run_input`).
- [ ] 4.4 Добавить backend тесты deterministic canonicalization (`reordered keys` -> same fingerprint, equivalent decimals -> same fingerprint).
- [ ] 4.5 Добавить backend тесты `application/problem+json` для валидационных и concurrency ошибок.
- [ ] 4.6 Добавить frontend unit/integration тесты для pool CRUD, topology editor, run form validation и safe actions, включая обработку `problem+json`.
- [ ] 4.7 Добавить browser smoke сценарий «3 организации -> минимальный пул -> top_down run со стартовой суммой -> confirm publication».
- [ ] 4.8 Прогнать `openspec validate enable-full-pool-ui-management --strict --no-interactive`.
