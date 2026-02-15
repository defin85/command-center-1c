## 1. Контракт и backend API для полного UI pool lifecycle
- [ ] 1.1 Добавить контрактные endpoint'ы для mutating-операций пула и топологии (pool metadata upsert + topology snapshot upsert) с tenant-boundary и доменной валидацией.
- [ ] 1.2 Расширить контракт создания run direction-specific полем `run_input` и задать обязательность полей по направлению (`top_down`/`bottom_up`).
- [ ] 1.3 Обеспечить сохранение `run_input` в run-state, включение в idempotency fingerprint и передачу в workflow input_context.
- [ ] 1.4 Обновить OpenAPI (`contracts/orchestrator/openapi.yaml`) и regenerated client/types для frontend.

## 2. UI каталога пулов и топологии
- [ ] 2.1 Расширить `/pools/catalog`: добавить раздел управления пулами (создание/редактирование/деактивация) в текущем tenant context.
- [ ] 2.2 Реализовать UI-редактор topology snapshot (узлы/рёбра, effective dates, root marker, weight/min/max) с preflight-валидацией обязательных полей.
- [ ] 2.3 Добавить отображение backend validation errors topology в operator-friendly виде без потери введённых данных.
- [ ] 2.4 Сохранить read-only preview графа по дате как контроль результата после mutating-операций.

## 3. UI запуска и контроля распределений
- [ ] 3.1 Расширить форму `/pools/runs`: direction-specific input, включая обязательную стартовую сумму для `top_down`.
- [ ] 3.2 Добавить UI для `bottom_up` входа (выбор шаблона и загрузка/ввод source payload) без ручного API-клиента.
- [ ] 3.3 Обеспечить end-to-end safe flow в UI: запуск, pre-publish обзор, `confirm-publication`, `abort-publication`, retry failed.
- [ ] 3.4 Обновить таблицу/детали run, чтобы явно показывать `run_input` и связанный provenance.

## 4. Тесты и валидация
- [ ] 4.1 Добавить backend тесты для новых pool/topology mutating endpoint'ов, валидации DAG и direction-specific `run_input`.
- [ ] 4.2 Добавить frontend unit/integration тесты для pool CRUD, topology editor, run form validation и safe actions.
- [ ] 4.3 Добавить browser smoke сценарий «3 организации -> минимальный пул -> top_down run со стартовой суммой -> confirm publication».
- [ ] 4.4 Прогнать `openspec validate enable-full-pool-ui-management --strict --no-interactive`.
