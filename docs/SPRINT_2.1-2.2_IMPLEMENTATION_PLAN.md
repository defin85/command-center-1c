# Sprint 2.1-2.2 Implementation Plan

**Версия:** 1.0
**Дата:** 2025-11-09
**Статус:** 🟢 READY FOR IMPLEMENTATION
**Message Protocol:** v2.0 FINALIZED

---

## 📋 Оглавление

1. [Анализ текущего состояния](#1-анализ-текущего-состояния)
2. [Архитектурные решения](#2-архитектурные-решения)
3. [Пошаговый план реализации](#3-пошаговый-план-реализации)
4. [Порядок выполнения](#4-порядок-выполнения)
5. [Testing Strategy](#5-testing-strategy)
6. [Риски и митигация](#6-риски-и-митигация)

---

## 1. Анализ текущего состояния

### 1.1 Django Orchestrator (Track 2A)

**Что уже реализовано (✅):**

| Компонент | Файл | Статус | Готовность |
|-----------|------|--------|-----------|
| **Models** | `apps/operations/models.py` | ✅ Готово | 100% |
| - `BatchOperation` | ✅ | Полная модель с статусами, progress tracking | 100% |
| - `Task` | ✅ | Полная модель с retry logic, worker tracking | 100% |
| **Templates** | `apps/templates/models.py` | ✅ Готово | 100% |
| - `OperationTemplate` | ✅ | Базовая модель шаблонов | 100% |
| **Database Models** | `apps/databases/models.py` | ✅ Готово | 100% |
| - `Database` | ✅ | Encrypted credentials, health checks | 100% |
| - `Cluster` | ✅ | Cluster management | 100% |
| **Celery Config** | `config/celery.py` | ✅ Частично | 50% |
| - Basic config | ✅ | Базовая конфигурация работает | 100% |
| - Beat schedule | ✅ | Periodic tasks настроены | 100% |
| - **Queue routing** | ❌ | НЕТ queue routing для operations | 0% |
| - **Retry policy** | ❌ | НЕТ retry configuration | 0% |

**Что нужно доработать (⚠️):**

| Компонент | Файл | Что нужно | Готовность |
|-----------|------|-----------|-----------|
| **Tasks** | `apps/operations/tasks.py` | Полная переработка | 10% |
| - `enqueue_operation()` | ❌ | TODO stub, нужна полная реализация | 0% |
| - Idempotency locks | ❌ | Отсутствует | 0% |
| - DLQ handling | ❌ | Отсутствует | 0% |
| **Views/API** | `apps/operations/views.py` | Нужны новые endpoints | 30% |
| - Callback endpoint | ❌ | Отсутствует | 0% |
| - Credentials endpoint | ❌ | Отсутствует (есть в databases, нужен адаптер) | 0% |
| **Celery Config** | `config/celery.py` | Обновить под v2.0 protocol | 50% |
| - Queue config | ❌ | Нужна настройка `cc1c:operations:v1` | 0% |
| - Retry policy | ❌ | Exponential backoff | 0% |
| **Settings** | `config/settings/base.py` | Добавить новые настройки | 80% |
| - Redis queue keys | ❌ | Константы для queue naming | 0% |
| - Worker auth config | ❌ | API key для worker authentication | 0% |

**Что нужно создать с нуля (🆕):**

1. **Credentials API Adapter** (`apps/databases/views.py`)
   - Endpoint: `GET /api/v1/databases/{id}/credentials`
   - Worker authentication (API Key)
   - Credential decryption и возврат

2. **Operation Callback Handler** (`apps/operations/views.py`)
   - Endpoint: `POST /api/v1/operations/{id}/callback`
   - Result processing
   - Task status updates

3. **Celery Task: `enqueue_operation()`** (`apps/operations/tasks.py`)
   - Message building (v2.0 schema)
   - Idempotency check (Redis lock)
   - Queue push (`LPUSH cc1c:operations:v1`)
   - DLQ handling

4. **Redis Client Wrapper** (`apps/operations/redis_client.py`)
   - Централизованный Redis client
   - Queue operations (LPUSH, BRPOP)
   - Lock operations (SET NX EX)

### 1.2 Go Worker (Track 2B)

**Что уже реализовано (✅):**

| Компонент | Файл | Статус | Готовность |
|-----------|------|--------|-----------|
| **Models (OLD)** | `shared/models/operation.go` | ⚠️ Устарело | 30% |
| - Basic structs | ✅ | Есть, но НЕ соответствуют v2.0 | 30% |
| **Queue Consumer** | `worker/internal/queue/redis.go` | ⚠️ Частично | 40% |
| - Redis client | ✅ | Работает | 100% |
| - `DequeueTask()` | ✅ | BRPOP реализован | 80% |
| - `PublishResult()` | ✅ | LPUSH реализован | 80% |
| - **Heartbeat** | ❌ | Отсутствует | 0% |
| - **Idempotency check** | ❌ | Отсутствует | 0% |
| **Processor** | `worker/internal/processor/processor.go` | ⚠️ Stub | 20% |
| - Basic structure | ✅ | Есть | 50% |
| - **OData operations** | ❌ | TODO stubs | 0% |
| - **Error handling** | ❌ | Примитивная | 20% |
| **Worker Pool** | `worker/internal/pool/pool.go` | ✅ Частично | 60% |
| - Pool structure | ✅ | Работает | 80% |
| - **Graceful shutdown** | ⚠️ | Нужна доработка | 50% |

**Что нужно доработать (⚠️):**

| Компонент | Файл | Что нужно | Готовность |
|-----------|------|-----------|-----------|
| **Models** | `shared/models/operation.go` | Обновить до v2.0 | 30% |
| - `OperationMessage` | ❌ | Полностью переписать под v2.0 schema | 0% |
| - `OperationResult` | ❌ | Добавить поля из v2.0 | 30% |
| **Queue Consumer** | `worker/internal/queue/redis.go` | Добавить функционал | 40% |
| - Queue naming | ❌ | Обновить на `cc1c:operations:v1` | 0% |
| - Heartbeat | ❌ | Реализовать | 0% |
| - Progress tracking | ❌ | Реализовать | 0% |
| **Processor** | `worker/internal/processor/processor.go` | Полная переработка | 20% |
| - OData integration | ❌ | Подключить OData client | 0% |
| - Timeout handling | ❌ | Context with timeout | 0% |

**Что нужно создать с нуля (🆕):**

1. **Credentials Client** (`worker/internal/credentials/client.go`)
   - HTTP client для Orchestrator API
   - Credential caching (TTL 2 min)
   - Retry logic
   - Authentication (API Key)

2. **Models v2.0** (`shared/models/operation_v2.go`)
   - `OperationMessage` (полная v2.0 schema)
   - `OperationResult` (v2.0)
   - `DatabaseResult` (v2.0)
   - Validation functions

3. **Heartbeat Manager** (`worker/internal/heartbeat/manager.go`)
   - Heartbeat loop (10 sec interval)
   - Redis key with TTL (30 sec)
   - Metadata (worker_id, status, current_task)

4. **Result Publisher** (`worker/internal/publisher/publisher.go`)
   - Redis results queue (`cc1c:operations:results:v1`)
   - HTTP callback (fallback)

---

## 2. Архитектурные решения

### 2.1 Структура модулей

**Django Orchestrator:**

```
orchestrator/
├── apps/
│   ├── operations/
│   │   ├── models.py          # ✅ Готово
│   │   ├── tasks.py           # ⚠️ ДОРАБОТАТЬ (enqueue_operation)
│   │   ├── views.py           # 🆕 ДОБАВИТЬ callback endpoint
│   │   ├── redis_client.py    # 🆕 СОЗДАТЬ (централизованный Redis)
│   │   ├── serializers.py     # ✅ Готово
│   │   └── urls.py            # ⚠️ ОБНОВИТЬ (новые endpoints)
│   │
│   ├── databases/
│   │   ├── views.py           # 🆕 ДОБАВИТЬ credentials endpoint
│   │   ├── models.py          # ✅ Готово
│   │   └── ...
│   │
│   └── templates/
│       ├── models.py          # ✅ Готово (базовая модель)
│       └── ...                # 🆕 СОЗДАТЬ engine (Sprint 2.2)
│
├── config/
│   ├── celery.py              # ⚠️ ОБНОВИТЬ (queue config, retry)
│   └── settings/
│       └── base.py            # ⚠️ ДОБАВИТЬ queue constants
```

**Go Worker:**

```
go-services/
├── shared/
│   ├── models/
│   │   ├── operation.go       # ⚠️ УСТАРЕЛО
│   │   ├── operation_v2.go    # 🆕 СОЗДАТЬ (v2.0 protocol)
│   │   └── database.go        # ✅ Готово
│   │
│   └── ...
│
└── worker/
    ├── internal/
    │   ├── queue/
    │   │   ├── redis.go       # ⚠️ ДОРАБОТАТЬ (heartbeat, idempotency)
    │   │   └── consumer.go    # 🆕 СОЗДАТЬ (main consumer loop)
    │   │
    │   ├── processor/
    │   │   ├── processor.go   # ⚠️ ПЕРЕПИСАТЬ (OData integration)
    │   │   └── timeout.go     # 🆕 СОЗДАТЬ (timeout handling)
    │   │
    │   ├── credentials/
    │   │   └── client.go      # 🆕 СОЗДАТЬ (fetch credentials)
    │   │
    │   ├── heartbeat/
    │   │   └── manager.go     # 🆕 СОЗДАТЬ (heartbeat loop)
    │   │
    │   └── publisher/
    │       └── publisher.go   # 🆕 СОЗДАТЬ (result publishing)
    │
    └── cmd/
        └── main.go            # ⚠️ ОБНОВИТЬ (connect all components)
```

### 2.2 Зависимости между компонентами

**Django Side:**

```
User Request
    ↓
BatchOperation.create() (Django ORM)
    ↓
enqueue_operation.delay() (Celery task)
    ↓
RedisClient.lpush("cc1c:operations:v1", message) (Redis)
    ↓
Worker consumes (Go)
```

**Go Side:**

```
Consumer.Start() (main loop)
    ↓
Redis.BRPOP("cc1c:operations:v1") (blocking dequeue)
    ↓
Validator.Validate(message) (v2.0 schema)
    ↓
CredentialsClient.Fetch(database_id) (HTTP GET)
    ↓
Processor.Process(operation, credentials) (OData)
    ↓
Publisher.PublishResult(result) (Redis or HTTP callback)
```

### 2.3 Обработка ошибок

**Error Handling Strategy:**

| Ошибка | Retry? | Действие | DLQ? |
|--------|--------|----------|------|
| **Redis connection error** | ✅ Yes (3x) | Exponential backoff (2s → 4s → 8s) | ✅ After 3 retries |
| **Timeout (30s)** | ✅ Yes (3x) | Retry with same timeout | ✅ After 3 retries |
| **OData auth error** | ❌ No | Mark failed, NO retry | ✅ Immediate DLQ |
| **Invalid entity** | ❌ No | Mark failed, NO retry | ✅ Immediate DLQ |
| **Network error** | ✅ Yes (3x) | Exponential backoff | ✅ After 3 retries |
| **Unknown error** | ✅ Yes (3x) | Exponential backoff | ✅ After 3 retries |

**DLQ Flow:**

```python
# After 3 failed retries
def move_to_dlq(operation_id, error_metadata):
    dlq_message = {
        "original_message": {...},
        "failure_metadata": {
            "failed_at": timezone.now(),
            "failure_count": 3,
            "last_error": error_metadata["error"],
            "retry_history": [...]
        }
    }

    # Push to DLQ
    redis.lpush("cc1c:operations:dlq:v1", json.dumps(dlq_message))

    # Set metadata with TTL 7 days
    redis.hset(f"cc1c:task:{operation_id}:dlq_meta", dlq_message)
    redis.expire(f"cc1c:task:{operation_id}:dlq_meta", 7 * 24 * 60 * 60)
```

### 2.4 Logging Strategy

**Python Logging:**

```python
import logging
logger = logging.getLogger(__name__)

# Structured logging with context
logger.info(
    "Enqueuing operation",
    extra={
        "operation_id": operation.id,
        "operation_type": operation.operation_type,
        "target_databases_count": operation.target_databases.count(),
        "user": request.user.username
    }
)
```

**Go Logging:**

```go
import "go.uber.org/zap"

logger.Info("Processing operation",
    zap.String("operation_id", msg.OperationID),
    zap.String("type", msg.OperationType),
    zap.Int("databases", len(msg.TargetDatabases)),
    zap.String("worker_id", workerID),
)
```

---

## 3. Пошаговый план реализации

### Track 2A: Django/Celery Producer (Python)

---

#### Task 2A.1: Обновить Celery Configuration

**Файл:** `orchestrator/config/celery.py`

**Описание:**
Добавить queue routing, retry policy и DLQ configuration для Message Protocol v2.0.

**Изменения:**

```python
# config/celery.py

# Queue Configuration
app.conf.task_routes = {
    'apps.operations.tasks.enqueue_operation': {
        'queue': 'operations',
        'routing_key': 'operations.enqueue',
    },
}

# Retry Configuration
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True
app.conf.worker_prefetch_multiplier = 1  # Fair task distribution

# Default retry policy
app.conf.task_default_retry_delay = 2  # seconds
app.conf.task_max_retries = 3

# Timeouts (seconds)
app.conf.task_soft_time_limit = 60  # Graceful timeout
app.conf.task_time_limit = 70        # Hard timeout
```

**Зависимости:**
- Django settings (`config/settings/base.py`)

**Тестирование:**
```bash
cd orchestrator
python manage.py shell
>>> from config.celery import app
>>> app.conf.task_routes
{'apps.operations.tasks.enqueue_operation': {'queue': 'operations'}}
```

**Acceptance Criteria:**
- ✅ Queue routing настроен
- ✅ Retry policy работает (exponential backoff)
- ✅ Timeouts установлены

---

#### Task 2A.2: Добавить Redis Queue Constants

**Файл:** `orchestrator/config/settings/base.py`

**Описание:**
Добавить константы для Redis queue naming согласно v2.0 protocol.

**Изменения:**

```python
# config/settings/base.py

# Redis Queue Configuration (Message Protocol v2.0)
REDIS_QUEUE_OPERATIONS = "cc1c:operations:v1"
REDIS_QUEUE_RESULTS = "cc1c:operations:results:v1"
REDIS_QUEUE_DLQ = "cc1c:operations:dlq:v1"

# Idempotency & Heartbeat
REDIS_KEY_TASK_LOCK = "cc1c:task:{task_id}:lock"
REDIS_KEY_TASK_PROGRESS = "cc1c:task:{task_id}:progress"
REDIS_KEY_WORKER_HEARTBEAT = "cc1c:worker:{worker_id}:heartbeat"

# Worker Authentication
WORKER_API_KEY = env('WORKER_API_KEY', default='dev-worker-key-change-in-production')

# DLQ Retention
DLQ_RETENTION_DAYS = 7
```

**Зависимости:**
- Нет

**Тестирование:**
```bash
python manage.py shell
>>> from django.conf import settings
>>> settings.REDIS_QUEUE_OPERATIONS
'cc1c:operations:v1'
```

**Acceptance Criteria:**
- ✅ Все queue constants определены
- ✅ Worker API key настроен

---

#### Task 2A.3: Создать Redis Client Wrapper

**Файл:** `orchestrator/apps/operations/redis_client.py` (новый)

**Описание:**
Централизованный Redis client с операциями для queue, locks, progress.

**Код:**

```python
"""Centralized Redis client for operations app."""
import redis
import json
from django.conf import settings
from typing import Optional, Dict, Any


class RedisClient:
    """Wrapper для Redis операций."""

    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=int(settings.REDIS_DB),
            decode_responses=True
        )

    # ========== Queue Operations ==========

    def enqueue_operation(self, message: Dict[str, Any]) -> bool:
        """
        Push message to operations queue.

        Args:
            message: Operation message (v2.0 schema)

        Returns:
            True if success
        """
        queue = settings.REDIS_QUEUE_OPERATIONS
        self.client.lpush(queue, json.dumps(message))
        return True

    def dequeue_result(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        Pop result from results queue (blocking).

        Args:
            timeout: Timeout in seconds

        Returns:
            Result dict or None
        """
        queue = settings.REDIS_QUEUE_RESULTS
        result = self.client.brpop(queue, timeout=timeout)

        if result:
            return json.loads(result[1])
        return None

    def enqueue_dlq(self, message: Dict[str, Any]) -> bool:
        """Push failed message to DLQ."""
        queue = settings.REDIS_QUEUE_DLQ
        self.client.lpush(queue, json.dumps(message))
        return True

    def get_queue_depth(self, queue_name: str) -> int:
        """Get queue length."""
        return self.client.llen(queue_name)

    # ========== Idempotency Locks ==========

    def acquire_lock(self, task_id: str, ttl_seconds: int = 3600) -> bool:
        """
        Acquire idempotency lock.

        Args:
            task_id: Operation/Task ID
            ttl_seconds: Lock TTL (default 1 hour)

        Returns:
            True if lock acquired, False if already exists
        """
        key = settings.REDIS_KEY_TASK_LOCK.format(task_id=task_id)
        return self.client.set(key, "locked", nx=True, ex=ttl_seconds)

    def extend_lock(self, task_id: str, ttl_seconds: int = 86400) -> bool:
        """Extend lock TTL (e.g., on completion to 24 hours)."""
        key = settings.REDIS_KEY_TASK_LOCK.format(task_id=task_id)
        return self.client.expire(key, ttl_seconds)

    def release_lock(self, task_id: str) -> bool:
        """Release lock (delete key)."""
        key = settings.REDIS_KEY_TASK_LOCK.format(task_id=task_id)
        return self.client.delete(key) > 0

    def check_lock(self, task_id: str) -> bool:
        """Check if lock exists."""
        key = settings.REDIS_KEY_TASK_LOCK.format(task_id=task_id)
        return self.client.exists(key) > 0

    # ========== Progress Tracking ==========

    def update_progress(self, task_id: str, progress: int, status: str) -> bool:
        """
        Update task progress.

        Args:
            task_id: Task ID
            progress: Progress percentage (0-100)
            status: Status string (processing, completed, etc.)
        """
        key = settings.REDIS_KEY_TASK_PROGRESS.format(task_id=task_id)
        self.client.hset(key, mapping={
            "progress": progress,
            "status": status,
            "updated_at": str(timezone.now())
        })
        self.client.expire(key, 3600)  # 1 hour TTL
        return True

    def get_progress(self, task_id: str) -> Optional[Dict[str, str]]:
        """Get task progress."""
        key = settings.REDIS_KEY_TASK_PROGRESS.format(task_id=task_id)
        data = self.client.hgetall(key)
        return data if data else None


# Singleton instance
redis_client = RedisClient()
```

**Зависимости:**
- `redis` package
- `settings.REDIS_*` constants

**Тестирование:**

```python
# apps/operations/tests/test_redis_client.py
import pytest
from apps.operations.redis_client import redis_client

@pytest.mark.django_db
def test_acquire_lock():
    task_id = "test-task-123"

    # First acquire should succeed
    assert redis_client.acquire_lock(task_id) is True

    # Second acquire should fail
    assert redis_client.acquire_lock(task_id) is False

    # Cleanup
    redis_client.release_lock(task_id)

@pytest.mark.django_db
def test_enqueue_operation():
    message = {
        "version": "2.0",
        "operation_id": "test-123",
        "operation_type": "create"
    }

    assert redis_client.enqueue_operation(message) is True

    # Check queue depth
    from django.conf import settings
    depth = redis_client.get_queue_depth(settings.REDIS_QUEUE_OPERATIONS)
    assert depth >= 1
```

**Acceptance Criteria:**
- ✅ Redis client подключается
- ✅ Queue operations работают (LPUSH/BRPOP)
- ✅ Lock operations работают (SET NX EX)
- ✅ Progress tracking работает (HSET)
- ✅ Unit tests pass

---

#### Task 2A.4: Реализовать `enqueue_operation()` Celery Task

**Файл:** `orchestrator/apps/operations/tasks.py`

**Описание:**
Переписать stub task с полной реализацией Message Protocol v2.0.

**Код:**

```python
"""Celery tasks for operations."""
from celery import shared_task
from django.utils import timezone
import logging

from .models import BatchOperation, Task
from .redis_client import redis_client

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=60,  # 60 seconds graceful
    time_limit=70,       # 70 seconds hard
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=300,  # Max 5 minutes
    retry_jitter=True    # Add randomness
)
def enqueue_operation(self, operation_id: str):
    """
    Enqueue operation to Go worker queue.

    Message Protocol v2.0:
    - Build message according to v2.0 schema
    - Check idempotency lock
    - Push to Redis queue: cc1c:operations:v1
    - Update operation status

    Args:
        operation_id: BatchOperation ID (UUID string)

    Returns:
        dict: {"status": "queued|duplicate", "operation_id": "..."}
    """
    logger.info(f"Enqueuing operation {operation_id}")

    try:
        # 1. Get operation from DB
        operation = BatchOperation.objects.get(id=operation_id)

        # 2. Idempotency check - acquire lock
        lock_acquired = redis_client.acquire_lock(
            task_id=operation_id,
            ttl_seconds=3600  # 1 hour
        )

        if not lock_acquired:
            logger.warning(
                f"Operation {operation_id} already locked (duplicate submission)"
            )
            return {
                "status": "duplicate",
                "operation_id": operation_id
            }

        # 3. Build Message Protocol v2.0 message
        message = {
            "version": "2.0",
            "operation_id": str(operation.id),
            "batch_id": None,  # TODO: Implement batch grouping in Phase 2
            "operation_type": operation.operation_type,
            "entity": operation.target_entity,

            "target_databases": [
                str(db.id) for db in operation.target_databases.all()
            ],

            "payload": {
                "data": operation.payload.get("data", {}),
                "filters": operation.payload.get("filters", {}),
                "options": operation.payload.get("options", {})
            },

            "execution_config": {
                "batch_size": operation.config.get("batch_size", 100),
                "timeout_seconds": 30,
                "retry_count": 3,
                "priority": "normal",
                "idempotency_key": str(operation.id)
            },

            "metadata": {
                "created_by": operation.created_by or "system",
                "created_at": operation.created_at.isoformat(),
                "template_id": str(operation.template.id) if operation.template else None,
                "tags": operation.metadata.get("tags", [])
            }
        }

        # 4. Enqueue to Redis
        redis_client.enqueue_operation(message)

        # 5. Update operation status
        operation.status = BatchOperation.STATUS_QUEUED
        operation.celery_task_id = self.request.id
        operation.save(update_fields=["status", "celery_task_id", "updated_at"])

        logger.info(
            f"Operation {operation_id} enqueued successfully",
            extra={
                "operation_id": operation_id,
                "operation_type": operation.operation_type,
                "target_databases_count": len(message["target_databases"])
            }
        )

        return {
            "status": "queued",
            "operation_id": operation_id,
            "celery_task_id": self.request.id
        }

    except BatchOperation.DoesNotExist:
        logger.error(f"Operation {operation_id} not found in database")
        raise

    except Exception as exc:
        logger.error(
            f"Error enqueueing operation {operation_id}: {exc}",
            exc_info=True
        )

        # Release lock on error
        redis_client.release_lock(operation_id)

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60)


@shared_task
def process_operation_result(result_data: dict):
    """
    Process operation result from Go worker.

    Called when worker publishes result to Redis results queue.
    Alternative to HTTP callback.

    Args:
        result_data: OperationResult dict from worker
    """
    operation_id = result_data.get("operation_id")
    status_val = result_data.get("status")
    results = result_data.get("results", [])

    logger.info(f"Processing result for operation {operation_id}, status={status_val}")

    try:
        operation = BatchOperation.objects.get(id=operation_id)

        # Update operation status
        if status_val == "completed":
            operation.status = BatchOperation.STATUS_COMPLETED
        elif status_val == "failed":
            operation.status = BatchOperation.STATUS_FAILED
        else:
            operation.status = BatchOperation.STATUS_PROCESSING

        # Update tasks
        for result in results:
            database_id = result.get("database_id")
            success = result.get("success")

            try:
                task = Task.objects.get(
                    batch_operation=operation,
                    database_id=database_id
                )

                if success:
                    task.mark_completed(result=result.get("data"))
                else:
                    task.mark_failed(
                        error_message=result.get("error", "Unknown error"),
                        error_code=result.get("error_code", "UNKNOWN_ERROR")
                    )
            except Task.DoesNotExist:
                logger.warning(
                    f"Task not found for database {database_id} in operation {operation_id}"
                )

        # Update operation progress
        operation.update_progress()

        # Extend lock to 24 hours (prevent re-execution)
        redis_client.extend_lock(operation_id, ttl_seconds=86400)

    except BatchOperation.DoesNotExist:
        logger.error(f"Operation {operation_id} not found")
```

**Зависимости:**
- `apps/operations/models.py` (BatchOperation, Task)
- `apps/operations/redis_client.py` (redis_client)
- Django settings

**Тестирование:**

```python
# apps/operations/tests/test_tasks.py
import pytest
from unittest.mock import patch, MagicMock
from apps.operations.tasks import enqueue_operation
from apps.operations.models import BatchOperation

@pytest.mark.django_db
def test_enqueue_operation_success():
    """Test successful operation enqueue."""

    # Create test operation
    operation = BatchOperation.objects.create(
        id="test-op-123",
        name="Test Operation",
        operation_type="create",
        target_entity="Catalog_Users",
        payload={"data": {"Name": "Test"}}
    )

    # Mock Redis
    with patch('apps.operations.tasks.redis_client') as mock_redis:
        mock_redis.acquire_lock.return_value = True
        mock_redis.enqueue_operation.return_value = True

        # Run task
        result = enqueue_operation(str(operation.id))

        # Assertions
        assert result["status"] == "queued"
        assert mock_redis.acquire_lock.called
        assert mock_redis.enqueue_operation.called

        # Check DB update
        operation.refresh_from_db()
        assert operation.status == BatchOperation.STATUS_QUEUED


@pytest.mark.django_db
def test_enqueue_operation_duplicate():
    """Test duplicate submission is rejected."""

    operation = BatchOperation.objects.create(
        id="test-op-456",
        name="Test Operation",
        operation_type="create",
        target_entity="Catalog_Users"
    )

    # Mock Redis - lock already exists
    with patch('apps.operations.tasks.redis_client') as mock_redis:
        mock_redis.acquire_lock.return_value = False

        result = enqueue_operation(str(operation.id))

        assert result["status"] == "duplicate"
```

**Acceptance Criteria:**
- ✅ Message protocol v2.0 соблюден
- ✅ Idempotency lock работает
- ✅ Redis queue push успешен
- ✅ Operation status обновляется
- ✅ Unit tests pass

---

#### Task 2A.5: Добавить Callback Endpoint

**Файл:** `orchestrator/apps/operations/views.py`

**Описание:**
HTTP callback endpoint для приема результатов от Go worker.

**Код:**

```python
# apps/operations/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import BatchOperation, Task
from .redis_client import redis_client

import logging
logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@extend_schema(
    summary="Callback от Go Worker после завершения операции",
    description="""
    Принимает результат выполнения операции от Go Worker.
    Обновляет статусы BatchOperation и Task.
    """,
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'operation_id': {'type': 'string'},
                'status': {'type': 'string', 'enum': ['completed', 'failed', 'timeout']},
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'database_id': {'type': 'string'},
                            'success': {'type': 'boolean'},
                            'data': {'type': 'object'},
                            'error': {'type': 'string'},
                            'error_code': {'type': 'string'},
                            'duration_seconds': {'type': 'number'}
                        }
                    }
                },
                'summary': {
                    'type': 'object',
                    'properties': {
                        'total': {'type': 'integer'},
                        'succeeded': {'type': 'integer'},
                        'failed': {'type': 'integer'}
                    }
                },
                'worker_id': {'type': 'string'}
            },
            'required': ['operation_id', 'status', 'results']
        }
    },
    responses={
        200: OpenApiResponse(description="Callback processed successfully"),
        400: OpenApiResponse(description="Invalid request"),
        404: OpenApiResponse(description="Operation not found")
    }
)
def operation_callback(request, operation_id):
    """
    Callback endpoint для Go Worker.

    POST /api/v1/operations/{operation_id}/callback

    Payload (OperationResult):
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
            "failed": 2
        },
        "worker_id": "worker-1"
    }
    """
    logger.info(f"Received callback for operation {operation_id}")

    # Validate operation_id match
    payload_op_id = request.data.get("operation_id")
    if payload_op_id != operation_id:
        return Response(
            {"error": "operation_id mismatch"},
            status=status.HTTP_400_BAD_REQUEST
        )

    result_status = request.data.get("status")
    results = request.data.get("results", [])
    worker_id = request.data.get("worker_id")

    if not result_status or not isinstance(results, list):
        return Response(
            {"error": "Invalid payload: missing status or results"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Get operation
        operation = BatchOperation.objects.get(id=operation_id)

        # Update operation status
        if result_status == "completed":
            operation.status = BatchOperation.STATUS_COMPLETED
        elif result_status == "failed":
            operation.status = BatchOperation.STATUS_FAILED
        elif result_status == "timeout":
            operation.status = BatchOperation.STATUS_FAILED  # Timeout = Failed

        operation.save(update_fields=["status", "updated_at"])

        # Update tasks
        for result in results:
            database_id = result.get("database_id")
            success = result.get("success")

            try:
                task = Task.objects.get(
                    batch_operation=operation,
                    database_id=database_id
                )

                # Set worker_id
                if worker_id:
                    task.worker_id = worker_id

                if success:
                    task.mark_completed(result=result.get("data"))
                else:
                    task.mark_failed(
                        error_message=result.get("error", "Unknown error"),
                        error_code=result.get("error_code", "UNKNOWN_ERROR"),
                        should_retry=True  # Will check retry_count internally
                    )

            except Task.DoesNotExist:
                logger.warning(
                    f"Task not found for database {database_id} in operation {operation_id}"
                )

        # Update operation progress
        operation.update_progress()

        # Extend idempotency lock to 24 hours
        redis_client.extend_lock(operation_id, ttl_seconds=86400)

        logger.info(
            f"Callback processed for operation {operation_id}",
            extra={
                "status": result_status,
                "total_results": len(results),
                "worker_id": worker_id
            }
        )

        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    except BatchOperation.DoesNotExist:
        logger.error(f"Operation {operation_id} not found")
        return Response(
            {"error": f"Operation {operation_id} not found"},
            status=status.HTTP_404_NOT_FOUND
        )
```

**Зависимости:**
- `apps/operations/models.py`
- `apps/operations/redis_client.py`

**URL Routing:**

```python
# apps/operations/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'batch-operations', views.BatchOperationViewSet)

urlpatterns = [
    path('', include(router.urls)),

    # Callback endpoint
    path(
        'operations/<str:operation_id>/callback',
        views.operation_callback,
        name='operation-callback'
    ),
]
```

**Тестирование:**

```python
# apps/operations/tests/test_views.py
import pytest
from rest_framework.test import APIClient
from apps.operations.models import BatchOperation, Task
from apps.databases.models import Database

@pytest.mark.django_db
def test_operation_callback_success():
    """Test callback with successful result."""

    # Setup
    client = APIClient()
    client.force_authenticate(user=User.objects.create_user('testuser'))

    operation = BatchOperation.objects.create(
        id="test-op-123",
        name="Test",
        operation_type="create",
        target_entity="Catalog_Users"
    )

    database = Database.objects.create(id="db-1", name="DB1")
    task = Task.objects.create(
        id="task-1",
        batch_operation=operation,
        database=database
    )

    # Callback payload
    payload = {
        "operation_id": "test-op-123",
        "status": "completed",
        "results": [
            {
                "database_id": "db-1",
                "success": True,
                "data": {"result": "ok"},
                "duration_seconds": 2.5
            }
        ],
        "worker_id": "worker-1"
    }

    # Call endpoint
    response = client.post(
        f"/api/v1/operations/test-op-123/callback",
        payload,
        format='json'
    )

    # Assertions
    assert response.status_code == 200

    operation.refresh_from_db()
    assert operation.status == BatchOperation.STATUS_COMPLETED

    task.refresh_from_db()
    assert task.status == Task.STATUS_COMPLETED
```

**Acceptance Criteria:**
- ✅ Callback endpoint доступен
- ✅ Worker authentication работает
- ✅ BatchOperation status обновляется
- ✅ Task statuses обновляются
- ✅ Idempotency lock продлевается
- ✅ Unit tests pass

---

#### Task 2A.6: Добавить Credentials Endpoint

**Файл:** `orchestrator/apps/databases/views.py`

**Описание:**
Endpoint для получения credentials по database_id (для Go Worker).

**Код:**

```python
# apps/databases/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Database

import logging
logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    summary="Получить credentials для базы (для Go Worker)",
    description="""
    Возвращает OData URL и credentials для базы данных.
    Используется Go Worker для выполнения операций.

    Requires authentication: Worker API Key
    """,
    responses={
        200: OpenApiResponse(
            description="Credentials returned",
            response={
                'type': 'object',
                'properties': {
                    'database_id': {'type': 'string'},
                    'odata_url': {'type': 'string'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string', 'description': 'Decrypted password'}
                }
            }
        ),
        404: OpenApiResponse(description="Database not found"),
        403: OpenApiResponse(description="Authentication failed")
    }
)
def get_database_credentials(request, database_id):
    """
    Get database credentials for Go Worker.

    GET /api/v1/databases/{database_id}/credentials

    Response:
    {
        "database_id": "uuid",
        "odata_url": "http://...",
        "username": "admin",
        "password": "decrypted_password"
    }
    """
    logger.info(f"Credentials request for database {database_id}")

    try:
        database = Database.objects.get(id=database_id)

        # ВАЖНО: Password автоматически расшифровывается
        # благодаря EncryptedCharField
        credentials = {
            "database_id": str(database.id),
            "odata_url": database.odata_url,
            "username": database.username,
            "password": database.password  # Auto-decrypted
        }

        logger.info(
            f"Credentials provided for database {database_id}",
            extra={"database_name": database.name}
        )

        return Response(credentials, status=status.HTTP_200_OK)

    except Database.DoesNotExist:
        logger.warning(f"Database {database_id} not found")
        return Response(
            {"error": f"Database {database_id} not found"},
            status=status.HTTP_404_NOT_FOUND
        )
```

**URL Routing:**

```python
# apps/databases/urls.py

urlpatterns = [
    # ... existing routes ...

    # Credentials endpoint for workers
    path(
        'databases/<str:database_id>/credentials',
        views.get_database_credentials,
        name='database-credentials'
    ),
]
```

**Тестирование:**

```python
# apps/databases/tests/test_credentials_endpoint.py
import pytest
from rest_framework.test import APIClient
from apps.databases.models import Database

@pytest.mark.django_db
def test_get_credentials_success():
    """Test credentials retrieval."""

    client = APIClient()
    # Simulate worker authentication
    client.credentials(HTTP_AUTHORIZATION='Bearer worker-api-key')

    # Create database
    db = Database.objects.create(
        id="db-123",
        name="Test DB",
        odata_url="http://localhost/odata",
        username="admin",
        password="secret123"
    )

    # Get credentials
    response = client.get(f"/api/v1/databases/db-123/credentials")

    assert response.status_code == 200
    assert response.data["database_id"] == "db-123"
    assert response.data["username"] == "admin"
    assert response.data["password"] == "secret123"  # Decrypted
```

**Acceptance Criteria:**
- ✅ Endpoint доступен
- ✅ Worker authentication работает
- ✅ Password decryption работает
- ✅ 404 если database не найдена
- ✅ Unit tests pass

---

### Track 2B: Go Worker Consumer

---

#### Task 2B.1: Обновить Models до v2.0

**Файл:** `go-services/shared/models/operation_v2.go` (новый)

**Описание:**
Создать Go structs согласно Message Protocol v2.0.

**Код:**

```go
// go-services/shared/models/operation_v2.go
package models

import "time"

// ========== Message Protocol v2.0 Structs ==========

// OperationMessage v2.0 - Full protocol specification
type OperationMessage struct {
	Version      string           `json:"version"`
	OperationID  string           `json:"operation_id"`
	BatchID      string           `json:"batch_id,omitempty"`
	OperationType string          `json:"operation_type"`
	Entity       string           `json:"entity"`

	TargetDatabases []string `json:"target_databases"`

	Payload      OperationPayload `json:"payload"`
	ExecConfig   ExecutionConfig  `json:"execution_config"`
	Metadata     MessageMetadata  `json:"metadata"`
}

type OperationPayload struct {
	Data    map[string]interface{} `json:"data"`
	Filters map[string]interface{} `json:"filters,omitempty"`
	Options map[string]interface{} `json:"options,omitempty"`
}

type ExecutionConfig struct {
	BatchSize      int    `json:"batch_size"`
	TimeoutSeconds int    `json:"timeout_seconds"`
	RetryCount     int    `json:"retry_count"`
	Priority       string `json:"priority"`
	IdempotencyKey string `json:"idempotency_key"`
}

type MessageMetadata struct {
	CreatedBy  string    `json:"created_by"`
	CreatedAt  time.Time `json:"created_at"`
	TemplateID string    `json:"template_id,omitempty"`
	Tags       []string  `json:"tags,omitempty"`
}

// OperationResult - Worker response to Orchestrator
type OperationResult struct {
	OperationID string           `json:"operation_id"`
	Status      string           `json:"status"` // completed|failed|timeout

	Results []DatabaseResult `json:"results"`

	Summary ResultSummary `json:"summary"`

	Timestamp time.Time `json:"timestamp"`
	WorkerID  string    `json:"worker_id"`
}

type DatabaseResult struct {
	DatabaseID   string                 `json:"database_id"`
	Success      bool                   `json:"success"`
	Data         map[string]interface{} `json:"data,omitempty"`
	Error        string                 `json:"error,omitempty"`
	ErrorCode    string                 `json:"error_code,omitempty"`
	Duration     float64                `json:"duration_seconds"`
}

type ResultSummary struct {
	Total       int     `json:"total"`
	Succeeded   int     `json:"succeeded"`
	Failed      int     `json:"failed"`
	AvgDuration float64 `json:"avg_duration_seconds"`
}

// ========== Validation ==========

// Validate validates the OperationMessage
func (om *OperationMessage) Validate() error {
	if om.Version != "2.0" {
		return fmt.Errorf("invalid version: %s (expected 2.0)", om.Version)
	}

	if om.OperationID == "" {
		return fmt.Errorf("operation_id is required")
	}

	if om.OperationType == "" {
		return fmt.Errorf("operation_type is required")
	}

	if len(om.TargetDatabases) == 0 {
		return fmt.Errorf("target_databases cannot be empty")
	}

	return nil
}
```

**Тестирование:**

```go
// shared/models/operation_v2_test.go
package models

import (
	"encoding/json"
	"testing"
	"time"
)

func TestOperationMessage_Validate(t *testing.T) {
	tests := []struct {
		name    string
		msg     OperationMessage
		wantErr bool
	}{
		{
			name: "valid message",
			msg: OperationMessage{
				Version:         "2.0",
				OperationID:     "test-123",
				OperationType:   "create",
				TargetDatabases: []string{"db-1"},
			},
			wantErr: false,
		},
		{
			name: "missing operation_id",
			msg: OperationMessage{
				Version:       "2.0",
				OperationType: "create",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.msg.Validate()
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestOperationMessage_JSONSerialization(t *testing.T) {
	msg := OperationMessage{
		Version:         "2.0",
		OperationID:     "test-123",
		OperationType:   "create",
		Entity:          "Catalog_Users",
		TargetDatabases: []string{"db-1", "db-2"},
		Payload: OperationPayload{
			Data: map[string]interface{}{
				"Name": "Test User",
			},
		},
		Metadata: MessageMetadata{
			CreatedBy: "user-123",
			CreatedAt: time.Now(),
		},
	}

	// Marshal
	data, err := json.Marshal(msg)
	if err != nil {
		t.Fatalf("failed to marshal: %v", err)
	}

	// Unmarshal
	var decoded OperationMessage
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("failed to unmarshal: %v", err)
	}

	if decoded.OperationID != msg.OperationID {
		t.Errorf("OperationID mismatch: got %s, want %s", decoded.OperationID, msg.OperationID)
	}
}
```

**Acceptance Criteria:**
- ✅ Все v2.0 structs определены
- ✅ JSON serialization/deserialization работает
- ✅ Validation функции работают
- ✅ Unit tests pass

---

#### Task 2B.2: Создать Credentials Client

**Файл:** `go-services/worker/internal/credentials/client.go` (новый)

**Описание:**
HTTP client для получения credentials от Django Orchestrator.

**Код:**

```go
// go-services/worker/internal/credentials/client.go
package credentials

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"go.uber.org/zap"
)

// DatabaseCredentials represents credentials for a 1C database
type DatabaseCredentials struct {
	DatabaseID string `json:"database_id"`
	ODataURL   string `json:"odata_url"`
	Username   string `json:"username"`
	Password   string `json:"password"`
}

// Client fetches credentials from Orchestrator API
type Client struct {
	orchestratorURL string
	apiKey          string
	httpClient      *http.Client

	// Cache with TTL
	cache    map[string]*cacheEntry
	cacheMu  sync.RWMutex
	cacheTTL time.Duration
}

type cacheEntry struct {
	credentials *DatabaseCredentials
	expiresAt   time.Time
}

// NewClient creates a new credentials client
func NewClient(orchestratorURL, apiKey string) *Client {
	return &Client{
		orchestratorURL: orchestratorURL,
		apiKey:          apiKey,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
		cache:    make(map[string]*cacheEntry),
		cacheTTL: 2 * time.Minute, // 2 minutes cache TTL
	}
}

// Fetch fetches credentials for a database (with caching)
func (c *Client) Fetch(ctx context.Context, databaseID string) (*DatabaseCredentials, error) {
	// Check cache first
	if creds := c.getFromCache(databaseID); creds != nil {
		logger.GetLogger().Debug("credentials cache hit",
			zap.String("database_id", databaseID),
		)
		return creds, nil
	}

	// Cache miss - fetch from API
	logger.GetLogger().Debug("credentials cache miss, fetching from API",
		zap.String("database_id", databaseID),
	)

	creds, err := c.fetchFromAPI(ctx, databaseID)
	if err != nil {
		return nil, err
	}

	// Store in cache
	c.putInCache(databaseID, creds)

	return creds, nil
}

func (c *Client) fetchFromAPI(ctx context.Context, databaseID string) (*DatabaseCredentials, error) {
	url := fmt.Sprintf("%s/api/v1/databases/%s/credentials", c.orchestratorURL, databaseID)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set authorization header (API Key)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch credentials: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized {
		return nil, fmt.Errorf("authentication failed: invalid API key")
	}

	if resp.StatusCode == http.StatusNotFound {
		return nil, fmt.Errorf("database %s not found", databaseID)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var creds DatabaseCredentials
	if err := json.NewDecoder(resp.Body).Decode(&creds); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	logger.GetLogger().Info("credentials fetched successfully",
		zap.String("database_id", databaseID),
		zap.String("odata_url", creds.ODataURL),
	)

	return &creds, nil
}

func (c *Client) getFromCache(databaseID string) *DatabaseCredentials {
	c.cacheMu.RLock()
	defer c.cacheMu.RUnlock()

	entry, exists := c.cache[databaseID]
	if !exists {
		return nil
	}

	// Check expiration
	if time.Now().After(entry.expiresAt) {
		return nil
	}

	return entry.credentials
}

func (c *Client) putInCache(databaseID string, creds *DatabaseCredentials) {
	c.cacheMu.Lock()
	defer c.cacheMu.Unlock()

	c.cache[databaseID] = &cacheEntry{
		credentials: creds,
		expiresAt:   time.Now().Add(c.cacheTTL),
	}
}

// ClearCache clears the credentials cache
func (c *Client) ClearCache() {
	c.cacheMu.Lock()
	defer c.cacheMu.Unlock()

	c.cache = make(map[string]*cacheEntry)
	logger.GetLogger().Info("credentials cache cleared")
}
```

**Тестирование:**

```go
// worker/internal/credentials/client_test.go
package credentials

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestClient_Fetch_Success(t *testing.T) {
	// Mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer test-api-key" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}

		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"database_id": "db-123",
			"odata_url": "http://localhost/odata",
			"username": "admin",
			"password": "secret"
		}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-api-key")

	creds, err := client.Fetch(context.Background(), "db-123")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if creds.DatabaseID != "db-123" {
		t.Errorf("expected database_id db-123, got %s", creds.DatabaseID)
	}
	if creds.Password != "secret" {
		t.Errorf("expected password secret, got %s", creds.Password)
	}
}

func TestClient_Fetch_Cache(t *testing.T) {
	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"database_id":"db-123","odata_url":"http://localhost","username":"admin","password":"secret"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-api-key")

	// First call - should hit API
	_, err := client.Fetch(context.Background(), "db-123")
	if err != nil {
		t.Fatalf("fetch failed: %v", err)
	}

	// Second call - should use cache
	_, err = client.Fetch(context.Background(), "db-123")
	if err != nil {
		t.Fatalf("fetch failed: %v", err)
	}

	if callCount != 1 {
		t.Errorf("expected 1 API call, got %d", callCount)
	}
}

func TestClient_Fetch_CacheExpiry(t *testing.T) {
	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"database_id":"db-123","odata_url":"http://localhost","username":"admin","password":"secret"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-api-key")
	client.cacheTTL = 100 * time.Millisecond // Short TTL for test

	// First call
	_, _ = client.Fetch(context.Background(), "db-123")

	// Wait for cache expiry
	time.Sleep(150 * time.Millisecond)

	// Second call - should hit API again
	_, _ = client.Fetch(context.Background(), "db-123")

	if callCount != 2 {
		t.Errorf("expected 2 API calls, got %d", callCount)
	}
}
```

**Acceptance Criteria:**
- ✅ HTTP client работает
- ✅ Authentication (API Key) работает
- ✅ Caching с TTL 2 min работает
- ✅ Cache expiry работает
- ✅ Error handling (401, 404) работает
- ✅ Unit tests pass

---

#### Task 2B.3: Обновить Redis Queue Consumer

**Файл:** `go-services/worker/internal/queue/consumer.go` (новый)

**Описание:**
Полноценный consumer с heartbeat, idempotency check, progress tracking.

**Код:**

```go
// go-services/worker/internal/queue/consumer.go
package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
	"go.uber.org/zap"
)

type Consumer struct {
	redis      *redis.Client
	processor  *processor.TaskProcessor
	workerID   string
	queueName  string
	resultsQueue string
}

// NewConsumer creates a new Redis queue consumer
func NewConsumer(cfg *config.Config, processor *processor.TaskProcessor) (*Consumer, error) {
	client := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})

	// Test connection
	if err := client.Ping(context.Background()).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	return &Consumer{
		redis:        client,
		processor:    processor,
		workerID:     cfg.WorkerID,
		queueName:    "cc1c:operations:v1",
		resultsQueue: "cc1c:operations:results:v1",
	}, nil
}

// Start starts the consumer main loop
func (c *Consumer) Start(ctx context.Context) error {
	log := logger.GetLogger()
	log.Info("worker started",
		zap.String("worker_id", c.workerID),
		zap.String("queue", c.queueName),
	)

	// Start heartbeat goroutine
	go c.heartbeatLoop(ctx)

	// Main processing loop
	for {
		select {
		case <-ctx.Done():
			log.Info("worker shutting down", zap.String("worker_id", c.workerID))
			return ctx.Err()

		default:
			// Blocking pop (5 second timeout)
			result, err := c.redis.BRPop(ctx, 5*time.Second, c.queueName).Result()
			if err == redis.Nil {
				// No task available, continue
				continue
			}
			if err != nil {
				log.Error("failed to dequeue task", zap.Error(err))
				time.Sleep(1 * time.Second) // Backoff on error
				continue
			}

			if len(result) < 2 {
				log.Error("invalid queue response")
				continue
			}

			// Parse message
			var msg models.OperationMessage
			if err := json.Unmarshal([]byte(result[1]), &msg); err != nil {
				log.Error("failed to parse message",
					zap.Error(err),
					zap.String("raw_message", result[1]),
				)
				continue
			}

			// Validate message
			if err := msg.Validate(); err != nil {
				log.Error("invalid message",
					zap.Error(err),
					zap.String("operation_id", msg.OperationID),
				)
				continue
			}

			// Process task
			c.processTask(ctx, &msg)
		}
	}
}

func (c *Consumer) processTask(ctx context.Context, msg *models.OperationMessage) {
	log := logger.GetLogger().With(
		zap.String("operation_id", msg.OperationID),
		zap.String("worker_id", c.workerID),
	)

	log.Info("processing task",
		zap.String("type", msg.OperationType),
		zap.Int("databases", len(msg.TargetDatabases)),
	)

	// Idempotency check
	lockKey := fmt.Sprintf("cc1c:task:%s:lock", msg.OperationID)
	exists := c.redis.Exists(ctx, lockKey).Val()
	if exists == 0 {
		log.Warn("task lock not found, skipping (likely duplicate or cancelled)")
		return
	}

	// Task timeout context
	taskCtx, cancel := context.WithTimeout(ctx,
		time.Duration(msg.ExecConfig.TimeoutSeconds)*time.Second)
	defer cancel()

	// Execute operation
	result := c.processor.Process(taskCtx, msg)

	// Publish result
	if err := c.publishResult(ctx, result); err != nil {
		log.Error("failed to publish result", zap.Error(err))
		// TODO: Retry or DLQ
	}

	// Extend lock on success
	if result.Status == "completed" {
		c.redis.Expire(ctx, lockKey, 24*time.Hour)
	}

	log.Info("task processing completed",
		zap.String("status", result.Status),
		zap.Int("succeeded", result.Summary.Succeeded),
		zap.Int("failed", result.Summary.Failed),
	)
}

func (c *Consumer) publishResult(ctx context.Context, result *models.OperationResult) error {
	data, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	return c.redis.LPush(ctx, c.resultsQueue, data).Err()
}

func (c *Consumer) heartbeatLoop(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			c.sendHeartbeat(ctx)
		}
	}
}

func (c *Consumer) sendHeartbeat(ctx context.Context) {
	key := fmt.Sprintf("cc1c:worker:%s:heartbeat", c.workerID)
	metadata := map[string]interface{}{
		"worker_id":      c.workerID,
		"status":         "alive",
		"last_heartbeat": time.Now().Format(time.RFC3339),
	}

	data, _ := json.Marshal(metadata)
	c.redis.Set(ctx, key, data, 30*time.Second) // TTL 30 seconds
}

// Close closes the Redis connection
func (c *Consumer) Close() error {
	return c.redis.Close()
}
```

**Acceptance Criteria:**
- ✅ BRPOP blocking dequeue работает
- ✅ Message parsing и validation работают
- ✅ Idempotency check реализован
- ✅ Heartbeat loop работает
- ✅ Result publishing работает
- ✅ Graceful shutdown работает

---

#### Task 2B.4: Переписать Processor с OData Integration

**Файл:** `go-services/worker/internal/processor/processor.go`

**Описание:**
Полная переработка processor для реального выполнения OData операций.

**Код:**

```go
// go-services/worker/internal/processor/processor.go
package processor

import (
	"context"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/credentials"
	"go.uber.org/zap"
)

// TaskProcessor handles task processing logic
type TaskProcessor struct {
	config      *config.Config
	credsClient *credentials.Client
	workerID    string
}

// NewTaskProcessor creates a new task processor
func NewTaskProcessor(cfg *config.Config, credsClient *credentials.Client) *TaskProcessor {
	return &TaskProcessor{
		config:      cfg,
		credsClient: credsClient,
		workerID:    cfg.WorkerID,
	}
}

// Process processes an operation message
func (p *TaskProcessor) Process(ctx context.Context, msg *models.OperationMessage) *models.OperationResult {
	log := logger.GetLogger().With(
		zap.String("operation_id", msg.OperationID),
		zap.String("worker_id", p.workerID),
	)

	result := &models.OperationResult{
		OperationID: msg.OperationID,
		WorkerID:    p.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResult{},
	}

	// Process each target database
	totalDatabases := len(msg.TargetDatabases)
	succeeded := 0
	failed := 0
	totalDuration := 0.0

	for i, databaseID := range msg.TargetDatabases {
		log.Info("processing database",
			zap.String("database_id", databaseID),
			zap.Int("progress", (i+1)*100/totalDatabases),
		)

		dbResult := p.processSingleDatabase(ctx, msg, databaseID)
		result.Results = append(result.Results, dbResult)

		if dbResult.Success {
			succeeded++
		} else {
			failed++
		}

		totalDuration += dbResult.Duration
	}

	// Calculate summary
	result.Summary = models.ResultSummary{
		Total:       totalDatabases,
		Succeeded:   succeeded,
		Failed:      failed,
		AvgDuration: totalDuration / float64(totalDatabases),
	}

	// Determine overall status
	if failed == 0 {
		result.Status = "completed"
	} else if succeeded == 0 {
		result.Status = "failed"
	} else {
		result.Status = "completed" // Partial success
	}

	// Check timeout
	if ctx.Err() == context.DeadlineExceeded {
		result.Status = "timeout"
	}

	return result
}

func (p *TaskProcessor) processSingleDatabase(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResult {
	start := time.Now()

	result := models.DatabaseResult{
		DatabaseID: databaseID,
	}

	// Fetch credentials
	creds, err := p.credsClient.Fetch(ctx, databaseID)
	if err != nil {
		result.Success = false
		result.Error = fmt.Sprintf("failed to fetch credentials: %v", err)
		result.ErrorCode = "CREDENTIALS_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// Execute operation via OData
	switch msg.OperationType {
	case "create":
		result = p.executeCreate(ctx, msg, creds)
	case "update":
		result = p.executeUpdate(ctx, msg, creds)
	case "delete":
		result = p.executeDelete(ctx, msg, creds)
	case "query":
		result = p.executeQuery(ctx, msg, creds)
	default:
		result.Success = false
		result.Error = fmt.Sprintf("unknown operation type: %s", msg.OperationType)
		result.ErrorCode = "INVALID_OPERATION"
	}

	result.DatabaseID = databaseID
	result.Duration = time.Since(start).Seconds()

	return result
}

func (p *TaskProcessor) executeCreate(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResult {
	// TODO: Implement OData POST
	// Placeholder implementation
	logger.GetLogger().Info("executing create operation (stub)",
		zap.String("entity", msg.Entity),
		zap.String("odata_url", creds.ODataURL),
	)

	// Simulate work
	time.Sleep(100 * time.Millisecond)

	return models.DatabaseResult{
		Success: true,
		Data: map[string]interface{}{
			"created": true,
			"entity":  msg.Entity,
		},
	}
}

func (p *TaskProcessor) executeUpdate(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResult {
	// TODO: Implement OData PATCH/PUT
	logger.GetLogger().Info("executing update operation (stub)")

	time.Sleep(100 * time.Millisecond)

	return models.DatabaseResult{
		Success: true,
		Data: map[string]interface{}{
			"updated": true,
		},
	}
}

func (p *TaskProcessor) executeDelete(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResult {
	// TODO: Implement OData DELETE
	logger.GetLogger().Info("executing delete operation (stub)")

	time.Sleep(100 * time.Millisecond)

	return models.DatabaseResult{
		Success: true,
		Data: map[string]interface{}{
			"deleted": true,
		},
	}
}

func (p *TaskProcessor) executeQuery(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResult {
	// TODO: Implement OData GET
	logger.GetLogger().Info("executing query operation (stub)")

	time.Sleep(100 * time.Millisecond)

	return models.DatabaseResult{
		Success: true,
		Data: map[string]interface{}{
			"results": []interface{}{},
		},
	}
}
```

**NOTE:** OData implementation - TODO для Phase 2.

**Acceptance Criteria:**
- ✅ Credential fetching работает
- ✅ Multi-database processing работает
- ✅ Timeout handling работает
- ✅ Result aggregation работает
- ⚠️ OData operations - stubs (реализация в Phase 2)

---

#### Task 2B.5: Обновить Worker main.go

**Файл:** `go-services/worker/cmd/main.go`

**Описание:**
Обновить entrypoint для подключения всех новых компонентов.

**Код:**

```go
// go-services/worker/cmd/main.go
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/worker/internal/credentials"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
	"github.com/commandcenter1c/commandcenter/worker/internal/queue"
	"go.uber.org/zap"
)

var (
	Version   = "dev"
	Commit    = "unknown"
	BuildTime = "unknown"
)

var showVersion bool

func init() {
	flag.BoolVar(&showVersion, "version", false, "Show version information and exit")
}

func main() {
	flag.Parse()

	if showVersion {
		fmt.Printf("Service: cc1c-worker\n")
		fmt.Printf("Version: %s\n", Version)
		fmt.Printf("Commit: %s\n", Commit)
		fmt.Printf("Built: %s\n", BuildTime)
		os.Exit(0)
	}

	// Load configuration
	cfg := config.LoadFromEnv()

	// Initialize logger
	logger.Init(logger.Config{
		Level:  cfg.LogLevel,
		Format: cfg.LogFormat,
	})

	log := logger.GetLogger()
	log.Info("starting Worker Service",
		zap.String("service", "cc1c-worker"),
		zap.String("version", Version),
		zap.String("commit", Commit),
		zap.String("worker_id", cfg.WorkerID),
	)

	// Create context with cancellation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Initialize credentials client
	credsClient := credentials.NewClient(
		cfg.OrchestratorURL,
		cfg.WorkerAPIKey,
	)
	log.Info("credentials client initialized")

	// Initialize task processor
	taskProcessor := processor.NewTaskProcessor(cfg, credsClient)
	log.Info("task processor initialized")

	// Initialize queue consumer
	consumer, err := queue.NewConsumer(cfg, taskProcessor)
	if err != nil {
		log.Fatal("failed to initialize consumer", zap.Error(err))
	}
	defer consumer.Close()

	log.Info("connected to Redis queue")

	// Start consumer (blocking)
	go func() {
		if err := consumer.Start(ctx); err != nil && err != context.Canceled {
			log.Error("consumer error", zap.Error(err))
		}
	}()

	log.Info("worker started, waiting for tasks")

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	<-sigChan
	log.Info("shutting down worker service")

	cancel() // Trigger graceful shutdown

	log.Info("worker service stopped")
}
```

**Зависимости:**
- `shared/config`
- `worker/internal/credentials`
- `worker/internal/processor`
- `worker/internal/queue`

**Acceptance Criteria:**
- ✅ Все компоненты инициализируются
- ✅ Graceful shutdown работает
- ✅ Worker запускается без ошибок

---

## 4. Порядок выполнения

### Оптимальная последовательность

**Week 1: Foundation**

**День 1-2: Django Setup**
1. Task 2A.1: Обновить Celery Config ✅
2. Task 2A.2: Добавить Redis Constants ✅
3. Task 2A.3: Создать Redis Client Wrapper ✅

**День 3-4: Django Tasks & Endpoints**
4. Task 2A.4: Реализовать `enqueue_operation()` ✅
5. Task 2A.5: Добавить Callback Endpoint ✅
6. Task 2A.6: Добавить Credentials Endpoint ✅

**День 5-7: Go Worker Foundation**
7. Task 2B.1: Обновить Models до v2.0 ✅
8. Task 2B.2: Создать Credentials Client ✅

---

**Week 2: Integration**

**День 8-10: Go Worker Consumer**
9. Task 2B.3: Обновить Redis Queue Consumer ✅
10. Task 2B.4: Переписать Processor (stub OData) ✅
11. Task 2B.5: Обновить Worker main.go ✅

**День 11-12: Integration Testing**
12. E2E flow testing ✅
13. Idempotency testing ✅
14. Timeout testing ✅

**День 13-14: Bug Fixes & Polish**
15. Fix discovered issues
16. Performance tuning
17. Documentation updates

---

### Parallel Tasks (можно делать параллельно)

**Django Side:**
- Task 2A.1, 2A.2, 2A.3 (независимы)
- Task 2A.5, 2A.6 (независимы от 2A.4)

**Go Side:**
- Task 2B.1, 2B.2 (независимы)

**Cross-stack:**
- Django + Go можно делать параллельно (разными разработчиками)

---

## 5. Testing Strategy

### 5.1 Unit Tests

**Python Unit Tests:**

```bash
# Orchestrator unit tests
cd orchestrator
pytest apps/operations/tests/test_tasks.py -v
pytest apps/operations/tests/test_redis_client.py -v
pytest apps/operations/tests/test_views.py -v
pytest apps/databases/tests/test_credentials_endpoint.py -v
```

**Target Coverage:** > 80%

**Go Unit Tests:**

```bash
# Worker unit tests
cd go-services/worker
go test ./internal/credentials/... -v
go test ./internal/processor/... -v
go test ./internal/queue/... -v

# Shared models tests
cd go-services/shared
go test ./models/... -v
```

**Target Coverage:** > 70%

### 5.2 Integration Tests

**E2E Flow Test:**

```python
# tests/integration/test_e2e_operation.py
import pytest
import time
from apps.operations.models import BatchOperation
from apps.databases.models import Database

@pytest.mark.integration
def test_end_to_end_operation_flow():
    """
    Test full flow: Django → Redis → Worker → Callback.

    Prerequisites:
    - Redis running
    - Go Worker running
    - Database configured
    """

    # 1. Create operation
    database = Database.objects.create(
        id="test-db-1",
        name="Test Database",
        odata_url="http://localhost/odata",
        username="admin",
        password="password123"
    )

    operation = BatchOperation.objects.create(
        id="e2e-test-op",
        name="E2E Test Operation",
        operation_type="create",
        target_entity="Catalog_Users",
        payload={
            "data": {
                "Name": "Test User",
                "Email": "test@example.com"
            }
        }
    )
    operation.target_databases.add(database)

    # 2. Enqueue operation
    from apps.operations.tasks import enqueue_operation
    result = enqueue_operation.delay(str(operation.id))

    # 3. Wait for processing (max 30 seconds)
    timeout = 30
    start = time.time()

    while time.time() - start < timeout:
        operation.refresh_from_db()

        if operation.status in [
            BatchOperation.STATUS_COMPLETED,
            BatchOperation.STATUS_FAILED
        ]:
            break

        time.sleep(1)

    # 4. Assertions
    operation.refresh_from_db()

    assert operation.status == BatchOperation.STATUS_COMPLETED, \
        f"Expected COMPLETED, got {operation.status}"

    assert operation.total_tasks == 1
    assert operation.completed_tasks == 1
    assert operation.failed_tasks == 0

    # Check task
    task = operation.tasks.first()
    assert task.status == Task.STATUS_COMPLETED
    assert task.worker_id is not None  # Worker ID set
```

**Idempotency Test:**

```python
@pytest.mark.integration
def test_idempotency_prevents_duplicate():
    """Test that duplicate submissions are prevented."""

    operation = BatchOperation.objects.create(
        id="idem-test",
        name="Idempotency Test",
        operation_type="create",
        target_entity="Catalog_Users"
    )

    # Submit twice
    result1 = enqueue_operation.delay(str(operation.id))
    result2 = enqueue_operation.delay(str(operation.id))

    # Wait
    time.sleep(2)

    # Check results
    assert result1.result["status"] == "queued"
    assert result2.result["status"] == "duplicate"

    # Only one task created
    assert operation.tasks.count() == 0  # Not yet created by worker
```

**Timeout Test:**

```python
@pytest.mark.integration
def test_timeout_handling():
    """Test that timeouts are handled correctly."""

    operation = BatchOperation.objects.create(
        id="timeout-test",
        name="Timeout Test",
        operation_type="create",
        target_entity="SlowEntity",  # Simulates slow operation
        config={"timeout_seconds": 1}  # Very short timeout
    )

    # Enqueue
    enqueue_operation.delay(str(operation.id))

    # Wait for timeout
    time.sleep(10)

    operation.refresh_from_db()

    # Should be failed or in DLQ
    assert operation.status in [
        BatchOperation.STATUS_FAILED,
        BatchOperation.STATUS_PROCESSING  # Still retrying
    ]
```

### 5.3 Load Testing

**Locust Load Test:**

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between
import uuid

class OperationUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def submit_operation(self):
        """Submit operation to Orchestrator."""

        operation_id = str(uuid.uuid4())

        payload = {
            "id": operation_id,
            "name": f"Load Test Operation {operation_id}",
            "operation_type": "create",
            "target_entity": "Catalog_Users",
            "target_databases": ["db-1", "db-2"],
            "payload": {
                "data": {
                    "Name": "Load Test User"
                }
            }
        }

        self.client.post(
            "/api/v1/batch-operations/",
            json=payload,
            headers={"Authorization": "Bearer test-token"}
        )
```

**Run Load Test:**

```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Open http://localhost:8089
# Set users: 20, spawn rate: 5
# Run for 5 minutes
```

**Load Test Scenarios:**

| Scenario | Users | Duration | Target | Pass Criteria |
|----------|-------|----------|--------|---------------|
| **Baseline** | 10 | 2 min | Verify stability | 100% success, <5s p95 |
| **Phase 1 Load** | 20 | 5 min | Simulate production | >95% success, <10s p95 |
| **Stress Test** | 50 | 10 min | Find breaking point | Graceful degradation |

---

## 6. Риски и митигация

### 6.1 Технические риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **Redis connection loss** | Средняя | Высокое | Retry logic, connection pooling, monitoring |
| **Credential cache stale** | Низкая | Среднее | TTL 2 min, manual refresh on 401 |
| **Worker crash during task** | Средняя | Среднее | Idempotency locks, task re-enqueue |
| **OData timeout** | Высокая | Высокое | Timeout 30s, retry 3x, DLQ |
| **1C transaction deadlock** | Средняя | Высокое | Keep transactions < 15s, batch operations |
| **Memory leak (Go worker)** | Низкая | Высокое | Monitoring, auto-restart, profiling |

### 6.2 Integration Risks

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **Protocol version mismatch** | Низкая | Высокое | Strict v2.0 validation, version field |
| **Queue name typo** | Низкая | Высокое | Use constants, integration tests |
| **Callback URL wrong** | Средняя | Среднее | Configuration validation, health checks |
| **API Key invalid** | Низкая | Высокое | Startup validation, clear error messages |

### 6.3 Operational Risks

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **DLQ overflow** | Низкая | Среднее | Monitoring, alerts, manual review process |
| **Worker pool exhaustion** | Средняя | Высокое | Auto-scaling (Phase 2), monitoring |
| **Database credentials change** | Средняя | Среднее | Cache TTL 2 min, refresh on 401 |

---

## Summary

### Готовность к реализации

**Track 2A (Django):** ✅ READY
- Все задачи определены
- Зависимости ясны
- Testing strategy готова

**Track 2B (Go):** ✅ READY
- Все задачи определены
- Models v2.0 spec готова
- Testing strategy готова

### Ожидаемый Timeline

- **Week 1:** Django Foundation + Go Models/Credentials
- **Week 2:** Go Consumer + Integration Testing

**Total:** ~2 недели для Sprint 2.1

### Next Steps

1. ✅ Review план с пользователем
2. **Начать реализацию** по порядку (Track 2A → Track 2B)
3. **Daily standups** для tracking progress
4. **Integration testing** в конце Week 2

---

**Документ готов к передаче Coder-у для реализации.**
