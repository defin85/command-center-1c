# Message Protocol v2.0 - Quick Reference

**Версия:** 2.0 (PRODUCTION READY)
**Дата:** 2025-11-09
**Статус:** ✅ ГОТОВ К РЕАЛИЗАЦИИ

---

## 🎯 Финальные решения

Все 7 открытых вопросов решены и утверждены:

| # | Вопрос | Решение | Обоснование |
|---|--------|---------|-------------|
| 1 | **Queue naming** | `cc1c:operations:v1` | Namespace pattern (сервис:тип:версия) |
| 2 | **Redis structure** | **Redis Lists** (LPUSH/BRPOP) | Простота + blocking ops |
| 3 | **Credentials** | **Centralized** (Django DB) + fetch by ID | Security: НЕ передавать через Redis |
| 4 | **Credential caching** | **2 минуты TTL** | Баланс security/performance |
| 5 | **Worker auth** | **API Key** (Phase 1) | Проще для internal service |
| 6 | **Timeout** | **Progressive** 15s → 30s → 60s | Exponential backoff |
| 7 | **Dead Letter Queue** | Dedicated DLQ + **7 дней retention** | Standard practice |
| 8 | **Heartbeat** | Redis key TTL (30s) | Low overhead |
| 9 | **Idempotency** | Operation ID + Redis lock | At-most-once guarantee |
| 10 | **Priority queues** | **Отложить на Phase 2** | YAGNI - сначала базовая функция |

---

## 📡 Message Schema v2.0

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

---

## 🔑 Redis Keys

```
# Main queues
cc1c:operations:v1              # Pending tasks (LPUSH/BRPOP)
cc1c:operations:results:v1      # Results from workers
cc1c:operations:dlq:v1          # Dead Letter Queue (7 days retention)

# Idempotency
cc1c:task:{task_id}:lock        # Dedup lock (TTL 1h → 24h)

# Progress tracking
cc1c:task:{task_id}:progress    # Hash: {progress: 0-100, status, updated_at}

# Worker heartbeat
cc1c:worker:{worker_id}:heartbeat  # JSON metadata (TTL 30s)
```

---

## 🔄 Flow

```
1. Django Orchestrator:
   - Проверить idempotency lock (Redis)
   - Собрать message (v2.0 schema)
   - LPUSH cc1c:operations:v1

2. Go Worker:
   - BRPOP cc1c:operations:v1 (blocking, 5s timeout)
   - Проверить lock (double-check)
   - Fetch credentials: GET /api/v1/databases/{id}/credentials
     (Cache: 2 min TTL, Auth: API Key)
   - Execute operation (timeout: 30s)
   - Update heartbeat every 10s
   - LPUSH result → cc1c:operations:results:v1

3. Django Callback Handler:
   - Read results from cc1c:operations:results:v1
   - Update operation status
   - Update tasks
   - WebSocket → Frontend (real-time progress)

4. Failed tasks:
   - Retry 3x (exponential backoff: 2s → 4s → 8s)
   - After 3 retries → LPUSH cc1c:operations:dlq:v1
   - DLQ retention: 7 days
```

---

## ⏱️ Timeouts

```
1C transaction:  15s (HARD LIMIT - cannot exceed)
Worker task:     30s (включая network overhead)
Celery task:     60s (monitoring + retry logic)

Retry backoff:
  Retry 1: 2s
  Retry 2: 4s
  Retry 3: 8s
  → DLQ (7 days retention)
```

---

## 🔒 Security

**Credentials:**
- ❌ НЕ передавать в message (security risk!)
- ✅ Centralized store (Django DB, encrypted)
- ✅ Worker fetch по ID: `/api/v1/databases/{id}/credentials`
- ✅ Cache: 2 min TTL (баланс security/performance)

**Worker Authentication:**
- Phase 1: **API Key** (simple, internal service-to-service)
- Phase 2: Можно мигрировать на JWT (если нужен granular access)

**Idempotency:**
- Redis lock: `cc1c:task:{operation_id}:lock`
- TTL: 1 hour (processing) → 24 hours (completed)
- Guarantee: at-most-once execution

---

## 📊 Monitoring

**Prometheus Metrics:**
```
cc1c_queue_depth{queue="operations"}      # Pending tasks
cc1c_queue_depth{queue="dlq"}             # DLQ size
cc1c_workers_active                       # Alive workers
cc1c_worker_task_duration_seconds         # Histogram
cc1c_worker_task_total{status="completed|failed"}
```

**Grafana Alerts:**
- DLQ size > 10 (5 min)
- No active workers (1 min)
- Failure rate > 10% (5 min)

---

## 📅 Implementation Timeline

**Phase 1 (Week 1): Foundation**
- Redis queue producer (Django)
- Redis queue consumer (Go)
- Message serialization

**Phase 2 (Week 2): Integration**
- Callback endpoint
- Credential fetch API
- Heartbeat mechanism

**Phase 3 (Week 3): Reliability**
- Idempotency locks
- Dead Letter Queue
- Retry logic

**Phase 4 (Week 4): Testing & Monitoring**
- Integration tests (E2E)
- Prometheus metrics
- Load testing

---

## 🚀 Next Steps

1. ✅ Protocol finalized - ВСЕ решения утверждены
2. **Sprint 2.1** - начать реализацию (Week 1-2)
3. **Sprint 2.2** - Template Engine (параллельно)
4. **Integration testing** - E2E tests
5. **Production deployment**

---

## 📖 Документация

**Full spec:** [MESSAGE_PROTOCOL_FINALIZED.md](MESSAGE_PROTOCOL_FINALIZED.md) (1300+ строк)

**Архив:** [MESSAGE_PROTOCOL.md](MESSAGE_PROTOCOL.md) (DRAFT v1.0 - устарел)

---

**Версия:** 2.0
**Статус:** Production Ready
**Все решения утверждены:** 2025-11-09
