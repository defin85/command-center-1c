# A/B Testing Metrics

Prometheus metrics для real-time мониторинга и сравнения Event-Driven vs HTTP Sync режимов выполнения операций.

## Цель

Предоставить данные для принятия решений о rollout Event-Driven архитектуры:
- **10% rollout** → анализ → **50% rollout** → анализ → **100% rollout**

## Метрики

### Основные счетчики

#### `worker_execution_mode_total`
- **Type:** Counter
- **Labels:** `mode` (event_driven, http_sync)
- **Description:** Общее количество выполненных операций по каждому режиму
- **Usage:**
  ```promql
  rate(worker_execution_mode_total[5m])  # ops/sec
  sum(rate(worker_execution_mode_total[1h])) by (mode)  # distribution
  ```

#### `worker_execution_success_total`
- **Type:** Counter
- **Labels:** `mode`
- **Description:** Количество успешно выполненных операций
- **Usage:**
  ```promql
  rate(worker_execution_success_total{mode="event_driven"}[5m]) /
  rate(worker_execution_mode_total{mode="event_driven"}[5m])  # success rate
  ```

#### `worker_execution_failure_total`
- **Type:** Counter
- **Labels:** `mode`
- **Description:** Количество неудачных выполнений
- **Usage:**
  ```promql
  rate(worker_execution_failure_total[5m])  # error rate
  ```

### Latency

#### `worker_execution_duration_seconds`
- **Type:** Histogram
- **Labels:** `mode`
- **Buckets:** [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60]
- **Description:** Время выполнения операций (в секундах)
- **Usage:**
  ```promql
  histogram_quantile(0.99, rate(worker_execution_duration_seconds_bucket{mode="event_driven"}[5m]))  # P99
  histogram_quantile(0.95, rate(worker_execution_duration_seconds_bucket[5m])) by (mode)  # P95 comparison
  ```

### Reliability

#### `worker_compensation_executed_total`
- **Type:** Counter
- **Labels:** `mode`, `reason` (lock_failed, install_failed, etc)
- **Description:** Количество выполненных compensation actions
- **Usage:**
  ```promql
  sum(rate(worker_compensation_executed_total[1h]))  # compensation frequency
  sum(rate(worker_compensation_executed_total[1h])) by (reason)  # breakdown by reason
  ```

#### `worker_circuit_breaker_trips_total`
- **Type:** Counter
- **Labels:** `mode`
- **Description:** Количество срабатываний circuit breaker
- **Usage:**
  ```promql
  rate(worker_circuit_breaker_trips_total[5m])  # trips per second
  ```

### Additional Metrics

#### `worker_retry_attempts_total`
- **Type:** Counter
- **Labels:** `mode`
- **Description:** Количество retry попыток

#### `worker_queue_depth`
- **Type:** Gauge
- **Labels:** `mode`
- **Description:** Текущая глубина очереди задач

#### `worker_success_rate`
- **Type:** Gauge
- **Labels:** `mode`
- **Description:** Текущий success rate (0.0-1.0)
- **Note:** В production лучше использовать Prometheus recording rules

## Recording Rules

Pre-computed aggregations для улучшения производительности dashboards:

### 5-minute window (для real-time monitoring)
- `worker:success_rate:5m` - Success rate
- `worker:throughput:5m` - Throughput (ops/sec)
- `worker:latency_p50:5m` - P50 latency
- `worker:latency_p95:5m` - P95 latency
- `worker:latency_p99:5m` - P99 latency
- `worker:error_rate:5m` - Error rate

### 1-hour window (для trend analysis)
- `worker:success_rate:1h`
- `worker:throughput:1h`
- `worker:latency_p99:1h`
- `worker:error_rate:1h`

## Использование в коде

### Автоматическая интеграция

Metrics уже интегрированы в `dual_mode.go`:
```go
// Автоматически записывается при каждом вызове ProcessExtensionInstall
mode := dm.determineExecutionMode(...)
metrics.ExecutionMode.WithLabelValues(string(mode)).Inc()
```

### Ручная запись

Если нужно записать metrics вручную:
```go
import "github.com/commandcenter1c/commandcenter/worker/internal/metrics"

// Record execution
metrics.RecordExecution("event_driven", 0.123, true)  // mode, duration, success

// Record compensation
metrics.RecordCompensation("event_driven", "lock_failed")

// Record circuit breaker trip
metrics.RecordCircuitBreakerTrip("event_driven")

// Update queue depth
metrics.UpdateQueueDepth("event_driven", 42)
```

## Endpoints

### Metrics Endpoint
- **URL:** `http://localhost:9191/metrics`
- **Format:** Prometheus text format
- **Example:**
  ```bash
  curl http://localhost:9191/metrics | grep worker_execution
  ```

