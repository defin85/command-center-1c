# План миграции BatchOperation на FSM

> Миграция модели BatchOperation с CharField на FSMField (django-fsm)

**Дата создания:** 2025-12-10
**Статус:** Планирование
**Приоритет:** Средний

---

## Текущее состояние

### Проблема

`BatchOperation.status` — это обычный `CharField`, статусы меняются прямым присвоением без валидации переходов:

```python
# orchestrator/apps/operations/models/batch_operation.py:96
status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

# Использование (небезопасно):
batch_op.status = BatchOperation.STATUS_PROCESSING  # Нет валидации!
batch_op.save()
```

### Диаграмма переходов статусов

```
                    ┌──────────────┐
                    │   PENDING    │
                    └──────┬───────┘
                           │ enqueue()
                    ┌──────▼───────┐
                    │   QUEUED     │
                    └──────┬───────┘
                           │ start_processing()
                    ┌──────▼───────┐
                    │  PROCESSING  │
                    └──────┬───────┘
                     ┌─────┴─────┐
              complete()    fail()
                 │              │
          ┌──────▼──────┐ ┌─────▼─────┐
          │  COMPLETED  │ │  FAILED   │
          └─────────────┘ └───────────┘

   + cancel() из PENDING/QUEUED/PROCESSING → CANCELLED
```

### Места прямого изменения статуса (15+ точек)

| Файл | Строки | Переход |
|------|--------|---------|
| `apps/operations/event_subscriber.py` | 350 | → PROCESSING |
| `apps/operations/event_subscriber.py` | 357, 692, 815 | → COMPLETED |
| `apps/operations/event_subscriber.py` | 372, 698, 822 | → FAILED |
| `apps/operations/services/operations_service.py` | 159, 929 | → QUEUED |
| `apps/operations/services/operations_service.py` | 948 | → FAILED |
| `apps/api_v2/views/operations.py` | 420 | → CANCELLED |
| `apps/operations/views.py` | 40 | → CANCELLED |
| `apps/operations/views.py` | 149, 151, 153 | → COMPLETED/FAILED |
| `apps/operations/models/batch_operation.py` | 153, 157, 161 | внутри update_progress() |

### Образец: WorkflowExecution (уже использует FSM)

```python
# orchestrator/apps/templates/workflow/models.py:590
status = FSMField(
    default=STATUS_PENDING,
    choices=STATUS_CHOICES,
    protected=True,  # Защита от прямого присвоения
)

@transition(field=status, source=STATUS_PENDING, target=STATUS_RUNNING)
def start(self):
    self.started_at = timezone.now()

@transition(field=status, source=STATUS_RUNNING, target=STATUS_COMPLETED)
def complete(self, result):
    self.final_result = result
    self.completed_at = timezone.now()
```

---

## План миграции

### Шаг 1: Модифицировать модель BatchOperation

**Файл:** `orchestrator/apps/operations/models/batch_operation.py`

```python
from django_fsm import FSMField, transition

class BatchOperation(models.Model):
    # ... существующие поля ...

    # ИЗМЕНЕНИЕ: CharField → FSMField
    status = FSMField(
        default=STATUS_PENDING,
        choices=STATUS_CHOICES,
        protected=True,  # Защита от прямого присвоения
        db_index=True,
    )

    # === FSM Transitions ===

    @transition(field=status, source=STATUS_PENDING, target=STATUS_QUEUED)
    def enqueue(self):
        """Поставить операцию в очередь Redis."""
        pass  # Логика постановки в очередь в сервисе

    @transition(field=status, source=STATUS_QUEUED, target=STATUS_PROCESSING)
    def start_processing(self):
        """Начать выполнение (Worker взял задачу)."""
        if not self.started_at:
            self.started_at = timezone.now()

    @transition(field=status, source=STATUS_PROCESSING, target=STATUS_COMPLETED)
    def complete(self):
        """Успешное завершение операции."""
        self.progress = 100
        if not self.completed_at:
            self.completed_at = timezone.now()

    @transition(field=status, source=STATUS_PROCESSING, target=STATUS_FAILED)
    def fail(self, error_message: str = None):
        """Завершение операции с ошибкой."""
        if not self.completed_at:
            self.completed_at = timezone.now()
        if error_message:
            if 'error' not in self.metadata:
                self.metadata['error'] = error_message

    @transition(
        field=status,
        source=[STATUS_PENDING, STATUS_QUEUED, STATUS_PROCESSING],
        target=STATUS_CANCELLED
    )
    def cancel(self):
        """Отмена операции."""
        if not self.completed_at:
            self.completed_at = timezone.now()
```

---

### Шаг 2: Создать миграцию

