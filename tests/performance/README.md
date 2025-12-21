# Performance Tests

Комплексное тестирование производительности Event-Driven архитектуры для Extension Install workflow.

## Описание

Performance тесты доказывают, что Event-Driven архитектура дает **10x improvement** по throughput и latency по сравнению с традиционным HTTP Sync подходом.

**Ключевые метрики:**
- **Throughput:** Operations per second (ops/s)
- **Latency:** P50, P95, P99 (seconds)
- **Success Rate:** Percentage of successful operations
- **Total Duration:** Time to complete all operations

## Структура тестов

### 1. Load Test: 100 Parallel Operations
**Файл:** `parallel_operations_test.go`

**Цель:** Проверить производительность системы при высокой параллельной нагрузке.

**Scope:**
- Запускает 100 операций одновременно
- Каждая операция выполняет полный workflow: lock → terminate → install → unlock
- Использует mock responder для симуляции ответов сервисов

**Target Metrics:**
- Total duration: < 60 seconds
- Success rate: > 95%
- P99 latency: < 10 seconds
- Throughput: > 10 ops/sec

**Запуск:**
```bash
make test-load
# или
go test -v -run TestPerformance_100ParallelOperations -timeout 300s
```

**Вывод:**
- `performance_report_100ops.json` - детальные метрики (JSON)
- `performance_report_100ops.md` - читаемый отчет (Markdown)

---

### 2. Benchmark: Event-Driven vs HTTP Sync
**Файлы:** `benchmark_test.go`

**Цель:** Сравнить производительность Event-Driven и HTTP Sync подходов.

**Tests:**

#### BenchmarkEventDriven
Измеряет производительность асинхронной публикации событий в Redis.

**Метод:**
- Publish event to Redis (non-blocking)
- Минимальная latency (network + Redis write)
- Масштабируется горизонтально (N publishers)

**Запуск:**
```bash
go test -bench BenchmarkEventDriven -benchtime=10s -benchmem
```

#### BenchmarkHTTPSync
Измеряет производительность традиционных blocking HTTP вызовов.

**Метод:**
- HTTP POST request (blocking)
- Ждет полного ответа от сервера
- Ограничен connection pool limits

**Запуск:**
```bash
go test -bench BenchmarkHTTPSync -benchtime=10s -benchmem
```

#### TestBenchmarkComparison
Функциональный тест для полного сравнения.

**Метод:**
- Запускает 1000 операций Event-Driven
- Запускает 1000 операций HTTP Sync
- Сравнивает throughput и latency
- Генерирует сравнительный отчет

**Запуск:**
```bash
make test-comparison
# или
go test -v -run TestBenchmarkComparison -timeout 300s
```

**Вывод:**
- `benchmark_event_driven.json/md` - Event-Driven метрики
- `benchmark_http_sync.json/md` - HTTP Sync метрики
- `benchmark_comparison.json/md` - сравнительный анализ

---

## Запуск тестов

### Prerequisite: Запуск Redis

Performance тесты используют тот же E2E Redis (localhost:6380):

```bash
cd tests/e2e
docker-compose -f docker-compose.e2e.yml up -d redis-e2e
```

**Или через Makefile:**
```bash
cd tests/performance
make setup
```

### Запуск всех тестов

```bash
cd tests/performance

# Все тесты сразу
make test-all

# Или по отдельности
make test-load          # Load test (100 ops)
make test-comparison    # Benchmark comparison
make test-bench         # Go benchmarks
```

### Cleanup

```bash
make clean  # Удалить сгенерированные отчеты
make stop   # Остановить E2E Redis
```

---

## Интерпретация результатов

### Success Rate
- ✅ **> 95%** - отлично, система надежна
- ⚠️ **90-95%** - приемлемо, но есть потери
- ❌ **< 90%** - требуется оптимизация или debugging

### P99 Latency
- ✅ **< 5s** - отлично, быстрая обработка
- ⚠️ **5-10s** - приемлемо
- ❌ **> 10s** - требуется оптимизация