### Expected Output
```
# HELP worker_execution_mode_total Total executions by mode (event_driven vs http_sync)
# TYPE worker_execution_mode_total counter
worker_execution_mode_total{mode="event_driven"} 150
worker_execution_mode_total{mode="http_sync"} 50

# HELP worker_execution_success_total Successful executions by mode
# TYPE worker_execution_success_total counter
worker_execution_success_total{mode="event_driven"} 148
worker_execution_success_total{mode="http_sync"} 49

# HELP worker_execution_duration_seconds Execution duration by mode
# TYPE worker_execution_duration_seconds histogram
worker_execution_duration_seconds_bucket{mode="event_driven",le="0.01"} 120
worker_execution_duration_seconds_bucket{mode="event_driven",le="0.025"} 145
...
```

## Grafana Dashboard

### Import
1. Open Grafana: http://localhost:3001
2. Go to Dashboards → Import
3. Upload: `infrastructure/monitoring/grafana/dashboards/ab_testing_dashboard.json`

### Panels
1. **Execution Mode Distribution** - Pie chart (Event vs HTTP split)
2. **Success Rate Comparison** - Time series (Event vs HTTP)
3. **Latency P99 Comparison** - Time series (Event vs HTTP)
4. **Throughput Comparison** - ops/sec by mode
5. **Error Rate by Mode** - Time series
6. **Compensation Events** - Stat (total count)
7. **Circuit Breaker Trips** - Stat (with thresholds)

### Refresh Rate
- Default: 30 seconds
- Range: Last 1 hour

## Alerting (Optional)

Pre-configured alerts в `recording_rules.yml`:

### EventDrivenLowSuccessRate
- **Threshold:** < 95%
- **Duration:** 5 minutes
- **Severity:** Warning

### HTTPSyncLowSuccessRate
- **Threshold:** < 90%
- **Duration:** 5 minutes
- **Severity:** Warning

### HighCircuitBreakerTripRate
- **Threshold:** > 0.1 trips/sec
- **Duration:** 5 minutes
- **Severity:** Critical

### HighCompensationRate
- **Threshold:** > 0.05 compensations/sec
- **Duration:** 10 minutes
- **Severity:** Warning

## Decision Making Criteria

### Phase 1: 10% Rollout
**Evaluate after 24 hours:**
- Success rate: Event-Driven >= HTTP Sync
- P99 latency: Event-Driven <= 2x HTTP Sync
- Error rate: Event-Driven <= HTTP Sync
- Circuit breaker trips: < 1 per hour

### Phase 2: 50% Rollout
**Evaluate after 48 hours:**
- Success rate: Event-Driven >= 95%
- P99 latency: Event-Driven < 1s
- Error rate: Event-Driven < 5%
- No critical alerts

### Phase 3: 100% Rollout
**Evaluate after 72 hours:**
- Success rate: Event-Driven >= 98%
- P99 latency: Event-Driven < 500ms
- Error rate: Event-Driven < 2%
- Zero circuit breaker trips

## Troubleshooting

### Metrics не появляются в Prometheus

1. Проверить что Worker запущен:
   ```bash
   curl http://localhost:9191/metrics
   ```

2. Проверить Prometheus targets:
   - Open: http://localhost:9090/targets
   - Verify: `worker` target is UP

3. Проверить Prometheus config:
   ```bash
   cat infrastructure/monitoring/prometheus/prometheus.yml | grep worker
   ```

### Dashboard не показывает данные

1. Проверить datasource в Grafana:
   - Settings → Data Sources → Prometheus
   - Verify URL: http://prometheus:9090

2. Проверить что есть данные в Prometheus:
   ```promql
   worker_execution_mode_total
   ```

3. Проверить time range в dashboard (default: last 1 hour)

### Recording rules не работают

1. Проверить что rules загружены:
   - Open: http://localhost:9090/rules
   - Verify: `worker_ab_testing` group is present

2. Проверить Prometheus logs:
   ```bash
   docker logs prometheus 2>&1 | grep -i "error.*rule"
   ```

3. Validate YAML syntax:
   ```bash
   promtool check rules infrastructure/monitoring/prometheus/recording_rules.yml
   ```

## Performance Impact

- **Memory:** ~50KB per mode per metric
- **CPU:** < 0.1% overhead (promauto registration)
- **Network:** ~1KB/scrape (15s interval = 4KB/min)
- **Disk (Prometheus):** ~10MB/day for raw metrics + 5MB/day for recording rules

## См. также

- [Task 3.2.2 Implementation Plan](docs/WEEK3_IMPLEMENTATION_PLAN.md#task-322-ab-testing-metrics)
- [Feature Flags README](../config/README.md)
- [Dual Mode Processor](../processor/dual_mode.go)
- [Prometheus Recording Rules](infrastructure/monitoring/prometheus/recording_rules.yml)
- [Grafana Dashboard](infrastructure/monitoring/grafana/dashboards/ab_testing_dashboard.json)
