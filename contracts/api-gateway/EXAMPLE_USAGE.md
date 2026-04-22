# API Gateway TypeScript Client - Примеры использования

> Актуальные примеры для `frontend/src/api/generated-gateway/`.

Этот client покрывает gateway-owned endpoints из `contracts/api-gateway/openapi.yaml`. Business `/api/v2/*` routes по-прежнему идут через `frontend/src/api/generated/`.

## Генерация клиента

```bash
cd frontend && npm run generate:api
```

## Импорт и создание клиента

```ts
import { getCommandCenter1CAPIGateway } from '@/api/generated-gateway'

export const gatewayApi = getCommandCenter1CAPIGateway()
```

## Поиск trace'ов через gateway

```ts
import { gatewayApi } from '@/api/gatewayClient'

async function loadRecentTraces() {
  const response = await gatewayApi.getTracingGetTraces({
    service: 'orchestrator',
    limit: 20,
    lookback: '1h',
  })

  return response.data.data ?? []
}
```

## Получение конкретного trace

```ts
import { gatewayApi } from '@/api/gatewayClient'

async function loadTrace(traceId: string) {
  const response = await gatewayApi.getTracingGetTrace(traceId)
  return response.data.data?.[0] ?? null
}
```

## Обработка class-aware `429`

```ts
import { AxiosError } from 'axios'
import type { TooManyRequestsResponse } from '@/api/generated-gateway/model'

async function safeLoadTraces() {
  try {
    return await gatewayApi.getTracingGetTraces({
      service: 'api-gateway',
      limit: 10,
      lookback: '30m',
    })
  } catch (error) {
    const axiosError = error as AxiosError<TooManyRequestsResponse>

    if (axiosError.response?.status === 429) {
      const payload = axiosError.response.data
      return {
        retryAfterSeconds: payload.retry_after_seconds,
        budgetClass: payload.rate_limit_class,
        budgetScope: payload.budget_scope,
        requestId: payload.request_id,
      }
    }

    throw error
  }
}
```

## Корреляция для incident/debug tooling

Gateway echoes stable request correlation fields in its error payloads:

```ts
import { AxiosError } from 'axios'
import type { ErrorResponse } from '@/api/generated-gateway/model'

function extractGatewayCorrelation(error: unknown) {
  const axiosError = error as AxiosError<ErrorResponse>
  return {
    requestId: axiosError.response?.data.request_id,
    uiActionId: axiosError.response?.data.ui_action_id,
  }
}
```

## Что использовать для business routes

- `@/api/generated-gateway`: gateway-owned tracing proxy endpoints и gateway error envelopes
- `@/api/generated`: typed business `/api/v2/*` routes from the orchestrator contract
