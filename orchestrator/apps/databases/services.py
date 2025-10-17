"""Business logic for databases."""

import logging
from typing import Dict, List, Any
from datetime import datetime
from django.db import transaction
from django.utils import timezone

from .models import Database, DatabaseGroup
from .odata import ODataClient, session_manager, ODataError

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
        result = {
            'healthy': False,
            'response_time': 0.0,
            'error': None,
            'status_code': None
        }

        try:
            # Получаем OData client из session manager
            client = session_manager.get_client(database)

            # Выполняем health check (простой GET запрос к metadata)
            health_result = client.health_check()

            # Вычисляем время ответа
            end_time = timezone.now()
            response_time = (end_time - start_time).total_seconds()

            result.update({
                'healthy': health_result.get('healthy', False),
                'response_time': response_time,
                'status_code': health_result.get('status_code', 200)
            })

            # Обновляем информацию в базе
            with transaction.atomic():
                database.last_check = timezone.now()
                database.last_check_status = 'success'
                database.consecutive_failures = 0
                database.last_error = None

                # Обновляем среднее время ответа (простое скользящее среднее)
                if database.avg_response_time is None:
                    database.avg_response_time = response_time
                else:
                    # Взвешенное среднее: 70% старое значение + 30% новое
                    database.avg_response_time = (
                        0.7 * database.avg_response_time + 0.3 * response_time
                    )

                database.save(update_fields=[
                    'last_check',
                    'last_check_status',
                    'consecutive_failures',
                    'last_error',
                    'avg_response_time',
                    'updated_at'
                ])

            logger.info(
                f"Health check successful for {database.name}: "
                f"{response_time:.3f}s"
            )

        except ODataError as e:
            # OData-specific errors
            error_msg = str(e)
            result['error'] = error_msg

            with transaction.atomic():
                database.last_check = timezone.now()
                database.last_check_status = 'failed'
                database.consecutive_failures += 1
                database.last_error = error_msg[:500]  # Ограничиваем длину
                database.save(update_fields=[
                    'last_check',
                    'last_check_status',
                    'consecutive_failures',
                    'last_error',
                    'updated_at'
                ])

            logger.error(
                f"Health check failed for {database.name}: {error_msg}",
                exc_info=True
            )

        except Exception as e:
            # Unexpected errors
            error_msg = f"Unexpected error: {str(e)}"
            result['error'] = error_msg

            with transaction.atomic():
                database.last_check = timezone.now()
                database.last_check_status = 'failed'
                database.consecutive_failures += 1
                database.last_error = error_msg[:500]
                database.save(update_fields=[
                    'last_check',
                    'last_check_status',
                    'consecutive_failures',
                    'last_error',
                    'updated_at'
                ])

            logger.error(
                f"Unexpected error during health check for {database.name}: {error_msg}",
                exc_info=True
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
            results.append({
                'database_id': str(db.id),
                'database_name': db.name,
                **result
            })
            if result['healthy']:
                healthy_count += 1

        summary = {
            'group_name': group.name,
            'total': len(databases),
            'healthy': healthy_count,
            'unhealthy': len(databases) - healthy_count,
            'results': results
        }

        logger.info(
            f"Health check completed for group {group.name}: "
            f"{healthy_count}/{len(databases)} healthy"
        )

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
            'created': created_count,
            'failed': failed_count,
            'errors': errors
        }

        logger.info(
            f"Bulk create completed: {created_count} created, {failed_count} failed"
        )

        return result


class ODataOperationService:
    """Service for performing OData operations on 1C databases."""

    @staticmethod
    def create_entity(
        database: Database,
        entity_type: str,
        entity_name: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Создает сущность в базе 1С через OData.

        Args:
            database: Database instance
            entity_type: Тип сущности ('Catalog', 'Document', 'InformationRegister')
            entity_name: Имя сущности (например, 'Пользователи')
            data: Dict с данными для создания

        Returns:
            Dict с результатом:
            {
                'success': bool,
                'data': Dict (если success=True),
                'error': str (если success=False)
            }
        """
        logger.info(
            f"Creating entity {entity_type}_{entity_name} in database {database.name}"
        )

        result = {
            'success': False,
            'data': None,
            'error': None
        }

        try:
            # Получаем OData client
            client = session_manager.get_client(database)

            # Формируем entity set name (например: 'Catalog_Пользователи')
            entity_set = f"{entity_type}_{entity_name}"

            # Создаем сущность
            created_entity = client.create_entity(entity_set, data)

            result.update({
                'success': True,
                'data': created_entity
            })

            logger.info(
                f"Successfully created entity {entity_set} in {database.name}"
            )

        except ODataError as e:
            error_msg = str(e)
            result['error'] = error_msg
            logger.error(
                f"Failed to create entity {entity_type}_{entity_name} "
                f"in {database.name}: {error_msg}",
                exc_info=True
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            result['error'] = error_msg
            logger.error(
                f"Unexpected error creating entity in {database.name}: {error_msg}",
                exc_info=True
            )

        return result

    @staticmethod
    def get_entities(
        database: Database,
        entity_type: str,
        entity_name: str,
        filter_query: str = None
    ) -> Dict[str, Any]:
        """
        Получает список сущностей из базы 1С.

        Args:
            database: Database instance
            entity_type: Тип сущности
            entity_name: Имя сущности
            filter_query: OData $filter query (optional)

        Returns:
            Dict с результатом:
            {
                'success': bool,
                'data': List[Dict] (если success=True),
                'count': int,
                'error': str (если success=False)
            }
        """
        logger.info(
            f"Getting entities {entity_type}_{entity_name} from database {database.name}"
        )

        result = {
            'success': False,
            'data': None,
            'count': 0,
            'error': None
        }

        try:
            # Получаем OData client
            client = session_manager.get_client(database)

            # Формируем entity set name
            entity_set = f"{entity_type}_{entity_name}"

            # Получаем сущности
            params = {}
            if filter_query:
                params['$filter'] = filter_query

            entities = client.get_entities(entity_set, params=params)

            result.update({
                'success': True,
                'data': entities.get('value', []),
                'count': len(entities.get('value', []))
            })

            logger.info(
                f"Successfully retrieved {result['count']} entities "
                f"from {database.name}"
            )

        except ODataError as e:
            error_msg = str(e)
            result['error'] = error_msg
            logger.error(
                f"Failed to get entities {entity_type}_{entity_name} "
                f"from {database.name}: {error_msg}",
                exc_info=True
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            result['error'] = error_msg
            logger.error(
                f"Unexpected error getting entities from {database.name}: {error_msg}",
                exc_info=True
            )

        return result
