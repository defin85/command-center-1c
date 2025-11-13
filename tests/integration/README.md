# Integration Tests для Event-Driven Architecture

Этот каталог содержит integration тесты для event-driven workflow между сервисами.

## Что тестируют integration тесты?

В отличие от **unit тестов** (которые используют mocks для всех зависимостей), **integration тесты** проверяют взаимодействие между реальными компонентами:

| Component | Unit Test | Integration Test |
|-----------|-----------|------------------|
| **Redis** | ❌ Mock | ✅ Real Redis container |
| **Event Publisher** | ❌ Mock | ✅ Real (shared/events) |
| **Event Subscriber** | ❌ Mock | ✅ Real (shared/events) |
| **Event Handlers** | ✅ Real | ✅ Real |
| **RAS/gRPC calls** | ❌ Mock | ❌ Mock (нет real 1C) |
| **PostgreSQL** | ❌ Mock | ⚠️ Real (в E2E тестах) |

## Структура тестов

```
tests/integration/
├── lock_workflow_test.go       # Lock command workflow (DEMO)
├── unlock_workflow_test.go     # Unlock command workflow (TODO)
├── terminate_workflow_test.go  # Terminate sessions workflow (TODO)
├── install_workflow_test.go    # Extension install workflow (TODO)
├── e2e_full_workflow_test.go   # Full E2E с PostgreSQL (TODO)
├── docker-compose.test.yml     # Test environment (Redis + PostgreSQL)
├── go.mod                      # Go dependencies
└── README.md                   # Эта инструкция
```

## Quick Start

### 1. Запуск Test Redis

```bash
# Start Redis test instance на порту 6380
docker run -d --name redis-test -p 6380:6379 redis:7-alpine

# Проверка что Redis работает
docker exec redis-test redis-cli ping
# Ожидается: PONG
```

### 2. Запуск Integration Тестов

```bash
cd /c/1CProject/command-center-1c/tests/integration

# Установить зависимости
go mod download

# Запустить все integration тесты
go test -v ./...

# Запустить конкретный тест
go test -v -run TestLockWorkflow_EndToEnd

# Запустить с детальным выводом
go test -v -run TestLockWorkflow_EndToEnd 2>&1 | tee test.log
```

### 3. Cleanup

```bash
# Остановить и удалить test Redis
docker stop redis-test && docker rm redis-test
```

## Демо тест: Lock Workflow

Файл: `lock_workflow_test.go`

**Что проверяет:**
1. ✅ Публикация lock command в Redis
2. ✅ cluster-service обрабатывает команду (real event handler)
3. ✅ cluster-service вызывает LockInfobase (mock RAS)
4. ✅ cluster-service публикует locked event
5. ✅ Проверка correlation_id end-to-end
6. ✅ Idempotency: duplicate command → skip operation, publish success
7. ✅ Fail-open: Redis unavailable → operation continues

**Пример вывода:**
```
=== RUN   TestLockWorkflow_EndToEnd
    lock_workflow_test.go:105: Publishing lock command to cluster-service...
    lock_workflow_test.go:109: Waiting for locked event from cluster-service...
    lock_workflow_test.go:113: ✅ Locked event received successfully
    lock_workflow_test.go:121: Event payload: {ClusterID:cluster-123 InfobaseID:infobase-456 DatabaseID:db-789 Message:Infobase locked successfully}
    lock_workflow_test.go:131: --- Testing Idempotency ---
    lock_workflow_test.go:134: Publishing duplicate lock command (testing idempotency)...
    lock_workflow_test.go:141: ✅ Idempotent response received (duplicate command handled correctly)
    lock_workflow_test.go:146: ✅ Service NOT called second time (idempotency working)
    lock_workflow_test.go:158: ✅ Integration test completed successfully
--- PASS: TestLockWorkflow_EndToEnd (0.25s)
PASS
```

## Architecture

### Unit Test (Existing)

```
Test → Mock Publisher → Mock Redis → Mock Service
  ✓ Fast (< 10ms)
  ✓ No external dependencies
  ✗ Не проверяет real integration
```

### Integration Test (NEW)

```
Test → Real Publisher → Real Redis → Real Handler → Mock Service
  ✓ Проверяет real event flow
  ✓ Проверяет real Redis Pub/Sub
  ✓ Проверяет idempotency
  ✗ Requires Docker
  ⚠ Slower (200-500ms)
```

### E2E Test (TODO)

```
Test → Real Publisher → Real Redis → Real Handler → Real Service → Real PostgreSQL
  ✓ Проверяет ПОЛНЫЙ workflow
  ✓ Проверяет DB updates
  ✗ Requires Docker Compose
  ⚠ Slowest (1-5 seconds)
```

## Docker Compose для E2E тестов

Создайте `docker-compose.test.yml`:

```yaml
version: '3.8'

services:
  redis-test:
    image: redis:7-alpine
    ports:
      - "6380:6379"
    networks:
      - test-network

  postgres-test:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: commandcenter_test
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5433:5432"
    networks:
      - test-network

networks:
  test-network:
    driver: bridge
```

**Запуск:**
```bash
docker-compose -f docker-compose.test.yml up -d
go test -v ./...
docker-compose -f docker-compose.test.yml down
```

## Troubleshooting

### Redis not available

**Проблема:**
```
Test Redis not available on localhost:6380
```

**Решение:**
```bash
docker run -d --name redis-test -p 6380:6379 redis:7-alpine
```

### Port already in use

**Проблема:**
```
Error starting userland proxy: listen tcp4 0.0.0.0:6380: bind: address already in use
```

**Решение:**
```bash
# Найти процесс использующий порт
netstat -ano | findstr :6380  # Windows
lsof -i :6380                 # Linux/Mac

# Остановить старый контейнер
docker stop redis-test && docker rm redis-test

# Запустить заново
docker run -d --name redis-test -p 6380:6379 redis:7-alpine
```

### Test timeout

**Проблема:**
```
Timeout waiting for locked event (2 seconds)
```

**Возможные причины:**
1. Redis не запущен
2. Event handler не обрабатывает событие
3. Событие публикуется в другой channel

**Debugging:**
```bash
# Проверить Redis logs
docker logs redis-test

# Проверить что events публикуются
docker exec redis-test redis-cli MONITOR

# Увеличить timeout в тесте (для debugging)
case <-time.After(10 * time.Second):  // Было 2 секунды
```

## Next Steps

1. **Добавить больше integration тестов:**
   - [ ] unlock_workflow_test.go
   - [ ] terminate_workflow_test.go
   - [ ] install_workflow_test.go

2. **Добавить E2E тесты с PostgreSQL:**
   - [ ] e2e_full_workflow_test.go
   - [ ] Проверка Task status updates в DB
   - [ ] Проверка BatchOperation state transitions

3. **CI/CD Integration:**
   - [ ] GitHub Actions workflow для integration tests
   - [ ] Docker Compose setup в CI
   - [ ] Test coverage reporting

4. **Performance тесты:**
   - [ ] 100 parallel operations
   - [ ] Event latency measurement (p50/p95/p99)
   - [ ] Memory leak detection

## References

- [Event-Driven Roadmap](../../docs/EVENT_DRIVEN_ROADMAP.md)
- [Event-Driven Architecture](../../docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md)
- [Shared Events Library](../../go-services/shared/events/)
- [cluster-service Handlers](../../go-services/cluster-service/internal/eventhandlers/)
