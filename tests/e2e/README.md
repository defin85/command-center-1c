# E2E Tests для Event-Driven Extension Install

> End-to-End тесты для полного workflow установки расширений в базы 1С

## Описание

E2E тесты проверяют весь жизненный цикл операции установки расширения:
- Отправка запроса через API Gateway
- Обработка в Orchestrator
- Выполнение через Worker
- Взаимодействие с worker и worker
- Compensation flow при ошибках

## Поддерживаемые режимы

### 1. Mock Mode (по умолчанию)

Все внешние сервисы мокируются. Не требует реальной 1C базы.

**Преимущества:**
- Быстрый запуск (нет зависимости от 1C)
- Контролируемое тестирование error scenarios
- Работает в CI/CD pipeline

**Что мокируется:**
- RAS gRPC Gateway (порты 9998, 8082)
- PostgreSQL E2E (порт 5433)
- Redis E2E (порт 6380)

### 2. Real 1C Mode

Требует настроенную тестовую базу 1С для полной интеграции.

**Установка:**
```bash
export TEST_1C_DATABASE=http://localhost/test-base/odata/standard.odata
export TEST_1C_USERNAME=admin
export TEST_1C_PASSWORD=password
```

**Важно:** В Real 1C Mode требуется:
- Доступная база 1С через OData
- Реальный RAS сервер
- Права администратора для lock/unlock базы

## Структура

```
tests/e2e/
├── docker-compose.e2e.yml       # Docker окружение для E2E
├── extension_install_test.go    # 4 E2E сценария
├── helpers.go                   # Test helpers (setup, cleanup, wait)
├── go.mod                       # Go dependencies
├── README.md                    # Эта документация
└── mocks/
    └── ras-grpc-gw/
        ├── Dockerfile           # Mock RAS container
        ├── main.go              # Mock RAS implementation
        ├── go.mod
        └── go.sum
```

## Запуск тестов

### Быстрый старт (Mock Mode)

```bash
cd tests/e2e

# 1. Запустить Docker окружение
docker-compose -f docker-compose.e2e.yml up -d

# 2. Проверить health всех сервисов
curl http://localhost:6380/           # Redis (PING → PONG)
curl http://localhost:8082/health     # Mock RAS
docker exec -it cc1c-postgres-e2e pg_isready

# 3. Запустить тесты
go test -v ./... -timeout 300s

# 4. Cleanup
docker-compose -f docker-compose.e2e.yml down -v
```

### Real 1C Mode

```bash
# 1. Установить переменные окружения для реальной базы
export TEST_1C_DATABASE=http://your-1c-server/test-db/odata/standard.odata
export TEST_1C_USERNAME=admin
export TEST_1C_PASSWORD=your-password

# 2. Запустить Docker окружение (без mock RAS)
docker-compose -f docker-compose.e2e.yml up -d redis-e2e postgres-e2e

# 3. Запустить тесты
go test -v ./... -timeout 300s

# 4. Cleanup
docker-compose -f docker-compose.e2e.yml down -v
unset TEST_1C_DATABASE TEST_1C_USERNAME TEST_1C_PASSWORD
```

### Запуск отдельных тестов

```bash
# Только Happy Path
go test -v -run TestE2E_ExtensionInstall_HappyPath -timeout 120s

# Только Lock Failure
go test -v -run TestE2E_ExtensionInstall_LockFailure -timeout 60s

# Только Install Failure + Compensation
go test -v -run TestE2E_ExtensionInstall_InstallFailureWithCompensation -timeout 120s

# Concurrent operations test
go test -v -run TestE2E_MultipleOperations_Concurrent -timeout 180s
```

### Skip E2E в short mode

```bash
# Пропустить все E2E тесты (для быстрых проверок)
go test -v -short ./...
```

## Тестовые сценарии

### Scenario 1: Happy Path

**Описание:** Полный успешный workflow установки расширения

**Шаги:**
1. Setup E2E environment
2. Create test extension (.cfe)
3. Execute workflow via API Gateway
4. Wait for completion (max 120s)
5. Verify success
6. Cleanup

