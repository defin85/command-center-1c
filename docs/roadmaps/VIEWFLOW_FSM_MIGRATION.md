# Roadmap: Миграция на viewflow.fsm

> **Статус:** На будущее (не критично)
> **Приоритет:** Низкий
> **Дата создания:** 2025-11-30
> **Текущее решение:** django-fsm-2 (community fork)

---

## Контекст

### Текущее состояние

Проект использует **django-fsm-2** для реализации Finite State Machine в модели `WorkflowExecution`. Это community-поддерживаемый fork оригинального django-fsm, который:

- Полностью совместим с существующим кодом
- Активно поддерживается (django-commons)
- Не требует изменений при обновлении

### Зачем рассматривать viewflow.fsm?

Автор оригинального django-fsm интегрировал его в **viewflow** — enterprise-grade workflow platform. Миграция на viewflow.fsm может быть целесообразна если:

1. Потребуется визуальный редактор workflow (Viewflow Pro)
2. Нужна интеграция с BPMN-процессами
3. Требуется более строгая типизация через Enum
4. Планируется использование других компонентов Viewflow

---

## Анализ различий API

### Импорты

```python
# django-fsm-2 (текущий)
from django_fsm import FSMField, transition, TransitionNotAllowed

# viewflow.fsm (новый)
from viewflow.fsm import State, TransitionNotAllowed
```

### Определение состояний

```python
# django-fsm-2 (текущий) - строки
class WorkflowExecution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = FSMField(default='pending', choices=STATUS_CHOICES)

# viewflow.fsm (новый) - только Enum
class ExecutionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'

class WorkflowExecutionFlow:
    status = State(ExecutionStatus, default=ExecutionStatus.PENDING)
```

### Декораторы переходов

```python
# django-fsm-2 (текущий)
class WorkflowExecution(models.Model):
    @transition(field=status, source='pending', target='running')
    def start(self):
        self.started_at = timezone.now()

# viewflow.fsm (новый)
class WorkflowExecutionFlow:
    status = State(ExecutionStatus, default=ExecutionStatus.PENDING)

    def __init__(self, execution):
        self.execution = execution

    @status.setter()
    def _set_status(self, value):
        self.execution.status = value

    @status.getter()
    def _get_status(self):
        return self.execution.status

    @status.transition(source=ExecutionStatus.PENDING, target=ExecutionStatus.RUNNING)
    def start(self):
        self.execution.started_at = timezone.now()
```

### Архитектурные различия

| Аспект | django-fsm-2 | viewflow.fsm |
|--------|--------------|--------------|
| Интеграция | Встроено в модель | Отдельный Flow-класс |
| Типы состояний | Строки или Enum | Только Enum |
| Getter/Setter | Не нужны | Обязательны |
| Зависимости | Минимальные | viewflow (тяжёлый) |
| Django Admin | Встроенная поддержка | Через viewflow-admin |

---

## План миграции

### Этап 1: Подготовка (1-2 часа)

- [ ] Создать Enum для всех статусов
- [ ] Написать адаптер для обратной совместимости
- [ ] Подготовить тестовое окружение

```python
# apps/templates/workflow/enums.py
from django.db import models

class ExecutionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'
```

### Этап 2: Создание Flow-классов (2-3 часа)

- [ ] Создать `WorkflowExecutionFlow` класс
- [ ] Реализовать getter/setter для синхронизации с ORM
- [ ] Перенести логику переходов

```python
# apps/templates/workflow/flows.py
from viewflow.fsm import State
from .enums import ExecutionStatus

class WorkflowExecutionFlow:
    status = State(ExecutionStatus, default=ExecutionStatus.PENDING)

    def __init__(self, execution: 'WorkflowExecution'):
        self.execution = execution

    @status.setter()
    def _set_status(self, value):
        self.execution.status = value

    @status.getter()
    def _get_status(self):
        return ExecutionStatus(self.execution.status)

    @status.transition(source=ExecutionStatus.PENDING, target=ExecutionStatus.RUNNING)
    def start(self):
        from django.utils import timezone
        self.execution.started_at = timezone.now()

    @status.transition(source=ExecutionStatus.RUNNING, target=ExecutionStatus.COMPLETED)
    def complete(self):
        from django.utils import timezone
        self.execution.finished_at = timezone.now()

    @status.transition(source=ExecutionStatus.RUNNING, target=ExecutionStatus.FAILED)
    def fail(self):
        from django.utils import timezone
        self.execution.finished_at = timezone.now()

    @status.transition(source=[ExecutionStatus.PENDING, ExecutionStatus.RUNNING],
                       target=ExecutionStatus.CANCELLED)
    def cancel(self):
        from django.utils import timezone
        self.execution.finished_at = timezone.now()
```

