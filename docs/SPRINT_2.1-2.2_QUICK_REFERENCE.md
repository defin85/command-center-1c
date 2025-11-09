# Sprint 2.1-2.2 Quick Reference

**Версия:** 1.0
**Дата:** 2025-11-09
**Для:** Coder
**Время чтения:** 3 минуты

---

## 🎯 Цель Sprint 2.1-2.2

Реализовать полную интеграцию **Django Orchestrator ↔ Go Worker** согласно Message Protocol v2.0.

**Deliverables:**
- ✅ Producer (Django/Celery): enqueue operations to Redis
- ✅ Consumer (Go Worker): process operations via OData
- ✅ Callback mechanism: results back to Django
- ✅ Idempotency, DLQ, Heartbeat

---

## 📦 Что уже есть (DONE)

### Django (Track 2A)
- ✅ **Models:** `BatchOperation`, `Task` - полные
- ✅ **Database Model:** `Database` с encrypted credentials
- ✅ **Celery Config:** базовая настройка
- ✅ **OData Client:** работает

### Go (Track 2B)
- ✅ **Basic models:** `operation.go` (устарело, нужно обновить)
- ✅ **Redis Queue:** `redis.go` (частично работает)
- ✅ **Worker Pool:** `pool.go` (базовая структура)

---

## 🛠️ Что нужно сделать

### Track 2A: Django/Celery Producer (6 tasks)

| Task | Файл | Описание | Сложность |
|------|------|----------|-----------|
| **2A.1** | `config/celery.py` | Queue routing + retry policy | ⭐ Easy |
| **2A.2** | `config/settings/base.py` | Redis queue constants | ⭐ Easy |
| **2A.3** | `apps/operations/redis_client.py` (new) | Redis wrapper | ⭐⭐ Medium |
| **2A.4** | `apps/operations/tasks.py` | `enqueue_operation()` task | ⭐⭐⭐ Hard |
| **2A.5** | `apps/operations/views.py` | Callback endpoint | ⭐⭐ Medium |
| **2A.6** | `apps/databases/views.py` | Credentials endpoint | ⭐⭐ Medium |

### Track 2B: Go Worker Consumer (5 tasks)

| Task | Файл | Описание | Сложность |
|------|------|----------|-----------|
| **2B.1** | `shared/models/operation_v2.go` (new) | v2.0 structs | ⭐⭐ Medium |
| **2B.2** | `worker/internal/credentials/client.go` (new) | Fetch credentials | ⭐⭐ Medium |
| **2B.3** | `worker/internal/queue/consumer.go` (new) | Main consumer loop | ⭐⭐⭐ Hard |
| **2B.4** | `worker/internal/processor/processor.go` | Process operations | ⭐⭐⭐ Hard |
| **2B.5** | `worker/cmd/main.go` | Wire everything | ⭐ Easy |

---

## 📋 Порядок выполнения

### Week 1: Foundation

**День 1-2: Django Setup**
1. 2A.1: Celery Config
2. 2A.2: Redis Constants
3. 2A.3: Redis Client

**День 3-4: Django Tasks**
4. 2A.4: `enqueue_operation()`
5. 2A.5: Callback Endpoint
6. 2A.6: Credentials Endpoint

**День 5-7: Go Foundation**
7. 2B.1: Models v2.0
8. 2B.2: Credentials Client

### Week 2: Integration

**День 8-10: Go Consumer**
9. 2B.3: Redis Consumer
10. 2B.4: Processor
11. 2B.5: Main.go

**День 11-14: Testing & Polish**
12. E2E Integration Tests
13. Load Testing
14. Bug Fixes

---

## 🔑 Key Decisions (Message Protocol v2.0)

| Решение | Значение | Обоснование |
|---------|----------|-------------|
| **Queue naming** | `cc1c:operations:v1` | Namespace pattern |
| **Redis structure** | Lists (LPUSH/BRPOP) | Простота + blocking ops |
| **Credentials** | Centralized (Django DB) | Security: НЕ передавать через Redis |
| **Cache TTL** | 2 минуты | Баланс security/performance |
| **Worker auth** | API Key (Phase 1) | Проще для internal service |
| **Timeout** | 15s → 30s → 60s | Progressive с exponential backoff |
| **DLQ retention** | 7 дней | Standard practice |
| **Heartbeat** | Redis key TTL 30s | Low overhead |
| **Idempotency** | Redis lock (1h → 24h) | At-most-once guarantee |

