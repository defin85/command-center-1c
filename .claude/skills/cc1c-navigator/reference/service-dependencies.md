# Service Dependencies - Детальный граф

## Runtime Dependencies

### Frontend (React:5173)
```
Frontend
  ↓ HTTP
API Gateway (:8080)
```

**Зависимости:**
- API Gateway ДОЛЖЕН быть запущен
- JWT token для authenticated requests

**Endpoints используемые:**
- `GET /api/databases` - список баз
- `POST /api/operations/execute` - выполнение операций
- `GET /health` - health check

---

### API Gateway (Go:8080)
```
API Gateway
  ↓ HTTP
Orchestrator (:8000)
```

**Зависимости:**
- Orchestrator ДОЛЖЕН быть запущен
- JWT secret для token verification

**Routing:**
- `/api/*` → Proxy к Orchestrator
- `/health` → Собственный health check

**НЕ зависит от:**
- Workers (они автономны)
- cluster-service (direct access)
- batch-service (direct access)

---

### Orchestrator (Django:8000)
```
Orchestrator
  ↓
PostgreSQL (:5432)  # Primary database
Redis (:6379)       # Celery queue
```

**Runtime зависимости:**
- **PostgreSQL** - КРИТИЧНО (primary database)
- **Redis** - КРИТИЧНО (Celery queue)

**Опциональные:**
- cluster-service - для cluster monitoring
- batch-service - для batch operations
- ClickHouse - для analytics (dev окружении)

**Django Apps:**
- `databases` - управление метаданными баз
- `operations` - выполнение операций
- `templates` - шаблонизация

---

### Celery Worker + Beat
```
Celery Worker/Beat
  ↓
Redis (:6379)       # Queue + result backend
PostgreSQL (:5432)  # Task state persistence
```

**Зависимости:**
- **Redis** - КРИТИЧНО (queue)
- **PostgreSQL** - для task results

**Enqueues tasks to:**
- Go Workers (через Redis queue)

---

### Go Worker (x2 replicas)
```
Go Worker
  ↓
Redis (:6379)       # Task queue
  ↓ OData
1C Bases (OData endpoints)
```

**Зависимости:**
- **Redis** - КРИТИЧНО (pull tasks)
- **1C Bases** - для выполнения операций