### Этап 3: Обновление модели (1-2 часа)

- [ ] Удалить FSMField и @transition из модели
- [ ] Добавить property для доступа к Flow
- [ ] Сохранить обратную совместимость методов

```python
# apps/templates/workflow/models.py
class WorkflowExecution(models.Model):
    status = models.CharField(
        max_length=20,
        choices=ExecutionStatus.choices,
        default=ExecutionStatus.PENDING,
        db_index=True,
    )

    @cached_property
    def flow(self) -> WorkflowExecutionFlow:
        return WorkflowExecutionFlow(self)

    # Прокси-методы для обратной совместимости
    def start(self):
        self.flow.start()
        self.save(update_fields=['status', 'started_at'])

    def complete(self):
        self.flow.complete()
        self.save(update_fields=['status', 'finished_at'])

    def fail(self):
        self.flow.fail()
        self.save(update_fields=['status', 'finished_at'])

    def cancel(self):
        self.flow.cancel()
        self.save(update_fields=['status', 'finished_at'])
```

### Этап 4: Миграция данных (30 минут)

- [ ] Создать Django миграцию
- [ ] Проверить совместимость существующих данных

```python
# migrations/000X_migrate_to_viewflow_fsm.py
from django.db import migrations

def forwards(apps, schema_editor):
    # Данные не меняются - статусы остаются строками
    # Миграция нужна только если меняется тип поля
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('templates', '0003_...'),
    ]
    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
```

### Этап 5: Обновление тестов (1-2 часа)

- [ ] Обновить импорты в тестах
- [ ] Адаптировать тесты под новый API
- [ ] Добавить тесты для Flow-класса

```python
# tests/test_models.py
from viewflow.fsm import TransitionNotAllowed  # Новый импорт

def test_execution_fsm_start_transition(workflow_execution):
    assert workflow_execution.status == ExecutionStatus.PENDING
    workflow_execution.start()  # Работает через прокси
    assert workflow_execution.status == ExecutionStatus.RUNNING
```

### Этап 6: Финализация (1 час)

- [ ] Обновить requirements.txt
- [ ] Удалить django-fsm-2
- [ ] Полный прогон тестов
- [ ] Обновить документацию

```diff
# requirements.txt
- django-fsm-2>=4.0.0
+ viewflow>=3.0.0
```

---

## Оценка трудозатрат

| Этап | Время | Риск |
|------|-------|------|
| Подготовка | 1-2 ч | Низкий |
| Flow-классы | 2-3 ч | Средний |
| Обновление модели | 1-2 ч | Средний |
| Миграция данных | 30 мин | Низкий |
| Обновление тестов | 1-2 ч | Средний |
| Финализация | 1 ч | Низкий |
| **Итого** | **6-10 ч** | **Средний** |

---

## Критерии для начала миграции

Миграцию стоит начинать когда:

1. **Требуется визуальный редактор** — Viewflow Pro предоставляет drag-and-drop конструктор workflow
2. **Нужна BPMN интеграция** — viewflow поддерживает BPMN 2.0
3. **django-fsm-2 перестанет поддерживаться** — маловероятно в ближайшие годы
4. **Требуется строгая типизация** — Enum-only подход предотвращает ошибки

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Breaking changes в коде | Высокая | Прокси-методы для обратной совместимости |
| Регрессии в тестах | Средняя | Полное покрытие тестами перед миграцией |
| Увеличение зависимостей | Высокая | viewflow ~5MB vs django-fsm-2 ~50KB |
| Сложность отладки | Средняя | Flow-класс добавляет уровень абстракции |

---

## Альтернативы

1. **Оставить django-fsm-2** — рекомендуется пока не появятся явные причины для миграции
2. **python-statemachine** — легковесная альтернатива без Django-интеграции
3. **transitions** — ещё одна FSM библиотека для Python

---

## Ссылки

- [viewflow.fsm Documentation](https://docs.viewflow.io/fsm/index.html)
- [Wrapping Django Models](https://docs.viewflow.io/fsm/models.html)
- [Migration Guide (official)](https://docs.viewflow.io/fsm/index.html#migration-from-django-fsm)
- [django-fsm-2 GitHub](https://github.com/django-commons/django-fsm-2)
- [Viewflow Pro](https://viewflow.io/) — коммерческая версия с визуальным редактором
