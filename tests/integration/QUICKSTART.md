# 🚀 Quick Start - Integration Tests

## Самый быстрый способ (3 команды)

```bash
cd /c/1CProject/command-center-1c/tests/integration

./test.sh setup      # Запустить Redis+PostgreSQL (один раз)
./test.sh test-all   # Запустить ВСЕ тесты
./test.sh cleanup    # Остановить окружение
```

**Результат:**
```
━━━ Running Basic Event Flow Tests ━━━
✅ TestEventFlow_PublishSubscribe - PASS
✅ TestIdempotency_RedisSetNX - PASS
✅ TestCorrelationID_Tracing - PASS
✅ TestMultipleSubscribers - PASS

━━━ Running Worker State Machine Tests ━━━
✅ TestStateMachine_HappyPath - PASS (4.29s)

SUMMARY:
  Basic Event Flow Tests:   ✅ PASS
  Worker SM Tests:          ✅ PASS

✅ ALL TESTS PASSED!
```

---

## 📋 Доступные команды

### Основные

```bash
./test.sh setup        # Запустить Redis (6380) + PostgreSQL (5433)
./test.sh test-all     # Запустить ВСЕ integration тесты
./test.sh cleanup      # Остановить окружение
./test.sh status       # Проверить что запущено
```

### Выборочные тесты

```bash
./test.sh test-basic           # Только базовые event flow (4 теста)
./test.sh test-worker          # Только Worker State Machine (1 тест)
./test.sh test-worker-v        # Worker SM с verbose output
./test.sh test-single <name>   # Один конкретный тест
```

**Примеры:**
```bash
./test.sh test-single TestEventFlow_PublishSubscribe
./test.sh test-single TestStateMachine_HappyPath
```

### Утилиты

```bash
./test.sh logs         # Логи Docker контейнеров (Ctrl+C выход)
./test.sh redis-cli    # Подключиться к Redis CLI
./test.sh psql         # Подключиться к PostgreSQL
```

### Cleanup

```bash
./test.sh cleanup      # Остановить (сохранить volumes)
./test.sh clean        # Остановить + удалить volumes (чистый старт)
```

---

## 🎯 Типичные сценарии использования

### Scenario 1: Первый запуск

```bash
cd /c/1CProject/command-center-1c/tests/integration

# Запустить всё одной командой
./test.sh all

# Что происходит:
# 1. Setup - запускает Redis + PostgreSQL
# 2. Test-all - запускает 5 integration тестов
# 3. Cleanup - останавливает окружение
```

### Scenario 2: Разработка (многократные запуски)

```bash
# Запустить окружение ОДИН РАЗ
./test.sh setup

# Запускать тесты сколько нужно
./test.sh test-worker          # Быстро проверить Worker SM
./test.sh test-basic           # Проверить event flow
./test.sh test-all             # Проверить всё

# В конце дня - остановить
./test.sh cleanup
```

### Scenario 3: Отладка конкретного теста

```bash
# Setup
./test.sh setup

# Запустить с verbose
./test.sh test-worker-v

# Посмотреть логи Redis (если нужно)
./test.sh logs

# Подключиться к Redis CLI
./test.sh redis-cli
> KEYS *                    # Посмотреть все ключи
> XINFO GROUPS events:*    # Посмотреть consumer groups
> exit

# Cleanup
./test.sh cleanup
```

### Scenario 4: Проблемы с окружением

```bash
# Проверить статус
./test.sh status

# Если Redis не отвечает:
./test.sh clean      # Полная очистка
./test.sh setup      # Запустить заново

# Или вручную:
docker stop cc1c-redis-test cc1c-postgres-test
docker rm cc1c-redis-test cc1c-postgres-test
./test.sh setup
```

---

## ⚡ Быстрые команды

**Самое частое использование:**

```bash
# Проверить что всё работает
./test.sh all

# Проверить только Worker SM
./test.sh setup && ./test.sh test-worker && ./test.sh cleanup

# Отладка
./test.sh setup
./test.sh test-worker-v 2>&1 | less    # Посмотреть full output
./test.sh cleanup
```

---

## 📊 Что тестирует каждая команда?

### test-basic (4 теста, ~2 сек)

- ✅ Event publishing → subscribing (real Redis)
- ✅ Redis SetNX idempotency
- ✅ Correlation ID end-to-end tracing
- ✅ Multiple subscribers fanout

### test-worker (1 тест Happy Path, ~4 сек)

- ✅ Worker State Machine full workflow
- ✅ Init → JobsLocked → SessionsClosed → ExtensionInstalled → Completed
- ✅ Event publishing (4 commands)
- ✅ Event receiving (4 responses)
- ✅ State transitions (5 transitions)
- ✅ Compensation stack management
- ✅ MockEventResponder (эмулирует worker + worker)

### test-all (5 тестов, ~6 сек)

Запускает оба типа тестов последовательно с красивым summary.

---

## 🛠️ Troubleshooting

### "docker: command not found"

**Проблема:** Docker не установлен или не в PATH

**Решение:**
```bash
# Проверить Docker
which docker

# Запустить Docker Desktop (Windows)
```

### "Error: No such container"

**Проблема:** Контейнеры не запущены

**Решение:**
```bash
./test.sh setup
```

### Тест зависает

**Проблема:** Redis не отвечает или deadlock

**Решение:**
```bash
# Перезапустить окружение
./test.sh clean
./test.sh setup

# Проверить статус
./test.sh status

# Запустить с timeout
cd ../../go-services/worker
timeout 30 go test ./test/integration/statemachine/... -v
```

### "Port already allocated"

**Проблема:** Порт 6380 или 5433 уже занят

**Решение:**
```bash
# Найти что занимает порт
netstat -ano | findstr :6380   # Windows
lsof -i :6380                  # Linux/Mac

# Остановить старые контейнеры
docker stop cc1c-redis-test cc1c-postgres-test 2>/dev/null
docker rm cc1c-redis-test cc1c-postgres-test 2>/dev/null

# Запустить заново
./test.sh setup
```

---

## 📝 Дополнительная информация

**Детальная документация:**
- [README.md](README.md) - Полная документация integration тестов
- [EVENT_DRIVEN_ROADMAP.md](../../docs/EVENT_DRIVEN_ROADMAP.md) - Week 3 roadmap

**Где тесты:**
- `tests/integration/event_flow_test.go` - Базовые тесты
- `go-services/worker/test/integration/statemachine/` - Worker SM тесты

**Как запускать вручную:**
```bash
# Базовые
cd /c/1CProject/command-center-1c/tests/integration
go test -v ./...

# Worker SM
cd /c/1CProject/command-center-1c/go-services/worker
go test ./test/integration/statemachine/... -v
```

---

**TL;DR:** Используйте `./test.sh all` для полной проверки! ✅
