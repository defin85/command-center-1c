# API Gateway OpenAPI Contract

> OpenAPI 3.0.3 contract for gateway-owned endpoints and shared gateway error envelopes.

## Что здесь является source of truth

- `contracts/api-gateway/openapi.yaml` описывает gateway-owned routes и gateway-generated error payloads.
- Текущий generated client для этого контракта живёт в `frontend/src/api/generated-gateway/`.
- Business `/api/v2/*` CRUD routes остаются source-of-truth в `contracts/orchestrator/openapi.yaml` и генерируются в `frontend/src/api/generated/`.

Иными словами: этот контракт нужен не для всего `/api/v2`, а для тех surfaces, которыми gateway владеет сам, плюс для общих envelopes вроде class-aware `429`.

## Что покрывает gateway сейчас

- `GET /health`
- `GET /metrics`
- `GET /api/v2/tracing/traces`
- `GET /api/v2/tracing/traces/{traceId}`
- shared gateway-generated error envelopes, включая correlated `request_id` и class-aware `429`

## Генерация frontend client

Authoritative flow:

```bash
cd frontend && npm run generate:api
```

Что происходит:

- `frontend/orval.config.ts` читает `../contracts/api-gateway/openapi.yaml`
- orval регенерирует `frontend/src/api/generated-gateway/`
- runtime entrypoint для этого клиента: `getCommandCenter1CAPIGateway()`

Минимальный пример:

```ts
import { getCommandCenter1CAPIGateway } from '@/api/generated-gateway'

const gatewayApi = getCommandCenter1CAPIGateway()

const response = await gatewayApi.getTracingGetTraces({
  service: 'orchestrator',
  limit: 20,
  lookback: '1h',
})

console.log(response.data.data)
```

## Rate limiting contract

Gateway больше не документируется как один global `100 req/min per user` bucket. Для authenticated `/api/v2` traffic gateway использует class-aware budgets:

- `shell_critical`
- `interactive`
- `background_heavy`
- `telemetry`

Tracing proxy по умолчанию находится в bounded `interactive` class, поэтому его OpenAPI contract теперь явно объявляет `429`.

### Machine-readable 429 payload

Gateway-generated `429 Too Many Requests` now includes:

- `request_id`
- optional `ui_action_id`
- `rate_limit_class`
- `retry_after_seconds`
- `budget_scope`

Example:

```json
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "request_id": "req-5ab86ce3-d7f2-4cbf-8204-8f3e3479dd15",
  "rate_limit_class": "interactive",
  "retry_after_seconds": 11,
  "budget_scope": "tenant=tenant:unknown;principal=user:user-1;class=interactive"
}
```

## Обновление контракта

Минимальный workflow:

1. Обновить `contracts/api-gateway/openapi.yaml`.
2. Проверить spec:
   `./contracts/scripts/validate-specs.sh`
3. Регенерировать frontend client:
   `cd frontend && npm run generate:api`
4. Прогнать релевантные tests/docs checks для изменённого surface.

Если change затрагивает business `/api/v2/*` routes, править нужно не этот контракт, а `contracts/orchestrator/openapi.yaml`.

## См. также

- [EXAMPLE_USAGE.md](./EXAMPLE_USAGE.md)
- [../README.md](../README.md)
- [OpenAPI 3.0.3](https://spec.openapis.org/oas/v3.0.3)
