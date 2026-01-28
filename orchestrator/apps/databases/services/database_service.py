from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from ..models import Database, DatabaseGroup
from ..odata import ODataError, session_manager

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for managing databases and performing health checks."""

    @staticmethod
    def health_check_database(database: Database) -> Dict[str, Any]:
        """
        Выполняет health check одной базы 1С.

        Args:
            database: Database instance для проверки

        Returns:
            Dict с результатами health check:
            {
                'healthy': bool,
                'response_time': float,
                'error': str (если есть),
                'status_code': int
            }
        """
        logger.info(f"Starting health check for database: {database.name}")

        start_time = timezone.now()
        result: Dict[str, Any] = {
            "healthy": False,
            "response_time": 0.0,
            "error": None,
            "status_code": None,
        }

        try:
            # Получаем OData client из session manager
            client = session_manager.get_client(
                base_id=str(database.id),
                base_url=database.odata_url,
                username=database.username,
                password=database.password,
                timeout=database.connection_timeout,
            )

            # Выполняем health check (простой GET запрос к metadata)
            health_result = client.health_check()

            is_healthy = False
            status_code: Optional[int] = None
            if isinstance(health_result, dict):
                is_healthy = bool(health_result.get("healthy"))
                status_code = health_result.get("status_code")
            else:
                is_healthy = bool(health_result)

            if status_code is None:
                status_code = 200 if is_healthy else 500

            # Вычисляем время ответа
            end_time = timezone.now()
            response_time = (end_time - start_time).total_seconds() * 1000  # Convert to milliseconds

            result.update(
                {
                    "healthy": is_healthy,
                    "response_time": response_time,
                    "status_code": status_code,
                }
            )

            # Используем существующий метод вместо дублирования
            database.mark_health_check(
                success=is_healthy,
                response_time=response_time,
            )

            if is_healthy:
                logger.info(
                    f"Database {database.name} health check: OK " f"(response_time={response_time:.3f}ms)"
                )
            else:
                logger.warning(
                    f"Database {database.name} health check: FAILED " f"(response_time={response_time:.3f}ms)"
                )

        except ODataError as e:
            # OData-specific errors
            error_msg = str(e)
            result["error"] = error_msg

            database.mark_health_check(
                success=False,
                response_time=None,
            )

            logger.warning(
                f"Database {database.name} health check: FAILED " f"(ODataError: {error_msg})"
            )

        except Exception as e:
            # Unexpected errors
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            result["error"] = error_msg

            database.mark_health_check(
                success=False,
                response_time=None,
            )

            logger.error(
                f"Database {database.name} health check: ERROR " f"({error_msg})",
                exc_info=True,
            )

        return result

    @staticmethod
    def health_check_group(group: DatabaseGroup) -> Dict[str, Any]:
        """
        Выполняет health check для всех баз в группе.

        Args:
            group: DatabaseGroup instance

        Returns:
            Dict с агрегированными результатами:
            {
                'total': int,
                'healthy': int,
                'unhealthy': int,
                'results': List[Dict]
            }
        """
        logger.info(f"Starting health check for group: {group.name}")

        databases = group.databases.all()
        results = []
        healthy_count = 0

        for db in databases:
            result = DatabaseService.health_check_database(db)
            results.append(
                {
                    "database_id": str(db.id),
                    "database_name": db.name,
                    **result,
                }
            )
            if result["healthy"]:
                healthy_count += 1

        summary = {
            "group_name": group.name,
            "total": len(databases),
            "healthy": healthy_count,
            "unhealthy": len(databases) - healthy_count,
            "results": results,
        }

        logger.info(f"Health check completed for group {group.name}: " f"{healthy_count}/{len(databases)} healthy")

        return summary

    @staticmethod
    def bulk_create_databases(databases_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Массовое создание баз данных.

        Args:
            databases_data: List of dicts с данными для создания баз

        Returns:
            Dict с результатами:
            {
                'created': int,
                'failed': int,
                'errors': List[str]
            }
        """
        logger.info(f"Starting bulk create for {len(databases_data)} databases")

        created_count = 0
        failed_count = 0
        errors = []

        for db_data in databases_data:
            try:
                with transaction.atomic():
                    database = Database.objects.create(**db_data)
                    created_count += 1
                    logger.info(f"Created database: {database.name}")
            except Exception as e:
                failed_count += 1
                error_msg = f"Failed to create database {db_data.get('name', 'unknown')}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        result = {
            "created": created_count,
            "failed": failed_count,
            "errors": errors,
        }

        logger.info(f"Bulk create completed: {created_count} created, {failed_count} failed")

        return result

