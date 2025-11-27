"""
ResultWaiter - ожидание результатов операции (SYNC режим).

Используется WorkflowEngine для синхронного ожидания завершения операций.
"""
import logging
import time
from typing import Any, Dict, List

from django.db import connection

from apps.operations.models import BatchOperation, Task

logger = logging.getLogger(__name__)


class OperationTimeoutError(Exception):
    """Raised when operation execution exceeds timeout."""

    def __init__(self, operation_id: str, timeout_seconds: int):
        self.operation_id = operation_id
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Operation {operation_id} did not complete within {timeout_seconds} seconds"
        )


class ResultWaiter:
    """
    Ожидание результатов операции (SYNC режим).

    Используется для синхронного ожидания завершения BatchOperation
    путем polling статуса в базе данных.
    """

    # Terminal statuses - operation is finished
    TERMINAL_STATUSES = frozenset([
        BatchOperation.STATUS_COMPLETED,
        BatchOperation.STATUS_FAILED,
        BatchOperation.STATUS_CANCELLED,
    ])

    @classmethod
    def wait(
        cls,
        operation_id: str,
        timeout_seconds: int = 300,
        poll_interval_seconds: float = 0.5
    ) -> Dict[str, Any]:
        """
        Ожидает завершения операции.

        Алгоритм:
        1. Polling BatchOperation.status в DB каждые poll_interval_seconds
        2. Если status in (completed, failed, cancelled) -> вернуть результат
        3. Если timeout -> raise OperationTimeoutError

        Args:
            operation_id: ID операции для ожидания
            timeout_seconds: Максимальное время ожидания (по умолчанию 5 минут)
            poll_interval_seconds: Интервал между проверками (по умолчанию 0.5 сек)

        Returns:
            {
                'success': bool,
                'status': str,
                'results': List[Dict],  # результаты по Task'ам
                'error': Optional[str],
                'progress': int,
                'duration_seconds': Optional[float]
            }

        Raises:
            OperationTimeoutError: Если операция не завершилась за timeout_seconds
            BatchOperation.DoesNotExist: Если операция не найдена
        """
        start_time = time.time()
        elapsed = 0.0

        logger.info(
            f"Waiting for operation {operation_id} to complete",
            extra={
                'operation_id': operation_id,
                'timeout_seconds': timeout_seconds,
                'poll_interval_seconds': poll_interval_seconds
            }
        )

        while elapsed < timeout_seconds:
            # Close old DB connections to get fresh data
            connection.close_if_unusable_or_obsolete()

            try:
                # Fetch operation from DB
                operation = BatchOperation.objects.get(id=operation_id)
            except BatchOperation.DoesNotExist:
                logger.error(f"Operation {operation_id} not found during wait")
                raise

            # Check if operation is in terminal state
            if operation.status in cls.TERMINAL_STATUSES:
                result = cls._build_result(operation)

                logger.info(
                    f"Operation {operation_id} completed with status {operation.status}",
                    extra={
                        'operation_id': operation_id,
                        'status': operation.status,
                        'success': result['success'],
                        'wait_duration_seconds': elapsed
                    }
                )

                return result

            # Log progress periodically (every 5 seconds)
            if int(elapsed) % 5 == 0 and elapsed > 0:
                logger.debug(
                    f"Operation {operation_id} still in progress",
                    extra={
                        'operation_id': operation_id,
                        'status': operation.status,
                        'progress': operation.progress,
                        'elapsed_seconds': elapsed
                    }
                )

            # Wait before next poll
            time.sleep(poll_interval_seconds)
            elapsed = time.time() - start_time

        # Timeout reached
        logger.error(
            f"Operation {operation_id} timed out after {timeout_seconds} seconds",
            extra={
                'operation_id': operation_id,
                'timeout_seconds': timeout_seconds
            }
        )

        raise OperationTimeoutError(
            operation_id=operation_id,
            timeout_seconds=timeout_seconds
        )

    @classmethod
    def _build_result(cls, operation: BatchOperation) -> Dict[str, Any]:
        """
        Строит результат из BatchOperation.

        Args:
            operation: BatchOperation instance

        Returns:
            Словарь с результатами операции
        """
        # Determine success
        success = operation.status == BatchOperation.STATUS_COMPLETED

        # Collect task results
        task_results = cls._collect_task_results(operation)

        # Build error message if failed
        error = None
        if operation.status == BatchOperation.STATUS_FAILED:
            failed_tasks = [t for t in task_results if not t.get('success', False)]
            if failed_tasks:
                error_messages = [t.get('error', 'Unknown error') for t in failed_tasks]
                error = "; ".join(set(error_messages))  # Unique errors
            else:
                error = "Operation failed with unknown error"
        elif operation.status == BatchOperation.STATUS_CANCELLED:
            error = "Operation was cancelled"

        return {
            'success': success,
            'status': operation.status,
            'results': task_results,
            'error': error,
            'progress': operation.progress,
            'duration_seconds': operation.duration_seconds,
            'statistics': {
                'total_tasks': operation.total_tasks,
                'completed_tasks': operation.completed_tasks,
                'failed_tasks': operation.failed_tasks,
                'success_rate': operation.success_rate
            }
        }

    @classmethod
    def _collect_task_results(cls, operation: BatchOperation) -> List[Dict[str, Any]]:
        """
        Собирает результаты всех Task операции.

        Args:
            operation: BatchOperation instance

        Returns:
            Список результатов по каждому Task
        """
        results = []

        for task in operation.tasks.select_related('database').all():
            task_result = {
                'task_id': task.id,
                'database_id': str(task.database.id),
                'database_name': task.database.name,
                'success': task.status == Task.STATUS_COMPLETED,
                'status': task.status,
                'duration_seconds': task.duration_seconds,
            }

            if task.result:
                task_result['data'] = task.result

            if task.error_message:
                task_result['error'] = task.error_message
                task_result['error_code'] = task.error_code or 'UNKNOWN_ERROR'

            results.append(task_result)

        return results

    @classmethod
    def check_status(cls, operation_id: str) -> Dict[str, Any]:
        """
        Проверяет текущий статус операции без ожидания.

        Args:
            operation_id: ID операции

        Returns:
            Словарь со статусом и прогрессом

        Raises:
            BatchOperation.DoesNotExist: Если операция не найдена
        """
        operation = BatchOperation.objects.get(id=operation_id)

        return {
            'operation_id': operation_id,
            'status': operation.status,
            'progress': operation.progress,
            'is_terminal': operation.status in cls.TERMINAL_STATUSES,
            'statistics': {
                'total_tasks': operation.total_tasks,
                'completed_tasks': operation.completed_tasks,
                'failed_tasks': operation.failed_tasks,
            }
        }