**Ожидаемый результат:**
- Status: `completed`
- ErrorMessage: пустая
- CompensationEvents: пустой список

**Режимы:**
- ✅ Mock Mode: проверка mock call sequence
- ✅ Real 1C Mode: проверка через OData + rollback

---

### Scenario 2: Lock Failure

**Описание:** Graceful error handling при ошибке блокировки базы

**Шаги:**
1. Setup E2E environment
2. Set mock RAS behavior: `lock_behavior = "fail"`
3. Execute workflow
4. Wait for failure (max 60s)
5. Verify graceful failure

**Ожидаемый результат:**
- Status: `failed`
- ErrorMessage: содержит "lock"
- CompensationEvents: пустой (ошибка на первом шаге)

**Режимы:**
- ✅ Mock Mode: полная проверка (контролируем RAS)
- ❌ Real 1C Mode: не применим (нельзя контролировать RAS)

---

### Scenario 3: Install Failure + Compensation

**Описание:** Ошибка при установке расширения с compensation flow

**Шаги:**
1. Setup E2E environment
2. Set mock RAS: `lock_behavior = "success"`
3. Set mock worker: `install_behavior = "fail"` (TODO)
4. Execute workflow
5. Wait for failure with compensation (max 120s)
6. Verify compensation executed (unlock)

**Ожидаемый результат:**
- Status: `failed`
- ErrorMessage: содержит "installation failed"
- CompensationEvents: содержит "unlock"

**Режимы:**
- ⚠️ Mock Mode: частично (требуется mock worker)
- ❌ Real 1C Mode: не применим (нельзя контролировать worker)

**Примечание:** Для полной реализации требуется mock worker

---

### BONUS: Concurrent Operations

**Описание:** Параллельные операции установки расширений

**Шаги:**
1. Setup E2E environment
2. Start 3 concurrent workflows для разных баз
3. Wait for all to complete (max 180s)
4. Verify all successful

**Ожидаемый результат:**
- Все 3 операции: Status = `completed`
- Нет race conditions
- Правильная изоляция операций

**Режимы:**
- ✅ Mock Mode: полная проверка
- ✅ Real 1C Mode: возможно (если есть 3 тестовые базы)

## Переменные окружения

| Переменная | Описание | По умолчанию | Обязательна |
|-----------|----------|--------------|-------------|
| `TEST_1C_DATABASE` | OData URL тестовой базы 1С | - | Нет (для Mock Mode) |
| `TEST_1C_USERNAME` | Имя пользователя 1С | - | Нет |
| `TEST_1C_PASSWORD` | Пароль пользователя 1С | - | Нет |

## Troubleshooting

### Проблема: Services не стартуют

**Симптомы:**
```
ERROR: for redis-e2e  Cannot start service redis-e2e: port is already allocated
```

**Решение:**
```bash
# Проверить занятые порты
netstat -ano | findstr "6380 5433 9998 8082"  # Windows
lsof -i :6380 -i :5433 -i :9998 -i :8082     # Linux/Mac

# Остановить конфликтующие контейнеры
docker-compose -f docker-compose.e2e.yml down -v

# Или убить процессы на портах
taskkill /PID <pid> /F  # Windows
kill -9 <pid>           # Linux/Mac
```

---

### Проблема: Timeout в тестах

**Симптомы:**
```
FAIL: Timeout waiting for operation mock-operation-20231118150000
```

**Решение:**
```bash
# Увеличить timeout в go test
go test -v ./... -timeout 600s

# Проверить что все сервисы running
docker-compose -f docker-compose.e2e.yml ps

# Проверить логи сервисов
docker logs cc1c-redis-e2e
docker logs cc1c-postgres-e2e
docker logs cc1c-ras-mock
```

---

### Проблема: Mock RAS не отвечает

**Симптомы:**
```
Waiting for Mock RAS at http://localhost:8082...
FAIL: Mock RAS not ready within timeout
```

**Решение:**
```bash
# Проверить что контейнер запущен
docker ps | grep ras-mock

# Проверить логи mock RAS
docker logs cc1c-ras-mock

# Пересобрать mock RAS
cd mocks/ras-grpc-gw
docker build -t ras-mock .

# Перезапустить
docker-compose -f ../../docker-compose.e2e.yml restart ras-mock
```

