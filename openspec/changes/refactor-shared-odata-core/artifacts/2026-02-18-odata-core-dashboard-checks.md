# Dashboard and checks: odataops vs pool.publication_odata

Дата: 2026-02-18
Задача: `command-center-1c-bqza.18`

## 1) Unified transport metrics (worker odata-core)

Новые канонические метрики transport-level:
- `cc1c_odata_transport_latency_seconds{operation,method,status_class,resend_attempt}`
- `cc1c_odata_transport_retries_total{operation,method,error_class,status_class}`
- `cc1c_odata_transport_errors_total{operation,method,error_code,error_class,status_class,retryable}`
- `cc1c_odata_transport_resend_attempt_total{operation,method}`

Operation labels для сравнения двух путей:
- `operation="odataops.create|update|delete|query"`
- `operation="pool.publication_odata"`

## 2) Trace signals (timeline)

Единые trace events из transport core:
- `external.odata.transport.request.completed`
- `external.odata.transport.request.failed`
- `external.odata.transport.retry.scheduled`

Обязательные поля корреляции:
- `transport_operation`
- `execution_id` (для workflow path)
- `node_id`
- `database_id`
- `attempt`, `resend_attempt`
- `status_class`, `error_code`, `error_class`, `retryable`

## 3) Dashboard checks (PromQL templates)

1. P95 latency by path:
```promql
histogram_quantile(
  0.95,
  sum by (le, operation) (
    rate(cc1c_odata_transport_latency_seconds_bucket[5m])
  )
)
```

2. Retry intensity by path:
```promql
sum by (operation) (
  rate(cc1c_odata_transport_retries_total[5m])
)
```

3. Resend attempt rate by path:
```promql
sum by (operation) (
  rate(cc1c_odata_transport_resend_attempt_total[5m])
)
```

4. Error class distribution by path:
```promql
sum by (operation, error_class) (
  rate(cc1c_odata_transport_errors_total[5m])
)
```

5. Non-retryable conflict/error spike:
```promql
sum by (operation, error_code) (
  rate(cc1c_odata_transport_errors_total{retryable="false"}[5m])
)
```

## 4) Operational acceptance checks

- [x] Сигналы `latency/retries/errors/resend_attempt` есть в едином transport core.
- [x] Оба пути (`odataops`, `pool.publication_odata`) используют одинаковую label model `operation`.
- [x] Trace events содержат attempt/resend + normalized error labels.
- [x] Доступны готовые PromQL checks для post-cutover сравнения путей.
