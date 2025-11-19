# Worker State Machine Integration Tests

Полный набор integration тестов для Worker State Machine, покрывающий failure scenarios, дедупликацию, восстановление и graceful degradation.

## Запуск тестов

### Предварительные требования

1. **Test Redis должен быть запущен:**
   ```bash
   cd /c/1CProject/command-center-1c/tests/integration
   docker-compose -f docker-compose.test.yml up -d redis-test
   ```

### Запуск всех тестов

```bash
cd /c/1CProject/command-center-1c/go-services/worker
go test -v ./test/integration/statemachine -timeout 300s
```

## Покрытие

- Tests 1-7: failure_scenarios_test.go (быстрые, 20-30s each)
- Tests 8-9: testcontainers_test.go (медленные, 60s each)

**Target coverage:** > 80% для State Machine integration scenarios

Подробную документацию см. в самих тестах.
