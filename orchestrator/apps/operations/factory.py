"""
BatchOperationFactory - фабрика для создания BatchOperation и связанных Task.

Используется WorkflowEngine для создания операций из шаблонов.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from django.db import transaction

from apps.databases.models import Database
from apps.operations.models import BatchOperation, Task
from apps.templates.models import OperationTemplate
from apps.templates.tracing import get_current_trace_id

logger = logging.getLogger(__name__)

TARGET_SCOPE_GLOBAL = "global"


def _extract_target_scope(rendered_data: Dict[str, Any]) -> str:
    if not isinstance(rendered_data, dict):
        return ""
    options = rendered_data.get("options")
    if isinstance(options, dict):
        value = str(options.get("target_scope") or "").strip().lower()
        if value:
            return value
    return ""


class BatchOperationFactory:
    """
    Фабрика для создания BatchOperation и связанных Task.

    Создает операции из шаблонов для выполнения на нескольких базах данных.
    Поддерживает как workflow-операции (с execution_id и node_id),
    так и ручные операции.
    """

    @classmethod
    def create(
        cls,
        template: OperationTemplate,
        rendered_data: Dict[str, Any],
        target_databases: List[str],
        workflow_execution_id: Optional[str] = None,
        node_id: Optional[str] = None,
        created_by: str = "system"
    ) -> BatchOperation:
        """
        Создает BatchOperation и Task для каждой целевой базы данных.

        Args:
            template: Шаблон операции
            rendered_data: Данные операции после рендеринга шаблона
            target_databases: Список UUID баз данных (строки)
            workflow_execution_id: ID выполнения workflow (опционально)
            node_id: ID узла в workflow (опционально)
            created_by: Имя пользователя/системы, создавшего операцию

        Returns:
            Созданный BatchOperation

        Raises:
            ValueError: Если target_databases пустой
            Database.DoesNotExist: Если база данных не найдена
        """
        target_scope = _extract_target_scope(rendered_data)

        # Валидация
        if not target_databases and target_scope != TARGET_SCOPE_GLOBAL:
            raise ValueError("target_databases cannot be empty")

        # Генерация operation_id
        operation_id = cls._generate_operation_id(
            workflow_execution_id=workflow_execution_id,
            node_id=node_id
        )

        # Определяем имя операции
        if workflow_execution_id:
            operation_name = f"Workflow: {template.name}"
        else:
            operation_name = f"Manual: {template.name}"

        # Определяем тип операции
        operation_type = getattr(template, 'operation_type', None) or 'query'

        # Определяем целевую сущность
        target_entity = rendered_data.get('entity', template.name)

        # Формируем метаданные
        trace_id = get_current_trace_id()
        metadata = {
            'workflow_execution_id': workflow_execution_id,
            'node_id': node_id,
        }
        if trace_id:
            metadata['trace_id'] = trace_id

        logger.info(
            f"Creating BatchOperation: id={operation_id}, "
            f"template={template.name}, databases={len(target_databases)}"
        )

        with transaction.atomic():
            # Создаем BatchOperation
            operation = BatchOperation.objects.create(
                id=operation_id,
                name=operation_name,
                operation_type=operation_type,
                target_entity=target_entity,
                payload=rendered_data,
                template=template,
                status=BatchOperation.STATUS_PENDING,
                created_by=created_by,
                metadata=metadata,
            )

            if target_scope == TARGET_SCOPE_GLOBAL:
                task_id = f"{operation_id}-global"
                Task.objects.create(
                    id=task_id,
                    batch_operation=operation,
                    database=None,
                    status=Task.STATUS_PENDING,
                )
                operation.total_tasks = 1
                operation.save(update_fields=['total_tasks', 'updated_at'])
                logger.info(
                    f"BatchOperation created: id={operation_id}, tasks=1 (global)"
                )
                return operation

            # Получаем объекты Database
            databases = list(Database.objects.filter(id__in=target_databases))

            # Проверяем, что все базы найдены
            found_ids = {db.id for db in databases}
            missing_ids = set(target_databases) - found_ids
            if missing_ids:
                logger.warning(
                    f"Some databases not found: {missing_ids}. "
                    f"Continuing with {len(databases)} databases."
                )

            # Устанавливаем M2M связь
            operation.target_databases.set(databases)

            # Bulk create Task для каждой базы
            tasks = []
            for db in databases:
                task_id = f"{operation_id}-{db.id[:8]}"
                tasks.append(Task(
                    id=task_id,
                    batch_operation=operation,
                    database=db,
                    status=Task.STATUS_PENDING,
                ))

            Task.objects.bulk_create(tasks)

            # Обновляем статистику
            operation.total_tasks = len(tasks)
            operation.save(update_fields=['total_tasks', 'updated_at'])

            logger.info(
                f"BatchOperation created: id={operation_id}, "
                f"tasks={len(tasks)}"
            )

        return operation

    @classmethod
    def _generate_operation_id(
        cls,
        workflow_execution_id: Optional[str] = None,
        node_id: Optional[str] = None
    ) -> str:
        """
        Генерирует уникальный ID операции.

        Важно: BatchOperation.id и Task.id имеют ограничение max_length=64,
        поэтому ID должен быть коротким и не включать execution_id / node_id.
        Эти значения сохраняются в metadata.

        Формат:
          - workflow: batch-wf-{uuid4hex}
          - manual:   batch-manual-{uuid4hex}

        Args:
            workflow_execution_id: ID выполнения workflow
            node_id: ID узла в workflow

        Returns:
            Уникальный ID операции
        """
        prefix = 'batch-wf' if workflow_execution_id else 'batch-manual'
        suffix = uuid4().hex

        return f"{prefix}-{suffix}"
