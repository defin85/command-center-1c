# OData Transport Boundaries

**Дата:** 2026-02-26  
**Статус:** APPROVED

## Контекст
В кодовой базе используются несколько OData-путей: runtime execution в worker, metadata catalog в orchestrator, а также legacy service-код в `apps/databases`.

Без явных owner boundaries возникают дубли transport-логики, дрейф ошибок и риск новых direct HTTP обходов.

## Решение
1. **Worker transport owner для runtime side effects**
   - `go-services/worker/internal/odata/*` является каноническим transport core для:
   - `odataops` (`create/update/delete/query`);
   - `pool.publication_odata`.
   - Доменные драйверы (`odataops`, `poolops`) используют transport через `odata.Service`, без дублирования HTTP-логики.

2. **Orchestrator metadata path использует общий adapter**
   - Для чтения `/$metadata` в orchestrator используется `apps.databases.odata.ODataMetadataAdapter`.
   - Прямые вызовы `requests.get(.../$metadata)` в доменном коде запрещены.

3. **Auth source-of-truth для metadata/publication — mapping-only**
   - Credentials берутся через `InfobaseUserMapping` (actor/service strategy).
   - Fallback на `Database.username/password` для metadata/publication запрещён.

4. **Fail-closed error contract**
   - Ошибки metadata/publication возвращают machine-readable поля.
   - Минимум: `code`, `detail`; для ссылочных/upstream ошибок — `errors[]` с `code/path/detail`.

5. **Legacy service path в orchestrator должен быть консистентен с OData core API**
   - `apps/databases/services/odata_operation_service.py` обязан использовать актуальную сигнатуру `session_manager.get_client(...)`.
   - Скрытые несовместимости сигнатур и payload shape считаются архитектурным дефектом.

## Разрешённые паттерны
- Worker: только `internal/odata` как transport слой.
- Orchestrator metadata: только через `apps.databases.odata` adapter.
- Доменные сервисы: orchestration/validation/diagnostics, но не raw HTTP transport.

## Запрещённые паттерны
- Новые direct HTTP вызовы к OData (`requests/httpx/net/http`) в доменных модулях вне канонического OData слоя.
- Runtime mixed-mode, где часть OData execution использует core, а часть legacy transport.
- Silent fallback на legacy database credentials в metadata/publication path.

## Последствия
**Плюсы**
- Единое поведение retry/auth/error normalization.
- Прозрачные owner boundaries для ревью и эксплуатации.
- Меньше регрессий при развитии metadata/publication.

**Минусы**
- Появляется дополнительный adapter-слой в orchestrator.
- Требуется поддерживать anti-regression проверки для boundary discipline.
