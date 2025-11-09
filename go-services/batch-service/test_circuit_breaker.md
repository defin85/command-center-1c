# Circuit Breaker Testing Guide

## Цель
Проверить работу circuit breaker при недоступности cluster-service

## Предварительные условия
- batch-service запущен
- cluster-service НЕ запущен (или остановлен)

## Тестовый сценарий

### 1. Запустить batch-service
```bash
cd go-services/batch-service
./cmd.exe
```

**Ожидаемый результат:**
```
INFO starting batch-service service="cc1c-batch-service"
INFO cluster client initialized url="http://localhost:8088" timeout="30s"
WARN cluster-service not available at startup
INFO Server listening addr="0.0.0.0:8087"
```

### 2. Вызвать GetSessions 3+ раз (через API или тесты)

**Пример curl:**
```bash
# Попытка 1 (circuit закрыт)
curl "http://localhost:8087/api/v1/sessions?infobase_id=test"

# Попытка 2 (circuit закрыт)
curl "http://localhost:8087/api/v1/sessions?infobase_id=test"

# Попытка 3 (circuit закрыт)
curl "http://localhost:8087/api/v1/sessions?infobase_id=test"

# Попытка 4 (circuit ОТКРЫЛСЯ - failure ratio >= 60%)
curl "http://localhost:8087/api/v1/sessions?infobase_id=test"
```

**Ожидаемые логи:**
```
ERROR failed to get sessions error="cluster-service request failed: ..."
ERROR failed to get sessions error="cluster-service request failed: ..."
ERROR failed to get sessions error="cluster-service request failed: ..."
INFO circuit breaker state changed service="cluster-service" from="closed" to="open"
```

### 3. Проверить что circuit открыт

**После открытия circuit:**
- Последующие запросы НЕ вызывают HTTP запросы
- Возвращается instant error: `circuit breaker is open`
- Latency снижается с 30 секунд до ~0ms

**Ожидаемое поведение:**
```bash
# Мгновенный отказ (без timeout 30s)
curl "http://localhost:8087/api/v1/sessions?infobase_id=test"
# Вернет ошибку МГНОВЕННО (без ожидания)
```

### 4. Запустить cluster-service и подождать 60 секунд

**Запустить cluster-service:**
```bash
cd go-services/cluster-service
go run cmd/main.go
```

**Подождать 60 секунд (timeout):**
- Circuit переходит в half-open state
- Разрешено 3 test requests

**Ожидаемые логи (через 60 сек):**
```
INFO circuit breaker state changed service="cluster-service" from="open" to="half-open"
```

### 5. Вызвать GetSessions снова (3 теста)

**Test requests в half-open state:**
```bash
curl "http://localhost:8087/api/v1/sessions?infobase_id=test"
curl "http://localhost:8087/api/v1/sessions?infobase_id=test"
curl "http://localhost:8087/api/v1/sessions?infobase_id=test"
```

**Если cluster-service работает:**
```
INFO circuit breaker state changed service="cluster-service" from="half-open" to="closed"
```

**Если cluster-service НЕ работает:**
```
INFO circuit breaker state changed service="cluster-service" from="half-open" to="open"
```

## Acceptance Criteria

✅ Circuit открывается после 60% failures (min 3 requests)
✅ Open state → instant failures без HTTP timeout
✅ Half-open state позволяет 3 test requests через 60 секунд
✅ State changes логируются с уровнем INFO
✅ HealthCheck НЕ использует circuit breaker (всегда проверяет реальное состояние)

## Параметры circuit breaker

- **MaxRequests:** 3 (half-open state)
- **Interval:** 10s (reset counts)
- **Timeout:** 60s (open → half-open)
- **ReadyToTrip:** 60% failure ratio, min 3 requests

## Дополнительно

### Настройка timeout через ENV
```bash
export CLUSTER_REQUEST_TIMEOUT=10  # 10 секунд
./cmd.exe
```

**Проверка в логах:**
```
INFO cluster client initialized timeout="10s"
```

### Проверка password sanitization
```bash
export LOG_LEVEL=debug
./cmd.exe

# Логи с /P*** вместо реального пароля
DEBUG executing 1cv8.exe command args=["DESIGNER","/Ftest.1cd","/Nadmin","/P***"]
```
