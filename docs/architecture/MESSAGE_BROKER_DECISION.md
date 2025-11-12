# Message Broker Decision: Redis vs RabbitMQ

**TL;DR:** Используй Redis (текущая реализация достаточна для Phase 1-2)

---

## Быстрые факты

| Критерий | Redis Lists | RabbitMQ | Победитель |
|----------|-------------|----------|------------|
| **Уже работает** | ✅ Да (Protocol v2.0) | ❌ Нет | **Redis** |
| **Effort для внедрения** | 0 дней | 5-7 дней | **Redis** |
| **Команда знает** | ✅ Да | ❌ Нет | **Redis** |
| **Достаточно для 700 баз** | ✅ Да | ✅ Да (overkill) | **Redis** |
| **Delivery guarantees** | ⚠️ At-most-once | ✅ At-least-once | RabbitMQ |
| **Complex routing** | ⚠️ Manual | ✅ Native | RabbitMQ |
| **Operational complexity** | ✅ Низкая | ⚠️ Высокая | **Redis** |

**Weighted Score:**
- Redis: **74.75/100**
- RabbitMQ: **80.25/100**

**НО:** Для нашего use case (700 баз, simple workflows) Redis **достаточен** (+0 days effort).

---

## Рекомендация

### Phase 1-2: Redis Lists (Current)
✅ **РЕКОМЕНДОВАНО**

**Почему:**
- Уже реализовано (Message Protocol v2.0 finalized)
- Покрывает 95% use cases
- Простота = меньше точек отказа
- Команда знает Redis (zero learning curve)
- 0 дней effort

**Limitations (acceptable):**
- At-most-once delivery (message loss risk при Redis crash)
- Manual Dead Letter Queue
- No complex routing

**Mitigation:**
- ✅ Redis AOF (persist every 1s)
- ✅ Idempotency keys (prevent duplicates)
- ✅ Manual DLQ implemented

---

### Phase 2: Redis Streams (Upgrade option)
⚠️ **OPTIONAL** (если появятся delivery guarantee requirements)

**When to consider:**
- Нужен audit log (replay messages)
- At-least-once delivery критично
- Consumer groups для scaling

**Effort:** 1-2 дня (90% code reuse)

**Changes:**
```python
# OLD (Lists):
redis.lpush("cc1c:operations:v1", message)

# NEW (Streams):
redis.xadd("operations", {"data": message}, maxlen=10000)
```

---

### Phase 3+: RabbitMQ
❌ **НЕ РЕКОМЕНДУЕТСЯ** для Phase 1-2

**When to consider (Phase 3+):**
- > 1000 databases (scale вырос 2x)
- Multi-tenant SaaS (priority по customer tier)
- Complex routing (10+ event types с разными consumers)
- Compliance audit (message retention > 30 days)

**Effort:** 5-7 дней + learning curve

**Cons:**
- Operational complexity (Erlang VM, clustering)
- New technology (team не знает AMQP)
- Overkill для simple task queue

---

## Decision Matrix

**Выбирай Redis Lists ЕСЛИ:**
- ✅ < 1000 databases
- ✅ Simple workflows
- ✅ Acceptable message loss risk (1-5s на Redis restart)
- ✅ Team familiar with Redis

**Выбирай Redis Streams ЕСЛИ:**
- ✅ Need audit log
- ✅ At-least-once delivery критично
- ✅ Consumer groups для scaling

**Выбирай RabbitMQ ЕСЛИ:**
- ✅ > 1000 databases
- ✅ Complex routing requirements
- ✅ Zero message loss requirement
- ✅ Multi-tenant architecture

---

## Pragmatic Approach

**Phase 1 (Weeks 1-6):** Redis Lists ✅
- Ship faster
- Proven architecture

**Phase 2 (Weeks 7-10):** Redis Streams (optional)
- IF delivery guarantees появились
- 1-2 дня migration

**Phase 3+ (Weeks 11+):** RabbitMQ (only if needed)
- ONLY IF real triggers:
  - Multi-tenant
  - Complex routing
  - Compliance audit > 30 days

---

## Industry Validation

**GitHub (Sidekiq):**
- Redis Lists для ~1M jobs/day
- Proven at scale

**Uber:**
- Redis Pub/Sub для real-time updates
- Kafka для event streaming

**Stripe:**
- RabbitMQ для payment workflows (financial transactions)

**CommandCenter1C:**
- NOT financial transactions → Redis acceptable
- 700 databases × 2 ops/day = 1400 ops/day (well within Redis capacity)

---

## Bottom Line

**НЕ переусложняйте преждевременно.**

Redis Lists достаточно для Phase 1-2. Upgrade when REAL NEED arises, not because "RabbitMQ is better."

**См. также:**
- [Полное сравнение](./REDIS_VS_RABBITMQ_COMPARISON.md) - 40+ страниц детального анализа
- [Message Protocol v2.0](../MESSAGE_PROTOCOL_FINALIZED.md) - финализированная спецификация

---

**Статус:** 🟢 APPROVED
**Дата:** 2025-11-12
**Next Review:** Phase 2 (Week 7)