---

## 📊 Message Protocol v2.0 Schema

### Queue Message (Django → Redis)

```json
{
  "version": "2.0",
  "operation_id": "uuid",
  "operation_type": "create|update|delete|query",
  "entity": "Catalog_Users",
  "target_databases": ["db-uuid-1", "db-uuid-2"],
  "payload": {
    "data": {"Name": "Test User"},
    "filters": {},
    "options": {}
  },
  "execution_config": {
    "batch_size": 100,
    "timeout_seconds": 30,
    "retry_count": 3,
    "priority": "normal",
    "idempotency_key": "operation_id"
  },
  "metadata": {
    "created_by": "user-123",
    "created_at": "2025-11-09T12:00:00Z",
    "template_id": "uuid",
    "tags": []
  }
}
```

### Result Message (Worker → Django)

```json
{
  "operation_id": "uuid",
  "status": "completed|failed|timeout",
  "results": [
    {
      "database_id": "uuid",
      "success": true,
      "data": {...},
      "error": null,
      "duration_seconds": 2.5
    }
  ],
  "summary": {
    "total": 10,
    "succeeded": 8,
    "failed": 2,
    "avg_duration_seconds": 2.3
  },
  "worker_id": "worker-1"
}
```

---

## 🔗 Redis Keys

```
# Main queues
cc1c:operations:v1              # Pending tasks (LPUSH/BRPOP)
cc1c:operations:results:v1      # Results from workers
cc1c:operations:dlq:v1          # Dead Letter Queue (7 days retention)

# Idempotency
cc1c:task:{task_id}:lock        # Dedup lock (TTL 1h → 24h)

# Progress tracking
cc1c:task:{task_id}:progress    # Hash: {progress: 0-100, status}

# Worker heartbeat
cc1c:worker:{worker_id}:heartbeat  # JSON metadata (TTL 30s)
```

---

## 🧪 Testing Checklist

### Unit Tests

**Python:**
```bash
cd orchestrator
pytest apps/operations/tests/test_tasks.py -v
pytest apps/operations/tests/test_redis_client.py -v
pytest apps/operations/tests/test_views.py -v
```

**Go:**
```bash
cd go-services/worker
go test ./internal/credentials/... -v
go test ./internal/processor/... -v
go test ./internal/queue/... -v
```

### Integration Tests

- [ ] E2E flow: Django → Redis → Worker → Callback
- [ ] Idempotency: duplicate submissions rejected
- [ ] Timeout: tasks timeout after 30s
- [ ] DLQ: failed tasks move to DLQ after 3 retries
- [ ] Heartbeat: worker heartbeat visible in Redis

### Load Tests

```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

**Targets:**
- 20 users, 95% success, <10s p95

---

## ⚠️ Critical Constraints

1. **1C Transactions < 15 seconds** - КРИТИЧНО!
2. **Connection limits:** max 3-5 per база
3. **Worker pool:** 10-20 workers (Phase 1)
4. **Rate limiting:** 100 req/min per user
5. **700+ баз** - scalability критична

---

## 📖 Full Documentation

- **Детальный план:** [SPRINT_2.1-2.2_IMPLEMENTATION_PLAN.md](SPRINT_2.1-2.2_IMPLEMENTATION_PLAN.md) (80KB)
- **Message Protocol:** [MESSAGE_PROTOCOL_FINALIZED.md](MESSAGE_PROTOCOL_FINALIZED.md) (1300 строк)
- **Quick Summary:** [MESSAGE_PROTOCOL_SUMMARY.md](MESSAGE_PROTOCOL_SUMMARY.md)

---

## 🚀 Quick Start для Coder

```bash
# 1. Checkout worktree
cd /c/1CProject/command-center-1c-track2
git status  # должен быть: feature/track2-orchestrator-worker-integration

# 2. Start dependencies
docker-compose -f docker-compose.local.yml up -d postgres redis

# 3. Start Django (для тестирования endpoints)
cd orchestrator
source venv/Scripts/activate
python manage.py runserver

# 4. Start Celery (для тестирования tasks)
celery -A config worker -l info

# 5. Start Go Worker (после реализации)
cd go-services/worker
go run cmd/main.go
```

---

**Ready to code!** 🎉

Начинай с Task 2A.1 и следуй порядку в [Implementation Plan](SPRINT_2.1-2.2_IMPLEMENTATION_PLAN.md).
