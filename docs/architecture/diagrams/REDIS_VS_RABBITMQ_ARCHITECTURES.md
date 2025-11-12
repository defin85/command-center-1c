# Redis vs RabbitMQ: Архитектурные диаграммы

**Сравнение архитектурных подходов для event-driven workflows**

---

## Option A: Redis Lists (Current Implementation)

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR LAYER                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Django/Celery                                           │   │
│  │  - enqueue_operation() task                              │   │
│  │  - Message Protocol v2.0 builder                         │   │
│  │  - Idempotency lock (Redis key)                          │   │
│  └────────────────┬─────────────────────────────────────────┘   │
│                   │ LPUSH (non-blocking)                        │
└───────────────────┼─────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         REDIS LAYER                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  cc1c:operations:v1          [Main Queue - Redis List]  │   │
│  │  ┌─────┬─────┬─────┬─────┬─────┐                        │   │
│  │  │ Op1 │ Op2 │ Op3 │ Op4 │ Op5 │  ← LPUSH (tail)        │   │
│  │  └─────┴─────┴─────┴─────┴─────┘                        │   │
│  │                               ↑                           │   │
│  │                               └─ BRPOP (head, blocking)  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  cc1c:operations:dlq:v1      [Dead Letter Queue]        │   │
│  │  ┌────────┬────────┬────────┐                           │   │
│  │  │ Failed1│ Failed2│ Failed3│  ← Manual push on max retry│  │
│  │  └────────┴────────┴────────┘                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Idempotency Locks                                       │   │
│  │  cc1c:task:<op_id>:lock  →  TTL: 1 hour                 │   │
│  │  (Prevent duplicate execution)                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────┬─────────────────────────────────────────────┘
                    │ BRPOP (blocking pop, 5s timeout)
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         WORKER LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Go Worker #1 │  │ Go Worker #2 │  │ Go Worker #N │          │
│  │              │  │              │  │              │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │ Consumer │ │  │ │ Consumer │ │  │ │ Consumer │ │          │
│  │ │  Loop    │ │  │ │  Loop    │ │  │ │  Loop    │ │          │
│  │ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │          │
│  │      │       │  │      │       │  │      │       │          │
│  │      ▼       │  │      ▼       │  │      ▼       │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │Processor │ │  │ │Processor │ │  │ │Processor │ │          │
│  │ │(OData)   │ │  │ │(OData)   │ │  │ │(OData)   │ │          │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  Load Balancing: Native (BRPOP = first-come-first-serve)       │
│  Scaling: Horizontal (add more workers → all read same queue)  │
└──────────────────────────────────────────────────────────────────┘

CHARACTERISTICS:
  ✅ Simple architecture (1 queue, multiple workers)
  ✅ Low latency (in-memory operations)
  ⚠️ At-most-once delivery (message removed on BRPOP)
  ⚠️ No ACK mechanism (if worker crashes → message lost)
  ✅ Idempotency locks mitigate duplicate execution
  ⚠️ Manual DLQ implementation