```bash
cd orchestrator
python manage.py makemigrations operations --name fsm_batch_operation_status
```

**Ожидаемая миграция:**

```python
# orchestrator/apps/operations/migrations/XXXX_fsm_batch_operation_status.py

import django_fsm
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('operations', 'previous_migration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batchoperation',
            name='status',
            field=django_fsm.FSMField(
                choices=[
                    ('pending', 'Pending'),
                    ('queued', 'Queued'),
                    ('processing', 'Processing'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                default='pending',
                max_length=50,
                protected=True,
            ),
        ),
    ]
```

---

### Шаг 3: Рефакторинг event_subscriber.py

**Файл:** `orchestrator/apps/operations/event_subscriber.py`

#### Замены:

```python
# Строка 350 — PROCESSING
# До:
batch_op.status = BatchOperation.STATUS_PROCESSING
if not batch_op.started_at:
    batch_op.started_at = timezone.now()
update_fields = ['status', 'started_at', 'updated_at']

# После:
batch_op.start_processing()  # FSM transition (устанавливает started_at внутри)
update_fields = ['status', 'started_at', 'updated_at']
```

```python
# Строки 357, 692, 815 — COMPLETED
# До:
batch_op.status = BatchOperation.STATUS_COMPLETED
batch_op.progress = 100
if not batch_op.completed_at:
    batch_op.completed_at = timezone.now()

# После:
batch_op.complete()  # FSM transition
```

```python
# Строки 372, 698, 822 — FAILED
# До:
batch_op.status = BatchOperation.STATUS_FAILED
if not batch_op.completed_at:
    batch_op.completed_at = timezone.now()
batch_op.metadata['error'] = message

# После:
batch_op.fail(error_message=message)  # FSM transition
```

---

### Шаг 4: Рефакторинг operations_service.py

**Файл:** `orchestrator/apps/operations/services/operations_service.py`

```python
# Строки 159, 929 — QUEUED
# До:
batch_operation.status = BatchOperation.STATUS_QUEUED
batch_operation.save(update_fields=['status', 'updated_at'])

# После:
batch_operation.enqueue()  # FSM transition
batch_operation.save(update_fields=['status', 'updated_at'])
```

```python
# Строка 948 — FAILED (при ошибке enqueue)
# До:
batch_operation.status = BatchOperation.STATUS_FAILED
batch_operation.save()

# После:
# Особый случай: ошибка до постановки в очередь
# Нужно добавить transition: PENDING → FAILED
batch_operation.fail_before_queue(error_message=str(e))
batch_operation.save()
```

**Дополнительный transition для edge case:**

```python
@transition(field=status, source=STATUS_PENDING, target=STATUS_FAILED)
def fail_before_queue(self, error_message: str = None):
    """Ошибка до постановки в очередь (например, Redis недоступен)."""
    if not self.completed_at:
        self.completed_at = timezone.now()
    if error_message:
        self.metadata['error'] = error_message
```

---

### Шаг 5: Рефакторинг views

#### api_v2/views/operations.py

```python
# Строка 420 — cancel_operation
# До:
operation.status = BatchOperation.STATUS_CANCELLED
operation.save(update_fields=['status', 'updated_at'])

# После:
operation.cancel()  # FSM transition
operation.save(update_fields=['status', 'completed_at', 'updated_at'])
```

#### operations/views.py

```python
# Строка 40 — cancel
# До:
operation.status = BatchOperation.STATUS_CANCELLED

# После:
operation.cancel()
```

```python
# Строки 149, 151, 153 — complete/fail based on result
# До:
if result.success:
    operation.status = BatchOperation.STATUS_COMPLETED
else:
    operation.status = BatchOperation.STATUS_FAILED

# После:
if result.success:
    operation.complete()
else:
    operation.fail(error_message=result.error)
```

---

### Шаг 6: Рефакторинг update_progress()

**Файл:** `orchestrator/apps/operations/models/batch_operation.py`

```python
def update_progress(self):
    """
    Update progress and statistics based on related tasks.
    Uses FSM transitions for status changes.
    """
    from .task import Task
    from django_fsm import can_proceed

    tasks = self.tasks.all()
    self.total_tasks = tasks.count()
    self.completed_tasks = tasks.filter(status=Task.STATUS_COMPLETED).count()
    self.failed_tasks = tasks.filter(status=Task.STATUS_FAILED).count()
    self.retry_tasks = tasks.filter(status=Task.STATUS_RETRY).count()

    if self.total_tasks > 0:
        self.progress = int((self.completed_tasks / self.total_tasks) * 100)
    else:
        self.progress = 0

    # FSM transitions вместо прямого присвоения
    all_done = (self.completed_tasks + self.failed_tasks) == self.total_tasks

    if self.completed_tasks == self.total_tasks and self.total_tasks > 0:
        # Все задачи успешно завершены
        if can_proceed(self, 'complete'):
            self.complete()
    elif self.failed_tasks > 0 and all_done:
        # Есть failed задачи и все задачи завершены
        if can_proceed(self, 'fail'):
            self.fail()

    self.save(update_fields=[
        'total_tasks',
        'completed_tasks',
        'failed_tasks',
        'retry_tasks',
        'progress',
        'status',
        'completed_at',
        'updated_at'
    ])
```

