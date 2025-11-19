# E2E Tests - Quick Start

> 2-минутное руководство для быстрого старта E2E тестов

## Минимальный запуск (Mock Mode)

```bash
cd tests/e2e

# 1. Запуск (через Makefile)
make test

# ИЛИ вручную:
docker-compose -f docker-compose.e2e.yml up -d
sleep 5
go test -v ./... -timeout 300s
docker-compose -f docker-compose.e2e.yml down -v
```

## Проверка без Docker (компиляция)

```bash
cd tests/e2e
go test -v -short ./...

# Вывод:
# --- SKIP: TestE2E_ExtensionInstall_HappyPath (0.00s)
# --- SKIP: TestE2E_ExtensionInstall_LockFailure (0.00s)
# --- SKIP: TestE2E_ExtensionInstall_InstallFailureWithCompensation (0.00s)
# --- SKIP: TestE2E_MultipleOperations_Concurrent (0.00s)
# PASS
```

## Отдельные тесты

```bash
make test-happy      # Happy Path
make test-lock       # Lock Failure
make test-concurrent # Concurrent ops
```

## Health check

```bash
make health
```

## Troubleshooting

**Порты заняты:**
```bash
docker-compose -f docker-compose.e2e.yml down -v
netstat -ano | findstr "6380 5433 9998 8082"
```

**Mock RAS не запустился:**
```bash
docker logs cc1c-ras-mock
docker-compose -f docker-compose.e2e.yml restart ras-mock
```

## Детали

Полная документация: [README.md](README.md)

---

**Время выполнения:** < 300s (все тесты)
**Требования:** Docker, Go 1.21+