```

---

## Option B: Redis Streams (Upgrade Path)

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR LAYER                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Django/Celery                                           │   │
│  │  - enqueue_operation_v2() task                           │   │
│  │  - XADD to stream                                        │   │
│  └────────────────┬─────────────────────────────────────────┘   │
│                   │ XADD (append to stream)                     │
└───────────────────┼─────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                       REDIS STREAMS LAYER                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Stream: cc1c:operations:stream:v1                       │   │
│  │                                                           │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │ Entry 1  │ Entry 2  │ Entry 3  │ Entry 4  │ ... │    │   │
│  │  │ 12345-0  │ 12346-0  │ 12347-0  │ 12348-0  │     │    │   │
│  │  │ {data}   │ {data}   │ {data}   │ {data}   │     │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  │                                                           │   │
│  │  MAXLEN: ~10000 (approximate, for performance)           │   │
│  │  Retention: Auto-trim old entries                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Consumer Group: worker-group                            │   │
│  │                                                           │   │
│  │  Consumers:                                              │   │
│  │  - worker-1  (last_id: 12347-0)                          │   │
│  │  - worker-2  (last_id: 12346-0)                          │   │
│  │  - worker-N  (last_id: 12345-0)                          │   │
│  │                                                           │   │
│  │  Pending List (XPENDING):                                │   │
│  │  ┌────────────────────────────────────────────┐          │   │
│  │  │ 12345-0  │ worker-1 │ idle: 2m │ retry: 1 │          │   │
│  │  │ 12348-0  │ worker-3 │ idle: 5m │ retry: 0 │          │   │
│  │  └────────────────────────────────────────────┘          │   │
│  │  (Messages not yet ACKed → retry after 5min idle)       │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────┬─────────────────────────────────────────────┘
                    │ XREADGROUP (blocking read, consumer groups)
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         WORKER LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Go Worker #1 │  │ Go Worker #2 │  │ Go Worker #N │          │
│  │              │  │              │  │              │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │XREADGROUP│ │  │ │XREADGROUP│ │  │ │XREADGROUP│ │          │
│  │ │ (block)  │ │  │ │ (block)  │ │  │ │ (block)  │ │          │
│  │ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │          │
│  │      │       │  │      │       │  │      │       │          │
│  │      ▼       │  │      ▼       │  │      ▼       │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │ Process  │ │  │ │ Process  │ │  │ │ Process  │ │          │
│  │ │ Message  │ │  │ │ Message  │ │  │ │ Message  │ │          │
│  │ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │          │
│  │      │       │  │      │       │  │      │       │          │
│  │      ▼       │  │      ▼       │  │      ▼       │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │   XACK   │ │  │ │   XACK   │ │  │ │   XACK   │ │          │
│  │ │(on success)│ │ │(on success)│ │ │(on success)│ │          │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Retry Worker (separate goroutine)                      │   │
│  │  - Every 1 minute: XPENDING → claim idle messages       │   │
│  │  - Retry messages idle > 5 minutes                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Load Balancing: Consumer Groups (Redis manages distribution)  │
│  Scaling: Horizontal (add worker → joins consumer group)       │
└──────────────────────────────────────────────────────────────────┘

CHARACTERISTICS:
  ✅ At-least-once delivery (XACK mechanism)
  ✅ Message persistence (survive Redis restart)
  ✅ Consumer groups (automatic load balancing)
  ✅ Automatic retry (XPENDING + claim)
  ✅ Audit log (can replay messages with XRANGE)
  ⚠️ Slightly more complex API (XADD, XREADGROUP, XACK)
  ⚠️ Memory overhead (~2x vs Lists due to metadata)
```

---

## Option C: RabbitMQ (Industrial-Grade Broker)

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR LAYER                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Django/Celery                                           │   │
│  │  - pika library (RabbitMQ Python client)                 │   │
│  │  - Publisher logic                                       │   │
│  └────────────────┬─────────────────────────────────────────┘   │
│                   │ Publish (AMQP protocol)                     │
│                   │ - Exchange: operations                       │
│                   │ - Routing Key: operations.install            │
│                   │ - Delivery Mode: 2 (persistent)              │
└───────────────────┼─────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                       RABBITMQ LAYER                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Exchange: operations (Topic Exchange)                   │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  Routing Logic:                                    │  │   │
│  │  │  - operations.install   → worker-operations queue  │  │   │
│  │  │  - operations.update    → worker-operations queue  │  │   │
│  │  │  - operations.priority  → priority-queue           │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Queue: worker-operations (Durable)                     │   │
│  │  ┌─────┬─────┬─────┬─────┬─────┐                        │   │
│  │  │ Op1 │ Op2 │ Op3 │ Op4 │ Op5 │                        │   │
│  │  └─────┴─────┴─────┴─────┴─────┘                        │   │
│  │                                                           │   │
│  │  Properties:                                             │   │
│  │  - Durable: true (survive broker restart)               │   │
│  │  - x-max-priority: 10 (priority levels)                 │   │
│  │  - x-dead-letter-exchange: operations-dlx               │   │
│  │  - x-message-ttl: 3600000 (1 hour)                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Dead Letter Exchange: operations-dlx (Fanout)          │   │
│  │  ↓                                                       │   │
│  │  Queue: operations-dlq                                  │   │
│  │  ┌────────┬────────┬────────┐                           │   │
│  │  │ Failed1│ Failed2│ Failed3│  ← Auto-routed on max retry│  │
│  │  └────────┴────────┴────────┘                           │   │
│  │  (Messages with x-death > 3 retries)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────┬─────────────────────────────────────────────┘
                    │ Consume (AMQP protocol)
                    │ - Manual ACK
                    │ - Prefetch: 1 (process one at a time)
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         WORKER LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Go Worker #1 │  │ Go Worker #2 │  │ Go Worker #N │          │
│  │              │  │              │  │              │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │ Consumer │ │  │ │ Consumer │ │  │ │ Consumer │ │          │
│  │ │ (AMQP)   │ │  │ │ (AMQP)   │ │  │ │ (AMQP)   │ │          │
│  │ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │          │
│  │      │       │  │      │       │  │      │       │          │
│  │      ▼       │  │      ▼       │  │      ▼       │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │ Process  │ │  │ │ Process  │ │  │ │ Process  │ │          │
│  │ │ Message  │ │  │ │ Message  │ │  │ │ Message  │ │          │
│  │ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │          │
│  │      │       │  │      │       │  │      │       │          │
│  │      ▼       │  │      ▼       │  │      ▼       │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │   ACK    │ │  │ │   ACK    │ │  │ │   ACK    │ │          │
│  │ │ (success)│ │  │ │ (success)│ │  │ │ (success)│ │          │
│  │ │          │ │  │ │          │ │  │ │          │ │          │
│  │ │   NACK   │ │  │ │   NACK   │ │  │ │   NACK   │ │          │
│  │ │ (failure)│ │  │ │ (failure)│ │  │ │ (failure)│ │          │
│  │ │ +requeue │ │  │ │ +requeue │ │  │ │ +requeue │ │          │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  Load Balancing: Native (RabbitMQ round-robin)                 │
│  Scaling: Horizontal (add worker → registers as consumer)      │
└──────────────────────────────────────────────────────────────────┘