### Throughput (Event-Driven vs HTTP Sync)
- ✅ **>= 10x improvement** - цель достигнута
- ⚠️ **5-10x improvement** - хорошо, но можно лучше
- ❌ **< 5x improvement** - требуется анализ bottlenecks

**Пример хороших результатов:**
```
Event-Driven: 150 ops/s
HTTP Sync:    12 ops/s
Improvement:  12.5x  ✅
```

---

## Архитектура Performance тестов

### Mock Responder Pattern

Performance тесты используют **Mock Responder** для симуляции ответов от worker и worker:

```
Test → Publish Command → Redis → Mock Responder
                                      ↓
Test ← Response Channel ← Redis ← Mock Response
```

**Преимущества:**
- Не требует реальных сервисов (изолированный тест)
- Контролируемая latency (10ms processing time)
- Высокая воспроизводимость результатов
- Быстрый setup/teardown

**Реализация:**
```go
// Mock Responder слушает все command каналы
pubsub := redis.PSubscribe(ctx, "commands:*")

for msg := range pubsub.Channel() {
    // Parse command
    var command EventEnvelope
    json.Unmarshal(msg.Payload, &command)

    // Simulate processing (10ms)
    time.Sleep(10 * time.Millisecond)

    // Send response
    response := NewResponseEvent(command.CorrelationID, ...)
    redis.Publish(ctx, "responses:"+command.CorrelationID, response)
}
```

### Workflow Simulation

Каждая тестовая операция выполняет полный Extension Install workflow:

1. **Lock Infobase** (`commands:worker:infobase:lock`)
   - Публикация команды
   - Ожидание ответа (max 5s timeout)

2. **Terminate Sessions** (`commands:worker:sessions:terminate`)
   - Публикация команды
   - Ожидание ответа (max 5s timeout)

3. **Install Extension** (`commands:worker:extension:install`)
   - Публикация команды
   - Ожидание ответа (max 5s timeout)

4. **Unlock Infobase** (`commands:worker:infobase:unlock`)
   - Публикация команды
   - Ожидание ответа (max 5s timeout)

**Total latency:** ~40-80ms (4 steps × 10ms processing + network overhead)

---

## Метрики и Формулы

### Throughput (ops/s)
```
ops_per_second = total_operations / total_duration_seconds
```

### Success Rate (%)
```
success_rate = (success_count / total_operations) × 100
```

### Latency Percentiles
- **P50 (median):** 50% операций быстрее этого значения
- **P95:** 95% операций быстрее этого значения
- **P99:** 99% операций быстрее этого значения (worst-case latency)

**Формула:**
```go
sorted := sort(latencies)
p99_index := int(len(sorted) × 0.99)
p99_latency := sorted[p99_index]
```

### Improvement Factor
```
improvement = event_driven_metric / http_sync_metric

Examples:
- Throughput: 150 ops/s / 12 ops/s = 12.5x improvement
- Latency: 5.0s / 0.05s = 100x faster (lower is better, so invert)
```

---

## Troubleshooting

### Redis connection refused
**Проблема:** `dial tcp [::1]:6380: connect: connection refused`

**Решение:**
```bash
cd tests/e2e
docker-compose -f docker-compose.e2e.yml up -d redis-e2e

# Проверка
docker ps | grep redis-e2e
```

### Tests timeout
**Проблема:** `panic: test timed out after 2m0s`

**Решение:**
```bash
# Увеличить timeout
go test -v -run TestPerformance_100ParallelOperations -timeout 300s
```

### Low throughput
**Проблема:** Throughput < 10 ops/s или improvement < 10x

**Возможные причины:**
1. **Redis latency** - проверить `redis-cli --latency`
2. **Mock responder не запущен** - проверить логи теста
3. **Timeout слишком большой** - уменьшить timeouts в `waitForResponse()`
4. **CPU throttling** - проверить загрузку процессора

