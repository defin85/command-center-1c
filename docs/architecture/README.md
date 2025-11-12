# Architecture Documentation

Архитектурная документация проекта CommandCenter1C.

---

## Быстрый доступ

### Ключевые решения

| Документ | Описание | Дата | Статус |
|----------|----------|------|--------|
| **[MESSAGE_BROKER_DECISION.md](MESSAGE_BROKER_DECISION.md)** | Redis vs RabbitMQ - Executive Decision | 2025-11-12 | ✅ APPROVED |
| **[REDIS_VS_RABBITMQ_COMPARISON.md](REDIS_VS_RABBITMQ_COMPARISON.md)** | Детальное сравнение (40+ стр) | 2025-11-12 | ✅ FINAL |

### Визуализации

| Документ | Описание | Дата |
|----------|----------|------|
| **[diagrams/REDIS_VS_RABBITMQ_ARCHITECTURES.md](diagrams/REDIS_VS_RABBITMQ_ARCHITECTURES.md)** | Архитектурные диаграммы для всех вариантов | 2025-11-12 |

---

## Структура директории

```
architecture/
├── README.md                              ← Вы здесь
├── MESSAGE_BROKER_DECISION.md             ← Краткое решение (TL;DR)
├── REDIS_VS_RABBITMQ_COMPARISON.md        ← Детальный анализ (40+ стр)
└── diagrams/
    └── REDIS_VS_RABBITMQ_ARCHITECTURES.md ← Визуальные диаграммы
```

---

## Основные архитектурные решения

### 1. Message Broker: Redis (Phase 1-2)

**Решение:** Используем Redis Lists (текущая реализация) для Phase 1-2

**Обоснование:**
- ✅ Уже реализовано (Message Protocol v2.0 finalized)
- ✅ Покрывает 95% use cases для 700 databases
- ✅ Простота = меньше точек отказа
- ✅ 0 дней effort (vs 5-7 дней для RabbitMQ)

**Когда пересмотреть:**
- Phase 2: Redis Streams (IF need better guarantees)
- Phase 3+: RabbitMQ (IF scale > 1000 databases OR multi-tenant)

**См.:**
- [MESSAGE_BROKER_DECISION.md](MESSAGE_BROKER_DECISION.md) - краткое резюме
- [REDIS_VS_RABBITMQ_COMPARISON.md](REDIS_VS_RABBITMQ_COMPARISON.md) - полный анализ

---

### 2. Event-Driven Architecture (Future)

**Статус:** Планируется для Phase 2+

**Current State:**
- Redis Lists для task queues (operations)
- Redis Pub/Sub для real-time progress updates
- HTTP calls между сервисами (worker → cluster-service)

**Future (Phase 2+):**
- Redis Streams для workflow events (optional upgrade)
- Event-driven coordination для complex workflows (extension install)

**Triggers для upgrade:**
- Audit log requirements
- Complex multi-service workflows
- At-least-once delivery критично

---

## Как читать эту документацию

### Если нужен quick answer:
1. Открой [MESSAGE_BROKER_DECISION.md](MESSAGE_BROKER_DECISION.md)
2. Читай секцию "TL;DR" (первые 2 страницы)

### Если нужно обоснование:
1. Открой [REDIS_VS_RABBITMQ_COMPARISON.md](REDIS_VS_RABBITMQ_COMPARISON.md)
2. Читай секции:
   - Executive Summary
   - Technical Comparison
   - Recommendation

### Если нужны визуализации:
1. Открой [diagrams/REDIS_VS_RABBITMQ_ARCHITECTURES.md](diagrams/REDIS_VS_RABBITMQ_ARCHITECTURES.md)
2. Смотри диаграммы для каждого варианта

### Если нужны детали реализации:
1. Открой [REDIS_VS_RABBITMQ_COMPARISON.md](REDIS_VS_RABBITMQ_COMPARISON.md)
2. Читай секции:
   - Architecture Options (detailed code samples)
   - Migration Path (step-by-step)
   - Effort Estimation

---

## Контекст принятия решений