CHARACTERISTICS:
  ✅ At-least-once delivery (publisher confirms + ACKs)
  ✅ Persistent queues + durable messages
  ✅ Native Dead Letter Exchange (automatic)
  ✅ Priority queues (1-255 levels)
  ✅ Complex routing (topic patterns, headers)
  ✅ Message TTL (per message/queue)
  ⚠️ Higher operational complexity (Erlang VM, clustering)
  ⚠️ Higher resource usage (~300-500MB vs Redis 100-200MB)
  ⚠️ Learning curve (AMQP protocol)
```

---

## Side-by-Side Comparison

```
┌───────────────────────┬─────────────────┬─────────────────┬─────────────────┐
│   Feature             │  Redis Lists    │  Redis Streams  │   RabbitMQ      │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Delivery Guarantee    │ At-most-once    │ At-least-once   │ At-least-once   │
│                       │ (message lost   │ (XACK)          │ (ACK/NACK)      │
│                       │  on BRPOP)      │                 │                 │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Message Persistence   │ ⚠️ Removed on   │ ✅ Yes          │ ✅ Yes          │
│                       │   read          │ (MAXLEN)        │ (durable queue) │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ ACK Mechanism         │ ❌ No           │ ✅ XACK         │ ✅ ACK/NACK     │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Dead Letter Queue     │ ⚠️ Manual       │ ⚠️ Manual       │ ✅ Native (DLX) │
│                       │ (separate queue)│ (XPENDING)      │                 │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Priority Queues       │ ⚠️ Manual       │ ⚠️ Manual       │ ✅ Native       │
│                       │ (multiple queues)│               │ (1-255 levels)  │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Complex Routing       │ ❌ No           │ ❌ No           │ ✅ Yes          │
│                       │                 │                 │ (exchanges)     │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Consumer Groups       │ ❌ No           │ ✅ Yes          │ ✅ Yes          │
│                       │                 │ (native)        │ (multiple       │
│                       │                 │                 │  consumers)     │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Message Replay        │ ❌ No           │ ✅ XRANGE       │ ⚠️ Limited      │
│                       │                 │ (audit log)     │ (plugin)        │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Latency               │ ✅ < 1ms        │ ✅ < 5ms        │ ⚠️ 10-50ms      │
│                       │ (in-memory)     │ (in-memory)     │ (AMQP overhead) │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Throughput            │ ✅ 100k+ msg/s  │ ✅ 80k+ msg/s   │ ⚠️ 10-50k msg/s │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Memory Footprint      │ ✅ Low          │ ⚠️ Medium       │ ⚠️ High         │
│                       │ (100-200MB)     │ (150-300MB)     │ (300-500MB)     │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Operational Complexity│ ✅ Low          │ ✅ Low          │ ⚠️ High         │
│                       │ (1 process)     │ (1 process)     │ (Erlang VM,     │
│                       │                 │                 │  clustering)    │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Learning Curve        │ ✅ Easy         │ ⚠️ Medium       │ ⚠️ High         │
│                       │ (simple API)    │ (XADD/XREAD)    │ (AMQP protocol) │
├───────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Migration Effort      │ ✅ 0 days       │ ⚠️ 1-2 days     │ ❌ 5-7 days     │
│                       │ (already done)  │ (90% reuse)     │ (new integration)│
└───────────────────────┴─────────────────┴─────────────────┴─────────────────┘

