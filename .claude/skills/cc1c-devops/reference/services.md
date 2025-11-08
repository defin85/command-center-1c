# Service Details Reference

Детальная информация о всех сервисах CommandCenter1C.

## batch-service

**Назначение:** Установка расширений (.cfe) в базы 1С через subprocess

**Технические параметры:**
- **Port:** 8087
- **Path:** go-services/batch-service
- **Language:** Go 1.21+
- **Dependencies:** 1cv8.exe (путь в переменных окружения)

**Запуск:**
```bash
cd go-services/batch-service
go run cmd/main.go
```

**Health check:**
```bash
curl http://localhost:8087/health
# Expected: {"status":"healthy","service":"batch-service","version":"dev"}
```

**API Endpoints:**
- `POST /api/v1/extensions/install` - установка расширения в одну базу
- `POST /api/v1/extensions/batch-install` - batch установка на несколько баз

**Environment Variables:**
```bash
SERVER_HOST=0.0.0.0
SERVER_PORT=8087
EXE_1CV8_PATH="C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe"
V8_DEFAULT_TIMEOUT=300
```

**Use Cases:**
- Установка конфигураций в базы 1С
- Batch операции на множество баз параллельно
- Использование 1cv8.exe напрямую (subprocess)

---

## cluster-service

**Назначение:** Мониторинг и управление кластерами 1С через gRPC протокол

**Технические параметры:**
- **Port:** 8088
- **Path:** go-services/cluster-service
- **Language:** Go 1.21+ / Gin + gRPC client
- **Dependencies:** ras-grpc-gw (КРИТИЧНО - должен быть запущен первым)

**Запуск:**
```bash
cd go-services/cluster-service
go run cmd/main.go
```

**Health check:**
```bash
curl http://localhost:8088/health
# Expected: {"status":"healthy","service":"cluster-service","version":"dev"}
```

**API Endpoints:**
- `GET /api/v1/clusters?server=localhost:1545` - список кластеров
- `GET /api/v1/infobases?server=localhost:1545` - список информационных баз
- `GET /api/v1/sessions?cluster=UUID` - активные сессии (Phase 2)

**Environment Variables:**
```bash
SERVER_HOST=0.0.0.0
SERVER_PORT=8088
GRPC_GATEWAY_ADDR=localhost:9999
LOG_LEVEL=info
```

**Use Cases:**
- Получение списка кластеров, информационных баз, сессий
- Real-time мониторинг с низкой latency (<100ms)
- Integration с Django Orchestrator

---

## ras-grpc-gw (External)

**Назначение:** Production-ready gRPC gateway для RAS протокола 1С Enterprise

**Технические параметры:**
- **Port:** 9999 (gRPC), 8081 (HTTP health)
- **Path:** ../ras-grpc-gw (вне monorepo)
- **Language:** Go 1.21+ / gRPC server
- **Dependencies:** RAS сервер 1С на порту 1545
- **Version:** v1.0.0-cc (форк с production features)

**Запуск:**
```bash
cd ../ras-grpc-gw
go run cmd/main.go localhost:1545
```

**Запуск (binary):**
```bash
cd ../ras-grpc-gw
./bin/ras-grpc-gw.exe --bind :9999 --health :8081 localhost:1545
```

**Health check:**
```bash
curl http://localhost:8081/health
# Expected: {"service":"ras-grpc-gw","status":"healthy","version":"v1.0.0-cc"}
```

**Environment Variables:**
```bash
HEALTH_ADDR=0.0.0.0:8081
DEBUG=false
```

**Use Cases:**
- Прокси между gRPC и бинарным протоколом RAS (Remote Administration Server)
- Connection pooling для масштабирования на 700+ баз
- Health checks и graceful shutdown

**⚠️ ВАЖНО:** Запускать ПЕРВЫМ перед cluster-service!

---

## Django Orchestrator

**Назначение:** Business logic orchestration

**Технические параметры:**
- **Port:** 8000
- **Path:** orchestrator/
- **Language:** Python 3.11+ / Django 4.2+ DRF

**Запуск:**
```bash
cd orchestrator
source venv/Scripts/activate  # Windows GitBash
python manage.py runserver 0.0.0.0:8000
```

**Health check:**
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","database":"connected","redis":"connected"}
```

**Admin Panel:**
http://localhost:8000/admin

**API Documentation (Swagger):**
http://localhost:8000/api/docs

---

## Celery Worker

**Назначение:** Async task processing

**Запуск:**
```bash
cd orchestrator
source venv/Scripts/activate
celery -A config worker -l info
```

**Inspect:**
```bash
celery -A config inspect active
celery -A config inspect stats
```

---

## Celery Beat

**Назначение:** Task scheduler

**Запуск:**
```bash
cd orchestrator
source venv/Scripts/activate
celery -A config beat -l info
```

---

## Go API Gateway

**Назначение:** HTTP routing, auth, rate limiting

**Технические параметры:**
- **Port:** 8080
- **Path:** go-services/api-gateway
- **Language:** Go 1.21+ / Gin

**Запуск:**
```bash
cd go-services/api-gateway
go run cmd/main.go
```

**Health check:**
```bash
curl http://localhost:8080/health
# Expected: {"status":"healthy","version":"1.0.0","uptime":"2h 30m"}
```

---

## Go Worker

**Назначение:** Parallel 1C operations processing

**Технические параметры:**
- **Path:** go-services/worker
- **Language:** Go 1.21+
- **Replicas:** 2 (deploy.replicas)

**Запуск:**
```bash
cd go-services/worker
go run cmd/main.go
```

---

## React Frontend

**Назначение:** UI

**Технические параметры:**
- **Port:** 5173
- **Path:** frontend/
- **Language:** TypeScript / React 18.2 + Ant Design

**Запуск:**
```bash
cd frontend
npm run dev
```

**Health check:**
```bash
curl http://localhost:5173
# Expected: HTTP 200 OK
```

---

## Infrastructure Services (Docker)

### PostgreSQL

**Port:** 5432

**Health check:**
```bash
docker-compose -f docker-compose.local.yml exec postgres pg_isready
# Expected: accepting connections
```

**Connect:**
```bash
docker exec -it postgres psql -U commandcenter -d commandcenter
```

### Redis

**Port:** 6379

**Health check:**
```bash
docker-compose -f docker-compose.local.yml exec redis redis-cli ping
# Expected: PONG
```

**Connect:**
```bash
docker-compose -f docker-compose.local.yml exec redis redis-cli
```

### ClickHouse (Optional)

**Ports:** 8123 (HTTP), 9000 (Native)

**Start:**
```bash
docker-compose -f docker-compose.local.yml --profile analytics up -d
```