### Текущее состояние проекта

**Phase 1 Progress:** ~45-50% готово (Week 2.5-3)

**Реализовано:**
- ✅ Infrastructure (Docker, Redis, PostgreSQL)
- ✅ Database models (Django ORM)
- ✅ OData client (Python)
- ✅ REST API (Django DRF)
- ✅ RAS integration (gRPC)
- ✅ Message Protocol v2.0 (Redis Lists)

**В процессе:**
- 🟡 Celery → Worker integration (30% готово)
- 🟡 Template Engine (20% готово)
- ❌ End-to-End workflow (TODO)

**Масштаб:**
- 700 databases
- ~1000-2000 operations/day (estimated)
- 10-20 parallel workers (Phase 1)

### Почему этот анализ сделан сейчас?

**Вопрос пользователя:** "Сравни Redis и RabbitMQ для event-driven workflow установки расширений"

**Контекст:** Выбираем Message Broker для реализации event-driven подхода в Phase 2+

**Проблема:** Worker делает HTTP calls к другим сервисам (coupled architecture) → нужен переход к event-driven

**Решение:** Comprehensive анализ Redis vs RabbitMQ с учетом:
- Текущей реализации (Redis Lists уже работает)
- Use cases проекта (extension install workflow)
- Масштаба (700 databases)
- Команды (знают Redis, НЕ знают RabbitMQ)
- Pragmatic подход (не переусложнять преждевременно)

---

## Следующие шаги

### Phase 1-2: Продолжаем с Redis Lists
1. ✅ Message Protocol v2.0 - finalized
2. ❌ Завершить Celery → Worker integration (критично)
3. ❌ Завершить Template Engine (критично)
4. ❌ End-to-End testing (operations → worker → 1C)

### Phase 2 (Optional): Upgrade to Redis Streams
**Только если появятся triggers:**
- Audit log requirements
- At-least-once delivery критично
- Message replay нужен

**Effort:** 1-2 дня (см. Migration Path в детальном документе)

### Phase 3+ (Future): Consider RabbitMQ
**Только если появятся triggers:**
- > 1000 databases (scale вырос 2x)
- Multi-tenant SaaS
- Complex routing (10+ event types)
- Compliance audit (retention > 30 days)

**Effort:** 2 недели (см. Effort Estimation в детальном документе)

---

## FAQ

**Q: Почему не RabbitMQ сразу?**
A: Redis Lists достаточно для 700 databases. RabbitMQ добавит 5-7 дней разработки + operational complexity БЕЗ ощутимых преимуществ для текущего масштаба.

**Q: А если Redis упадёт?**
A: Redis AOF (persist every 1s) + idempotency keys = приемлемый риск (max 1-5s message loss). RabbitMQ тоже НЕ даёт exactly-once.

**Q: Когда реально нужен RabbitMQ?**
A: Phase 3+ при появлении real triggers (multi-tenant, complex routing, scale > 1000 databases). До тех пор - YAGNI.

**Q: А Kafka?**
A: Kafka для event streaming (log aggregation, analytics). Для task queues - overkill. См. industry best practices в детальном документе.

**Q: Можно ли мигрировать Redis → RabbitMQ потом?**
A: Да, см. Migration Path в [REDIS_VS_RABBITMQ_COMPARISON.md](REDIS_VS_RABBITMQ_COMPARISON.md). Estimated effort: 2 недели.

---

## Авторы

**AI Architect Team**
- Дата: 2025-11-12
- Контекст: Phase 1 (Week 2.5-3), Message Broker selection

---

## Changelog

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2025-11-12 | 1.0 | Создан comprehensive анализ Redis vs RabbitMQ (3 документа: decision, comparison, diagrams) |

---

**См. также:**
- [../ROADMAP.md](../ROADMAP.md) - Overall project roadmap
- [../MESSAGE_PROTOCOL_FINALIZED.md](../MESSAGE_PROTOCOL_FINALIZED.md) - Current protocol (Redis Lists)
- [../START_HERE.md](../START_HERE.md) - Project quickstart