LEGEND:
  ✅ Excellent / Native support
  ⚠️ Acceptable / Manual implementation
  ❌ Not supported / High effort
```

---

## Migration Flow: Lists → Streams → RabbitMQ

```
PHASE 1 (Current)
┌─────────────────────┐
│   Redis Lists       │  ← You are here
│   (LPUSH/BRPOP)     │
│                     │
│   Status: ✅ DONE   │
│   Effort: 0 days    │
└─────────────────────┘
          │
          │ Optional upgrade (Phase 2)
          │ IF: need better guarantees
          ▼
PHASE 2 (Optional)
┌─────────────────────┐
│   Redis Streams     │
│   (XADD/XREADGROUP) │
│                     │
│   Status: ⏳ TODO   │
│   Effort: 1-2 days  │
│   Trigger:          │
│   - Audit log need  │
│   - At-least-once   │
└─────────────────────┘
          │
          │ Optional upgrade (Phase 3+)
          │ IF: scale > 1000 databases
          ▼
PHASE 3+ (Future)
┌─────────────────────┐
│   RabbitMQ          │
│   (AMQP/Exchanges)  │
│                     │
│   Status: ⏸️ HOLD   │
│   Effort: 5-7 days  │
│   Trigger:          │
│   - Multi-tenant    │
│   - Complex routing │
│   - Scale > 1000    │
└─────────────────────┘

RECOMMENDATION:
  → Stay on Redis Lists for Phase 1-2
  → Upgrade to Streams IF needed (low effort)
  → RabbitMQ ONLY if real triggers appear
```

---

## Use Case Fit

```
┌─────────────────────────────────────────────────────────────────┐
│                    USE CASE ANALYSIS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Extension Install Workflow (700 databases)                     │
│  ┌────────────┬────────────┬────────────┬─────────────────┐     │
│  │            │ Redis Lists│Redis Streams│   RabbitMQ     │     │
│  ├────────────┼────────────┼────────────┼─────────────────┤     │
│  │ Fit        │ ✅ Good    │ ✅ Better  │ ⚠️ Overkill    │     │
│  │ Effort     │ 0 days     │ 1-2 days   │ 5-7 days        │     │
│  │ Risk       │ Low        │ Low        │ Medium          │     │
│  └────────────┴────────────┴────────────┴─────────────────┘     │
│                                                                  │
│  Real-time Progress Updates                                     │
│  ┌────────────┬────────────┬────────────┬─────────────────┐     │
│  │            │ Pub/Sub    │ Streams    │   RabbitMQ     │     │
│  ├────────────┼────────────┼────────────┼─────────────────┤     │
│  │ Fit        │ ✅ Perfect │ ⚠️ Overkill│ ⚠️ Overkill    │     │
│  │ Latency    │ < 1ms      │ < 5ms      │ 10-50ms         │     │
│  │ Persistence│ ❌ No      │ ✅ Yes     │ ✅ Yes          │     │
│  │ Need?      │ ❌ No      │ ❌ No      │ ❌ No           │     │
│  └────────────┴────────────┴────────────┴─────────────────┘     │
│                                                                  │
│  Multi-Service Events (Phase 3+)                                │
│  ┌────────────┬────────────┬────────────┬─────────────────┐     │
│  │            │ Redis Lists│Redis Streams│   RabbitMQ     │     │
│  ├────────────┼────────────┼────────────┼─────────────────┤     │
│  │ Routing    │ ⚠️ Manual  │ ⚠️ Manual  │ ✅ Native      │     │
│  │ Complexity │ Low        │ Low        │ Medium          │     │
│  │ Recommended│ Phase 1-2  │ Phase 2    │ Phase 3+        │     │
│  └────────────┴────────────┴────────────┴─────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary

**For CommandCenter1C:**

1. **Phase 1-2 (Current):** Redis Lists ✅
   - Simple, proven, sufficient для 700 databases
   - 0 days effort (already implemented)

2. **Phase 2 (Optional Upgrade):** Redis Streams
   - IF need better guarantees OR audit log
   - 1-2 days migration (low risk)

3. **Phase 3+ (Future):** RabbitMQ
   - ONLY IF real triggers appear (multi-tenant, complex routing)
   - 5-7 days migration + operational complexity

**Bottom Line:** Don't over-engineer. Redis достаточно для текущего масштаба.

**См. также:**
- [Детальное сравнение](../REDIS_VS_RABBITMQ_COMPARISON.md)
- [Краткое решение](../MESSAGE_BROKER_DECISION.md)

---

**Дата:** 2025-11-12
**Версия:** 1.0