---

### Проблема: PostgreSQL connection refused

**Симптомы:**
```
FAIL: PostgreSQL not ready within timeout
```

**Решение:**
```bash
# Проверить health
docker exec -it cc1c-postgres-e2e pg_isready

# Проверить переменные окружения
docker exec -it cc1c-postgres-e2e env | grep POSTGRES

# Подключиться вручную
docker exec -it cc1c-postgres-e2e psql -U postgres -d commandcenter_e2e -c "SELECT 1;"

# Если нет базы, пересоздать
docker-compose -f docker-compose.e2e.yml down -v
docker-compose -f docker-compose.e2e.yml up -d postgres-e2e
```

---

### Проблема: Real 1C Mode не работает

**Симптомы:**
```
TEST_1C_DATABASE configured but connection fails
```

**Решение:**
```bash
# 1. Проверить доступность OData endpoint
curl -u admin:password http://your-1c-server/test-db/odata/standard.odata

# 2. Проверить права пользователя
# Должны быть права на:
# - Чтение метаданных
# - Lock/Unlock базы
# - Установка расширений

# 3. Проверить firewall/network
ping your-1c-server
telnet your-1c-server 80

# 4. Fallback на Mock Mode
unset TEST_1C_DATABASE
```

## CI/CD Integration

### GitHub Actions

```yaml
name: E2E Tests

on:
  pull_request:
    branches: [master, develop]
  push:
    branches: [master]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Go
        uses: actions/setup-go@v4
        with:
          go-version: '1.21'

      - name: Start E2E environment
        run: |
          cd tests/e2e
          docker-compose -f docker-compose.e2e.yml up -d
          sleep 10  # Wait for services

      - name: Run E2E tests
        run: |
          cd tests/e2e
          go test -v ./... -timeout 300s

      - name: Cleanup
        if: always()
        run: |
          cd tests/e2e
          docker-compose -f docker-compose.e2e.yml down -v
```

## Best Practices

1. **Always use defer env.Cleanup()**
   - Предотвращает утечку ресурсов
   - Останавливает Docker containers

2. **Use reasonable timeouts**
   - Happy Path: 120s max
   - Failure scenarios: 60s
   - Concurrent: 180s

3. **Skip в short mode**
   ```go
   if testing.Short() {
       t.Skip("Skipping E2E test")
   }
   ```

4. **Log важные шаги**
   ```go
   t.Logf("Executing workflow for database: %s", dbID)
   ```

5. **Verify cleanup**
   ```bash
   # После тестов не должно быть leftover containers
   docker ps -a | grep e2e
   ```

## Метрики

**Target метрики для E2E тестов:**
- Execution time: < 300s (все 4 теста)
- Success rate: 100% в Mock Mode
- Coverage: 80%+ E2E scenarios
- Flakiness: < 1% (max 1 flaky run из 100)

**Current status:**
- ✅ Mock Mode: fully implemented
- ⚠️ Real 1C Mode: partially implemented (требует настройку)
- ⚠️ Compensation flow: требует mock worker

## Roadmap

**Completed:**
- [x] Docker Compose E2E environment
- [x] Mock RAS gRPC Gateway
- [x] E2E test helpers (setup, cleanup, wait)
- [x] Scenario 1: Happy Path (Mock Mode)
- [x] Scenario 2: Lock Failure (Mock Mode)
- [x] Scenario 3: Install Failure skeleton
- [x] BONUS: Concurrent operations test

**TODO:**
- [ ] Mock Batch Service для Scenario 3
- [ ] Real 1C Mode полная поддержка
- [ ] OData verification helpers
- [ ] Extension rollback automation
- [ ] Performance benchmarks
- [ ] Load testing (100+ concurrent operations)

## Контакты

**Вопросы и issues:**
- GitHub Issues: [командный репозиторий]
- Документация проекта: `/docs`
- Integration Tests: `/tests/integration`

---

**Версия:** 1.0.0
**Последнее обновление:** 2025-11-18
**Автор:** CommandCenter1C Team
