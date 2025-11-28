# Prometheus Metrics для Saga Compensation

## Обзор

Файл `go-services/worker/internal/statemachine/compensation_metrics.go` предоставляет Prometheus метрики для мониторинга:
- Выполнения компенсаций (успешность, время, попытки)
- Восстановления stuck workflows (watchdog)
- Fallback хранения/воспроизведения событий (PostgreSQL fallback)

## Создаваемые метрики

### 1. saga_compensation_total (Counter)

Количество попыток компенсации.

**Labels:** `name` (имя компенсации), `success` (true/false)

```promql
# Общее количество попыток (все компенсации)
saga_compensation_total

# Успешные компенсации для конкретного компонента
saga_compensation_total{name="rollback_transaction", success="true"}

# Неудачные компенсации
saga_compensation_total{name="cleanup_resources", success="false"}
```

### 2. saga_compensation_duration_seconds (Histogram)

Время выполнения компенсации в секундах.

**Labels:** `name` (имя компенсации)
**Buckets:** 0.1s, 0.2s, 0.4s, 0.8s, 1.6s, 3.2s, 6.4s, 12.8s, 25.6s, 51.2s, 102.4s

```promql
# Среднее время выполнения за 5 минут
rate(saga_compensation_duration_seconds_sum[5m]) / 
rate(saga_compensation_duration_seconds_count[5m])

# 95-й перцентиль latency
histogram_quantile(0.95, saga_compensation_duration_seconds_bucket)
```

### 3. saga_compensation_attempts (Histogram)

Количество попыток (включая retries) для выполнения компенсации.

**Labels:** `name` (имя компенсации)
**Buckets:** 1, 2, 3, 4, 5

```promql
# Среднее количество попыток
rate(saga_compensation_attempts_sum[5m]) / 
rate(saga_compensation_attempts_count[5m])

# Компенсации требующие более 2 попыток
increase(saga_compensation_attempts_bucket{le="2"}[1h])
```

### 4. saga_stuck_workflows_recovered_total (Counter)

Количество stuck workflows восстановленных watchdog'ом.

```promql
# Скорость восстановления stuck workflows
rate(saga_stuck_workflows_recovered_total[5m])

# Общее количество восстановленных за час
increase(saga_stuck_workflows_recovered_total[1h])
```

### 5. saga_events_fallback_stored_total (Counter)

Количество событий сохраненных в PostgreSQL fallback.

```promql
# События в fallback за последний час
increase(saga_events_fallback_stored_total[1h])

# Скорость сохранения в fallback
rate(saga_events_fallback_stored_total[5m])
```

### 6. saga_events_fallback_replayed_total (Counter)

Количество событий воспроизведенных из PostgreSQL fallback.

```promql
# События воспроизведены из fallback за последний час
increase(saga_events_fallback_replayed_total[1h])

# Скорость воспроизведения из fallback
rate(saga_events_fallback_replayed_total[5m])
```

## Практические примеры Prometheus запросов

### Успешность компенсаций

```promql
# Процент успешных компенсаций
(saga_compensation_total{success="true"} / 
 (saga_compensation_total{success="true"} + saga_compensation_total{success="false"})) * 100

# Процент для конкретного компонента
(saga_compensation_total{name="rollback_transaction", success="true"} / 
 (saga_compensation_total{name="rollback_transaction", success="true"} + 
  saga_compensation_total{name="rollback_transaction", success="false"})) * 100
```

### Время выполнения

```promql
# Минимальное время
histogram_quantile(0.10, saga_compensation_duration_seconds_bucket)

# Медиана
histogram_quantile(0.50, saga_compensation_duration_seconds_bucket)

# 99-й перцентиль
histogram_quantile(0.99, saga_compensation_duration_seconds_bucket)

# Максимальное наблюдаемое время
saga_compensation_duration_seconds_bucket{le="+Inf"}
```

### Аномалии и проблемы

```promql
# Компенсации требующие 3+ попыток (проблемные)
rate(saga_compensation_attempts_bucket{le="3"}[5m]) - 
rate(saga_compensation_attempts_bucket{le="2"}[5m])

# Увеличение count failed events в fallback (Redis down?)
rate(saga_events_fallback_stored_total[1m]) > 0.1

# Много stuck workflows (проблемы с recovery)
rate(saga_stuck_workflows_recovered_total[5m]) > 0.5
```

## Интеграция с Grafana

### Рекомендуемая визуализация

1. **Compensation Success Rate** (Gauge)
   ```promql
   (saga_compensation_total{success="true"} / 
    (saga_compensation_total{success="true"} + saga_compensation_total{success="false"})) * 100
   ```

2. **Compensation Duration (p95)** (Graph)
   ```promql
   histogram_quantile(0.95, rate(saga_compensation_duration_seconds_bucket[5m]))
   ```

3. **Compensation Attempts Distribution** (Heatmap)
   ```promql
   saga_compensation_attempts_bucket
   ```

4. **Stuck Workflows Recovery Rate** (Graph)
   ```promql
   rate(saga_stuck_workflows_recovered_total[5m])
   ```

5. **Fallback Events Flow** (Stacked Area)
   ```promql
   rate(saga_events_fallback_stored_total[5m])
   rate(saga_events_fallback_replayed_total[5m])
   ```

## Пороги и alerts

### Critical

```yaml
- alert: CompensationFailureRate
  expr: |
    (saga_compensation_total{success="false"} / saga_compensation_total) > 0.1
  for: 5m
  annotations:
    summary: "High compensation failure rate (>10%)"

- alert: StuckWorkflows
  expr: rate(saga_stuck_workflows_recovered_total[5m]) > 1
  for: 5m
  annotations:
    summary: "Too many stuck workflows being recovered"

- alert: FallbackStorageHigh
  expr: rate(saga_events_fallback_stored_total[1m]) > 0.5
  for: 5m
  annotations:
    summary: "High rate of events in fallback (Redis issue?)"
```

### Warning

```yaml
- alert: CompensationDurationHigh
  expr: |
    histogram_quantile(0.95, rate(saga_compensation_duration_seconds_bucket[5m])) > 30
  for: 10m
  annotations:
    summary: "Compensation p95 latency > 30s"

- alert: CompensationRetriesHigh
  expr: |
    (rate(saga_compensation_attempts_sum[5m]) / 
     rate(saga_compensation_attempts_count[5m])) > 1.5
  for: 10m
  annotations:
    summary: "Average compensation retries > 1.5"
```

## Интеграция в код

```go
package myservice

import "github.com/commandcenter1c/commandcenter/worker/internal/statemachine"

func setupCompensation() {
    // Создаем recorder
    metricsRecorder := statemachine.NewPrometheusMetricsRecorder()
    
    // Используем в executor
    executor := statemachine.NewCompensationExecutor(
        config,
        auditLogger,
        metricsRecorder,
    )
    
    // Метрики записываются автоматически
    result := executor.ExecuteWithRetry(ctx, operationID, compensation)
}

// Для watchdog и fallback используй напрямую
statemachine.RecordStuckWorkflowRecovered()
statemachine.RecordFailedEventStored()
statemachine.RecordFailedEventReplayed()
```

## Требования

- Prometheus 2.0+
- Grafana 7.0+ (для dashboards)
- Go client library: github.com/prometheus/client_golang

## Связанная документация

- [compensation_executor.go](go-services/worker/internal/statemachine/compensation_executor.go) - Executor с support для MetricsRecorder
- [compensation.go](go-services/worker/internal/statemachine/compensation.go) - Compensation interface
- [EVENT_DRIVEN_ARCHITECTURE.md](docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md) - Event-driven design