**Автономен от:**
- Orchestrator (workers don't call Django directly)
- API Gateway
- Frontend

**Connection pooling:**
- Max 3-5 connections per 1C база
- Connection timeout: 15s

---

### cluster-service (Go:8088)
```
cluster-service
  ↓ gRPC
ras-grpc-gw (:9999)
  ↓ Binary protocol
1C RAS (:1545)
```

**Зависимости:**
- **ras-grpc-gw** - КРИТИЧНО (gRPC gateway)
- **1C RAS Server** - для cluster metadata

**⚠️ ВАЖНО:** Запускать ПЕРВЫМ перед cluster-service!

**Startup order:**
1. ras-grpc-gw (должен быть готов)
2. cluster-service (подключается к gRPC)

**Integration:**
- Django может вызывать cluster-service для monitoring
- Но cluster-service НЕ зависит от Django

---

### batch-service (Go:8087)
```
batch-service
  ↓ subprocess
1cv8.exe (1C platform binary)
  ↓
1C Bases (file/server mode)
```

**Зависимости:**
- **1cv8.exe** - КРИТИЧНО (path в env var)
- **1C Bases** - для установки расширений

**Environment variables:**
```bash
EXE_1CV8_PATH="C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe"
V8_DEFAULT_TIMEOUT=300
```

**Автономен от:**
- Orchestrator
- Workers
- cluster-service

---

### ras-grpc-gw (External:9999)
```
ras-grpc-gw
  ↑ gRPC (cluster-service)
  ↓ Binary protocol
1C RAS (:1545)
```

**Зависимости:**
- **1C RAS Server** - КРИТИЧНО
- НЕ зависит от CommandCenter1C сервисов

**Repository:**
- `C:\1CProject\ras-grpc-gw` (форк v8platform/ras-grpc-gw)

**Startup command:**
```bash
cd ../ras-grpc-gw
go run cmd/main.go localhost:1545
```

---

## Build-time Dependencies

### Go Services → shared/

Все Go микросервисы используют shared пакеты:

```
api-gateway/
worker/          } → go-services/shared/
cluster-service/     ├── auth/
batch-service/       ├── config/
                     ├── logger/
                     ├── metrics/
                     └── models/
```

**Shared packages:**
- `auth/` - JWT validation
- `config/` - Config loading (env vars)
- `logger/` - Structured logging (zerolog)
- `metrics/` - Prometheus metrics
- `models/` - Shared data models

**Важно:**
- Изменения в `shared/` влияют на ВСЕ Go сервисы
- Требуется rebuild всех зависимых сервисов

---

## Data Flow Patterns

### User Operation Flow (Write Path)

```
1. User clicks "Execute Operation" in Frontend
   ↓ HTTP POST /api/operations/execute
2. API Gateway (JWT validation, rate limiting)
   ↓ Proxy request
3. Orchestrator (Django)
   - Validate operation parameters
   - Save OperationHistory
   - Enqueue Celery task
   ↓ Redis
4. Celery Worker picks up task
   - Render template
   - Enqueue Go Worker tasks
   ↓ Redis queue
5. Go Worker (x2 replicas)
   - Pull task from queue
   - Execute via OData
   ↓ OData HTTP
6. 1C Base processes request
   ↓ Result
7. Go Worker updates task status
   ↓ Redis/PostgreSQL
8. Frontend polls for result
   ↓ WebSocket/Polling
9. User sees result
```

### Cluster Monitoring Flow (Read Path)

```
1. User opens "Cluster Monitor" in Frontend
   ↓ HTTP GET /api/clusters
2. API Gateway (JWT validation)
   ↓ Proxy
3. Orchestrator (Django)
   ↓ HTTP
4. cluster-service
   ↓ gRPC
5. ras-grpc-gw
   ↓ Binary protocol
6. 1C RAS Server
   ↓ Cluster metadata
7. Response bubbles back to Frontend
```

### Health Check Flow

```
1. User runs ./scripts/dev/health-check.sh
   ↓ Parallel HTTP requests
2. API Gateway /health → OK
   Orchestrator /health → OK
   cluster-service /health → OK
   batch-service /health → OK
   Frontend / → OK
   ↓
3. Script reports status for all
```

---

## Critical Paths (Должны работать всегда)

### Path 1: Basic Operation Execution

**Services required:**
1. PostgreSQL (database)
2. Redis (queue)
3. Orchestrator (Django)
4. API Gateway (routing)
5. Celery Worker (task processing)
6. Go Worker (OData execution)
7. Frontend (UI)

**Если любой отвалится:**
- Operation execution fails
- User видит error

---

### Path 2: Cluster Monitoring

**Services required:**
1. ras-grpc-gw (gRPC gateway)
2. cluster-service (API)
3. API Gateway (optional, если direct access)
4. Frontend (UI)

**Если ras-grpc-gw отвалится:**
- Cluster monitoring unavailable
- Operations продолжают работать (independent)

---

## Failure Scenarios

### Scenario 1: Redis Down

**Impact:**
- ❌ Task queue не работает
- ❌ Celery tasks не enqueue
- ❌ Go Workers не получают tasks
- ✅ Health checks продолжают работать
- ✅ Database CRUD продолжает работать

**Mitigation:**
- Redis HA (Sentinel/Cluster)
- Fallback to synchronous execution (для critical operations)

---

### Scenario 2: PostgreSQL Down

**Impact:**
- ❌ Orchestrator не работает
- ❌ Task results не сохраняются
- ❌ Database metadata недоступна
- ❌ ВСЕ операции остановлены

**Mitigation:**
- PostgreSQL HA (Streaming Replication)
- Regular backups
- Read replicas для read-only queries

---

### Scenario 3: 1C Base Unavailable

**Impact:**
- ❌ Operations на эту базу fail
- ✅ Operations на другие базы продолжают работать
- ✅ Система продолжает функционировать

**Mitigation:**
- Retry logic (exponential backoff)
- Mark база as "unhealthy"
- Alert admin

---

### Scenario 4: ras-grpc-gw Down

**Impact:**
- ❌ Cluster monitoring недоступен
- ✅ Operations продолжают работать (через OData)
- ✅ Система полностью функциональна

**Mitigation:**
- Restart ras-grpc-gw
- Cluster monitoring опциональный feature

---

## Startup Order (Critical!)

**Правильная последовательность:**

1. **Infrastructure** (если не запущено):
   ```bash
   docker-compose -f docker-compose.local.yml up -d postgres redis
   ```

2. **ras-grpc-gw** (ПЕРВЫМ для cluster monitoring):
   ```bash
   cd ../ras-grpc-gw
   go run cmd/main.go localhost:1545
   # Подождать 3-5 секунд
   ```

3. **cluster-service** (зависит от ras-grpc-gw):
   ```bash
   cd go-services/cluster-service
   go run cmd/main.go
   ```

4. **batch-service** (независим):
   ```bash
   cd go-services/batch-service
   go run cmd/main.go
   ```

5. **Остальные сервисы** (порядок не критичен):
   ```bash
   ./scripts/dev/start-all.sh
   ```

**Проверка:**
```bash
./scripts/dev/health-check.sh
```

---

## Port Allocation

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| **Frontend** | 5173 | HTTP | React dev server |
| **API Gateway** | 8080 | HTTP | Main API endpoint |
| **Orchestrator** | 8000 | HTTP | Django app |
| **cluster-service** | 8088 | HTTP | Cluster monitoring API |
| **batch-service** | 8087 | HTTP | Batch operations API |
| **ras-grpc-gw** | 9999 | gRPC | RAS gRPC gateway |
| **ras-grpc-gw** | 8081 | HTTP | Health check |
| **PostgreSQL** | 5432 | PostgreSQL | Primary database |
| **Redis** | 6379 | Redis | Queue + cache |
| **ClickHouse HTTP** | 8123 | HTTP | Analytics queries |
| **ClickHouse Native** | 9000 | ClickHouse | Native protocol |
| **Grafana** | 3001 | HTTP | Dashboards |
| **Prometheus** | 9090 | HTTP | Metrics |

---

## См. также

- `monorepo-structure.md` - Детальная структура файлов
- `docs/LOCAL_DEVELOPMENT_GUIDE.md` - Руководство по local development
- `CLAUDE.md` - Критичные сервисы и порядок запуска
