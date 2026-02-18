## 1. Spec & Contracts
- [ ] 1.1 Добавить capability `worker-odata-transport-core` с требованиями shared transport-контракта.
- [ ] 1.2 Зафиксировать в `pool-workflow-execution-core`, что `pool.publication_odata` после cutover исполняется через worker `odata-core`, а bridge-path остаётся только для non-OData pool шагов.
- [ ] 1.3 Зафиксировать контракт Big-bang cutover: mixed-mode между `odataops` и `pool.publication_odata` в production запрещён.

## 2. OData Core Interface
- [ ] 2.1 Спроектировать и реализовать интерфейс `odata-core` (auth/session/retry/error mapping/batch helpers).
- [ ] 2.2 Зафиксировать retry policy (retryable/non-retryable ошибки, backoff+jitter, лимиты попыток).
- [ ] 2.3 Встроить compatibility profile checks (`odata-compatibility-profile`) в worker transport path для `pool.publication_odata`.

## 3. Big-bang Readiness
- [ ] 3.1 Подготовить parity-baseline old/new transport behavior для `odataops` и `pool.publication_odata`.
- [ ] 3.2 Подготовить единый release gate и cutover checklist (без per-driver включения в production).
- [ ] 3.3 Подготовить rollback plan и rehearsal (возврат на предыдущий релиз + deterministic fail-closed поведение).

## 4. Big-bang Cutover
- [ ] 4.1 В одном релизном окне одновременно переключить `odataops` и `pool.publication_odata` на worker `odata-core`.
- [ ] 4.2 Отключить legacy OData transport для `pool.publication_odata` в Orchestrator runtime.
- [ ] 4.3 Удалить/деактивировать дубли transport-компонентов после cutover (без длительного mixed-path).

## 5. Observability
- [ ] 5.1 Добавить метрики и tracing для retries/latency/errors/resend-attempt в `odata-core`.
- [ ] 5.2 Проверить, что `odataops` и `pool.publication_odata` публикуют одинаковые telemetry-сигналы transport-слоя после Big-bang.

## 6. Validation
- [ ] 6.1 Unit tests для `odata-core` (retry classification, jitter backoff boundaries, error normalization).
- [ ] 6.2 Integration tests для pool publication и generic CRUD после миграции.
- [ ] 6.3 Регрессионный E2E: распределение 500 на 3 организации с созданием документов в ИБ.
- [ ] 6.4 Rehearsal тест Big-bang cutover (staging) + rollback drill.
- [ ] 6.5 Прогнать `openspec validate refactor-shared-odata-core --strict --no-interactive`.