---

### Шаг 7: Добавить тесты FSM

**Файл:** `orchestrator/apps/operations/tests/test_batch_operation_fsm.py`

```python
"""Tests for BatchOperation FSM transitions."""

import pytest
from django.utils import timezone
from django_fsm import TransitionNotAllowed

from apps.operations.models import BatchOperation


@pytest.mark.django_db
class TestBatchOperationFSM:
    """Test FSM state transitions for BatchOperation."""

    @pytest.fixture
    def batch_operation(self):
        """Create a pending batch operation."""
        return BatchOperation.objects.create(
            id='test-op-001',
            name='Test Operation',
            operation_type=BatchOperation.TYPE_LOCK_SCHEDULED_JOBS,
            target_entity='Infobase',
            status=BatchOperation.STATUS_PENDING,
        )

    # === Valid Transitions ===

    def test_pending_to_queued(self, batch_operation):
        """Test PENDING → QUEUED transition."""
        assert batch_operation.status == BatchOperation.STATUS_PENDING

        batch_operation.enqueue()
        batch_operation.save()

        assert batch_operation.status == BatchOperation.STATUS_QUEUED

    def test_queued_to_processing(self, batch_operation):
        """Test QUEUED → PROCESSING transition."""
        batch_operation.enqueue()
        batch_operation.save()

        batch_operation.start_processing()
        batch_operation.save()

        assert batch_operation.status == BatchOperation.STATUS_PROCESSING
        assert batch_operation.started_at is not None

    def test_processing_to_completed(self, batch_operation):
        """Test PROCESSING → COMPLETED transition."""
        batch_operation.enqueue()
        batch_operation.start_processing()

        batch_operation.complete()
        batch_operation.save()

        assert batch_operation.status == BatchOperation.STATUS_COMPLETED
        assert batch_operation.progress == 100
        assert batch_operation.completed_at is not None

    def test_processing_to_failed(self, batch_operation):
        """Test PROCESSING → FAILED transition."""
        batch_operation.enqueue()
        batch_operation.start_processing()

        batch_operation.fail(error_message='Test error')
        batch_operation.save()

        assert batch_operation.status == BatchOperation.STATUS_FAILED
        assert batch_operation.completed_at is not None
        assert batch_operation.metadata.get('error') == 'Test error'

    def test_cancel_from_pending(self, batch_operation):
        """Test PENDING → CANCELLED transition."""
        batch_operation.cancel()
        batch_operation.save()

        assert batch_operation.status == BatchOperation.STATUS_CANCELLED

    def test_cancel_from_queued(self, batch_operation):
        """Test QUEUED → CANCELLED transition."""
        batch_operation.enqueue()

        batch_operation.cancel()
        batch_operation.save()

        assert batch_operation.status == BatchOperation.STATUS_CANCELLED

    def test_cancel_from_processing(self, batch_operation):
        """Test PROCESSING → CANCELLED transition."""
        batch_operation.enqueue()
        batch_operation.start_processing()

        batch_operation.cancel()
        batch_operation.save()

        assert batch_operation.status == BatchOperation.STATUS_CANCELLED

    # === Invalid Transitions ===

    def test_cannot_skip_queued(self, batch_operation):
        """Cannot go directly from PENDING to PROCESSING."""
        with pytest.raises(TransitionNotAllowed):
            batch_operation.start_processing()

    def test_cannot_complete_from_pending(self, batch_operation):
        """Cannot complete from PENDING state."""
        with pytest.raises(TransitionNotAllowed):
            batch_operation.complete()

    def test_cannot_complete_from_queued(self, batch_operation):
        """Cannot complete from QUEUED state."""
        batch_operation.enqueue()

        with pytest.raises(TransitionNotAllowed):
            batch_operation.complete()

    def test_cannot_reprocess_completed(self, batch_operation):
        """Cannot go back to PROCESSING from COMPLETED."""
        batch_operation.enqueue()
        batch_operation.start_processing()
        batch_operation.complete()
        batch_operation.save()

        with pytest.raises(TransitionNotAllowed):
            batch_operation.start_processing()

    def test_cannot_cancel_completed(self, batch_operation):
        """Cannot cancel a COMPLETED operation."""
        batch_operation.enqueue()
        batch_operation.start_processing()
        batch_operation.complete()
        batch_operation.save()

        with pytest.raises(TransitionNotAllowed):
            batch_operation.cancel()

    def test_cannot_cancel_failed(self, batch_operation):
        """Cannot cancel a FAILED operation."""
        batch_operation.enqueue()
        batch_operation.start_processing()
        batch_operation.fail()
        batch_operation.save()

        with pytest.raises(TransitionNotAllowed):
            batch_operation.cancel()

    # === Protected Field ===

    def test_direct_assignment_raises_error(self, batch_operation):
        """Direct status assignment should raise AttributeError."""
        with pytest.raises(AttributeError):
            batch_operation.status = BatchOperation.STATUS_COMPLETED


@pytest.mark.django_db
class TestBatchOperationFSMEdgeCases:
    """Test edge cases for BatchOperation FSM."""

    def test_fail_before_queue(self):
        """Test PENDING → FAILED for enqueue errors."""
        op = BatchOperation.objects.create(
            id='test-op-fail-early',
            name='Fail Early Test',
            operation_type=BatchOperation.TYPE_LOCK_SCHEDULED_JOBS,
            target_entity='Infobase',
        )

        op.fail_before_queue(error_message='Redis connection failed')
        op.save()

        assert op.status == BatchOperation.STATUS_FAILED
        assert 'Redis connection failed' in op.metadata.get('error', '')

    def test_idempotent_transitions(self):
        """Test that transitions are idempotent when already in target state."""
        op = BatchOperation.objects.create(
            id='test-op-idempotent',
            name='Idempotent Test',
            operation_type=BatchOperation.TYPE_LOCK_SCHEDULED_JOBS,
            target_entity='Infobase',
        )

        op.enqueue()
        op.start_processing()
        op.complete()
        op.save()

        # Trying to complete again should raise
        with pytest.raises(TransitionNotAllowed):
            op.complete()
```

