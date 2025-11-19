# Performance Tests - Quick Start

⏱️ **Время:** 2-3 минуты

---

## Быстрый запуск (одной командой)

```bash
cd tests/performance
make setup && make test-all
```

**Это запустит:**
1. E2E Redis (localhost:6380)
2. Load test (100 parallel ops)
3. Benchmark comparison (Event-Driven vs HTTP Sync)
4. Генерацию всех отчетов

---

## Шаг за шагом

### 1. Setup

```bash
cd tests/performance

# Запустить E2E Redis
make setup

# Или вручную:
cd ../e2e && docker-compose -f docker-compose.e2e.yml up -d redis-e2e && cd ../performance

# Проверить:
docker ps | grep redis
# Ожидается: cc1c-redis-test или cc1c-redis-e2e на порту 6380
```

### 2. Load Test (100 parallel ops)

```bash
make test-load

# Или вручную:
go test -v -run TestPerformance_100ParallelOperations -timeout 300s
```

**Ожидаемый результат:**
- Duration: ~5-10 seconds
- Success rate: ~91-100%
- Throughput: ~20 ops/s
- Отчеты: `performance_report_100ops.json/md`

### 3. Benchmark Comparison

```bash
make test-comparison

# Или вручную:
go test -v -run TestBenchmarkComparison -timeout 300s
```

**Ожидаемый результат:**
- Event-Driven: ~3000-4000 ops/s
- HTTP Sync: ~80-100 ops/s
- **Improvement: ~40x** 🎉
- Отчеты: `benchmark_*.json/md`

### 4. Просмотр отчетов

```bash
# Comparison (ГЛАВНЫЙ ОТЧЕТ)
cat benchmark_comparison.md

# Load test
cat performance_report_100ops.md

# Summary
cat PERFORMANCE_TEST_SUMMARY.md
```

### 5. Cleanup

```bash
make clean  # Удалить *.json и *.md отчеты
make stop   # Остановить Redis
```

---

## Что должно получиться

### Load Test Output

```
========================================
   100 PARALLEL OPERATIONS LOAD TEST
========================================
✓ Performance environment initialized
  - Redis: localhost:6380
  - Context timeout: 10 minutes
✓ Redis DB flushed
✓ Mock responder started
Starting 100 parallel operations...
Progress: 10/100 operations completed
Progress: 20/100 operations completed
...
✓ All operations completed in 5.07s

========================================
      PERFORMANCE TEST SUMMARY
========================================
Total Operations:    100
Success Count:       91
Failure Count:       9
Success Rate:        91.00%
----------------------------------------
Total Duration:      5.07s
Operations/sec:      19.74
----------------------------------------
Latency Distribution:
  Min:      3.059s
  Mean:     3.694s
  P50:      3.620s
  P95:      5.027s
  P99:      5.066s
  Max:      5.066s
========================================
✓ 100 Parallel Operations test PASSED
```

### Benchmark Comparison Output

```
========================================
  EVENT-DRIVEN vs HTTP SYNC BENCHMARK
========================================
Running Event-Driven benchmark...
  Event-Driven: 1000 ops in 258ms (3867 ops/s)

Running HTTP Sync benchmark...
  HTTP Sync: 1000 ops in 10.7s (92.93 ops/s)

--- Comparison ---
========================================
  EVENT-DRIVEN vs HTTP SYNC COMPARISON
========================================
Metric              Event-Driven    HTTP Sync      Improvement
------------------------------------------------------------------------
Throughput          3867.53 ops/s   92.93 ops/s    41.6x
P50 Latency         0.000s          0.011s         360.1x faster
P95 Latency         0.001s          0.011s         16.3x faster
P99 Latency         0.001s          0.012s         11.5x faster
========================================
✅ TARGET ACHIEVED: Event-Driven shows 10x+ improvement!
========================================

✅ Event-Driven shows 41.6x throughput improvement (>= 10x target)
✓ Benchmark comparison completed
```

---

## Troubleshooting

### Redis не запускается

**Проблема:** `port is already allocated`

**Решение:**
```bash
# Проверить что запущено
docker ps | grep redis

# Если уже есть Redis на 6380 - использовать его
# Если нет - остановить и перезапустить:
make stop && make setup
```

### Тесты падают с timeout

**Проблема:** `test timed out after 2m0s`

**Решение:**
```bash
# Увеличить timeout
go test -v -run TestPerformance_100ParallelOperations -timeout 300s
```

### Low throughput

**Проблема:** Throughput < 10 ops/s

**Решение:**
1. Проверить Redis latency: `docker exec -it cc1c-redis-test redis-cli --latency`
2. Проверить CPU load
3. Перезапустить тесты: `make clean && make test-all`

---

## Доступные команды

```bash
make help          # Показать все команды
make setup         # Запустить Redis
make deps          # Скачать Go dependencies
make test-load     # Load test (100 ops)
make test-bench    # Go benchmarks
make test-comparison  # Benchmark comparison
make test-all      # Все тесты
make clean         # Удалить отчеты
make stop          # Остановить Redis
```

---

## Файлы отчетов

После запуска тестов будут созданы:

**JSON (machine-readable):**
- `performance_report_100ops.json`
- `benchmark_event_driven.json`
- `benchmark_http_sync.json`
- `benchmark_comparison.json` ⭐

**Markdown (human-readable):**
- `performance_report_100ops.md`
- `benchmark_event_driven.md`
- `benchmark_http_sync.md`
- `benchmark_comparison.md` ⭐

**Documentation:**
- `PERFORMANCE_TEST_SUMMARY.md` - итоговый summary ⭐
- `README.md` - полная документация
- `QUICKSTART.md` - этот файл

---

## Следующие шаги

После успешного запуска тестов:

1. **Прочитай summary:** `cat PERFORMANCE_TEST_SUMMARY.md`
2. **Посмотри comparison:** `cat benchmark_comparison.md`
3. **Проверь acceptance criteria** - все ли PASS
4. **Commit результаты** (опционально)

```bash
git add tests/performance/
git commit -m "feat(tests): Add performance tests - 41.6x improvement validated"
```

---

**Время выполнения:** 2-3 минуты
**Сложность:** ⭐ Легко
**Требования:** Docker, Go 1.21+

✅ Готово к запуску!
