## 1. Spec & Contracts
- [ ] 1.1 Добавить capability `worker-odata-transport-core` с требованиями shared transport-контракта.
- [ ] 1.2 Зафиксировать в `pool-workflow-execution-core`, что `publication_odata` в worker path использует shared `odata-core` без изменения доменной семантики.

## 2. OData Core Interface
- [ ] 2.1 Спроектировать и реализовать интерфейс `odata-core` (auth/session/retry/error mapping/batch helpers).
- [ ] 2.2 Зафиксировать retry policy (retryable/non-retryable ошибки, backoff+jitter, лимиты попыток).

## 3. Migration: Poolops First
- [ ] 3.1 Переключить `poolops(publication_odata)` на `odata-core`.
- [ ] 3.2 Проверить сохранение контрактов publication diagnostics/idempotency для pool runtime.

## 4. Migration: ODataops
- [ ] 4.1 Переключить `odataops` (`create|update|delete|query`) на `odata-core`.
- [ ] 4.2 Удалить дублирующиеся transport-компоненты после успешного переключения обоих драйверов.

## 5. Observability
- [ ] 5.1 Добавить метрики и tracing для retries/latency/errors/resend-attempt в `odata-core`.
- [ ] 5.2 Проверить, что оба драйвера публикуют одинаковые telemetry-сигналы для transport-слоя.

## 6. Validation
- [ ] 6.1 Unit tests для `odata-core` (retry classification, jitter backoff boundaries, error normalization).
- [ ] 6.2 Integration tests для pool publication и generic CRUD после миграции.
- [ ] 6.3 Регрессионный E2E: распределение 500 на 3 организации с созданием документов в ИБ.
- [ ] 6.4 Прогнать `openspec validate refactor-shared-odata-core --strict --no-interactive`.