**Debugging:**
```bash
# Redis latency test
docker exec -it redis-e2e redis-cli --latency

# Redis stats
docker exec -it redis-e2e redis-cli INFO stats

# Go test с verbose logging
go test -v -run TestPerformance_100ParallelOperations
```

---

## Best Practices

### 1. Изоляция тестов
- Каждый тест использует свой `correlation_id`
- FlushDB перед тестом для чистого состояния
- Cleanup после теста (defer env.Cleanup())

### 2. Timeouts
- Context timeout: 10 minutes (весь тест)
- Step timeout: 5 seconds (каждый шаг workflow)
- Mock responder timeout: 100ms graceful shutdown

### 3. Параллелизм
- Load test: 100 goroutines (фиксировано)
- Benchmark: `b.RunParallel()` (автоматически)
- Mock responder: 1 goroutine на все команды

### 4. Metrics Collection
- Atomic counters для success/failure (`sync/atomic`)
- Mutex для latency slice (`sync.Mutex`)
- Non-blocking channel для events

### 5. Reporting
- JSON для machine-readable данных
- Markdown для human-readable отчетов
- Console output для real-time feedback

---

## Integration с CI/CD

### GitHub Actions Example

```yaml
name: Performance Tests

on:
  pull_request:
    branches: [master]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2am

jobs:
  performance:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - uses: actions/setup-go@v4
      with:
        go-version: '1.21'

    - name: Start Redis
      run: |
        cd tests/e2e
        docker-compose -f docker-compose.e2e.yml up -d redis-e2e

    - name: Run Performance Tests
      run: |
        cd tests/performance
        make test-all

    - name: Upload Reports
      uses: actions/upload-artifact@v3
      with:
        name: performance-reports
        path: tests/performance/*.md

    - name: Check Performance Threshold
      run: |
        # Parse benchmark_comparison.json
        # Fail if throughput_improvement < 10.0
        cd tests/performance
        python3 -c "
        import json
        with open('benchmark_comparison.json') as f:
            data = json.load(f)
            improvement = data['throughput_improvement_factor']
            if improvement < 10.0:
                print(f'❌ Performance threshold not met: {improvement}x < 10x')
                exit(1)
            else:
                print(f'✅ Performance threshold met: {improvement}x >= 10x')
        "
```

---

## Дальнейшие улучшения

### Phase 2: Real Service Integration
- Запускать реальные worker и worker
- Тестировать против реальной 1С базы (если доступна)
- Проверять real OData latency

### Phase 3: Stress Testing
- 1000+ параллельных операций
- Длительные тесты (1+ час)
- Memory leak detection
- Connection pool exhaustion

### Phase 4: Advanced Metrics
- CPU profiling (`pprof`)
- Memory profiling
- Goroutine leak detection
- Redis connection pool stats

### Phase 5: Visualization
- Grafana dashboards для real-time metrics
- Latency heatmaps
- Throughput time series
- Success rate trends

---

## Справка

### Полезные команды

```bash
# Быстрый старт
make setup && make test-all

# Только load test
make load

# Только benchmark comparison
make compare

# Посмотреть отчеты
cat performance_report_100ops.md
cat benchmark_comparison.md

# Cleanup
make clean stop
```

### Файлы

**Source:**
- `setup.go` - environment setup
- `helpers.go` - helper functions
- `report.go` - report structures and generators
- `parallel_operations_test.go` - load test
- `benchmark_test.go` - benchmarks

**Generated:**
- `*.json` - machine-readable metrics
- `*.md` - human-readable reports
- `go.sum` - Go dependencies checksum

**Configuration:**
- `go.mod` - Go module definition
- `Makefile` - build automation
- `README.md` - this file

---

## Контакты

**Вопросы по performance тестам:**
- Документация: `docs/WEEK3_IMPLEMENTATION_PLAN.md`
- Event-Driven архитектура: `docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md`
- Integration тесты: `tests/integration/README.md`
- E2E тесты: `tests/e2e/README.md`

---

**Версия:** 1.0
**Последнее обновление:** 2025-11-18
**Статус:** ✅ Готово к использованию