---

### Шаг 8: Прогнать все тесты

```bash
# Все тесты Django
cd orchestrator && pytest -v

# Только FSM тесты
pytest apps/operations/tests/test_batch_operation_fsm.py -v

# С coverage
pytest --cov=apps/operations --cov-report=html
```

---

## Порядок выполнения

| # | Задача | Файлы | Сложность | Риск |
|---|--------|-------|-----------|------|
| 1 | Модифицировать модель | `batch_operation.py` | Средняя | Низкий |
| 2 | Создать миграцию | `migrations/` | Низкая | Низкий |
| 3 | Добавить тесты FSM | `test_batch_operation_fsm.py` | Средняя | Низкий |
| 4 | Рефакторинг event_subscriber | `event_subscriber.py` | Высокая | Средний |
| 5 | Рефакторинг operations_service | `operations_service.py` | Средняя | Средний |
| 6 | Рефакторинг views | `views.py` x2 | Низкая | Низкий |
| 7 | Рефакторинг update_progress | `batch_operation.py` | Средняя | Средний |
| 8 | Прогнать все тесты | - | - | - |
| 9 | Ручное тестирование | - | - | - |

---

## Преимущества после миграции

1. **Валидация переходов** — нельзя перейти из COMPLETED в PROCESSING
2. **Защита от ошибок** — `protected=True` блокирует прямое присвоение
3. **Единообразие** — один паттерн для BatchOperation и WorkflowExecution
4. **Аудит** — легко добавить логирование в transition методы
5. **Расширяемость** — можно добавить conditions и permissions

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Сломаются существующие тесты | Высокая | Обновить все тесты, использующие прямое присвоение |
| Event subscriber перестанет работать | Средняя | Тщательно протестировать event flow |
| Несовместимость со старыми данными | Низкая | Миграция только меняет тип поля, данные сохранятся |
| Go Worker не сможет обновлять статус | Нет | Worker публикует события, не меняет статус напрямую |

---

## Rollback план

1. Откатить миграцию: `python manage.py migrate operations <previous_migration>`
2. Вернуть `CharField` вместо `FSMField`
3. Убрать `@transition` декораторы
4. Вернуть прямое присвоение статусов

---

## Связанные документы

- `orchestrator/apps/templates/workflow/models.py` — образец FSM реализации
- `docs/EVENT_DRIVEN_ROADMAP.md` — архитектура событий
- `CLAUDE.md` — общие правила проекта

---

**Автор:** Claude (AI Assistant)
**Версия:** 1.0
