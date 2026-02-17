## 1. Spec & Contracts
- [ ] 1.1 Уточнить требования `pool-workflow-execution-core` для маршрутизации `pool.*` через выделенный execution path в workflow worker (без fallback в generic драйверы).
- [ ] 1.2 Зафиксировать fail-closed поведение при отсутствии pool executor (runtime error вместо `execution_skipped` успеха).
- [ ] 1.3 Уточнить правила status projection: `published/partial_success` только при подтверждённом завершении publication-step.

## 2. Worker: poolops execution path
- [ ] 2.1 Добавить `poolops`-драйвер/адаптер и wiring в workflow engine (`OperationExecutor` dependency injection).
- [ ] 2.2 Реализовать маршрутизацию `pool.*` operation types только в `poolops` path; запретить fallback в generic drivers.
- [ ] 2.3 Реализовать fail-closed обработку misconfiguration (нет executor/adapter) с machine-readable ошибкой.

## 3. Orchestrator: projection hardening
- [ ] 3.1 Обновить rules в pool run projection, чтобы исключить `published` при `workflow:completed` без подтверждённого publication-step результата.
- [ ] 3.2 Убрать/пересобрать синтетические переходы `publication_step_state` из агрегатного workflow status updater.
- [ ] 3.3 Обеспечить обратную совместимость historical run-ов и стабильные diagnostics в API.

## 4. Validation
- [ ] 4.1 Unit tests: routing `pool.*`, fail-closed при отсутствии executor, отсутствие `execution_skipped`-success для pool path.
- [ ] 4.2 Integration tests: `publication_odata` реально исполняется, создаются publication attempts/documents.
- [ ] 4.3 Regression tests: сценарий “workflow completed без публикации” не проецируется как `published`.
- [ ] 4.4 Зафиксировать результат этапа 1 (`poolops + fail-closed + projection`) как базу для transport-консолидации.

## 5. Shared OData transport (зависит от этапа 2 и 3)
- [ ] 5.1 Выделить общий `odata-core` слой для auth/session/retry/error mapping/batch helpers.
- [ ] 5.2 Переключить `poolops(publication_odata)` на `odata-core` без изменения domain-логики шага.
- [ ] 5.3 Переключить `odataops` на `odata-core` с сохранением существующего контракта generic CRUD.
- [ ] 5.4 Удалить дублирующиеся OData transport-компоненты после переключения обоих драйверов.

## 6. Final validation
- [ ] 6.1 Unit/integration tests на паритет transport-поведения `poolops` и `odataops` (retry/errors/auth/session reuse).
- [ ] 6.2 Regression tests: после перехода на `odata-core` сценарий run `500` на 3 организации с созданием документов остаётся зелёным.
- [ ] 6.3 Прогнать `openspec validate add-poolops-driver-workflow-runtime-fail-closed --strict --no-interactive`.
