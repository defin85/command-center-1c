from __future__ import annotations

import logging
from typing import Any, Dict

from ..models import Database
from ..odata import ODataError, session_manager

logger = logging.getLogger(__name__)


class ODataOperationService:
    """Service for performing OData operations on 1C databases."""

    @staticmethod
    def create_entity(
        database: Database,
        entity_type: str,
        entity_name: str,
        data: Dict[str, Any],
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
        logger.info(f"Creating entity {entity_type}_{entity_name} in database {database.name}")

        result = {
            "success": False,
            "data": None,
            "error": None,
        }

        try:
            # Получаем OData client
            client = session_manager.get_client(database)

            # Формируем entity set name (например: 'Catalog_Пользователи')
            entity_set = f"{entity_type}_{entity_name}"

            # Создаем сущность
            created_entity = client.create_entity(entity_set, data)

            result.update(
                {
                    "success": True,
                    "data": created_entity,
                }
            )

            logger.info(f"Successfully created entity {entity_set} in {database.name}")

        except ODataError as e:
            error_msg = str(e)
            result["error"] = error_msg
            logger.error(
                f"Failed to create entity {entity_type}_{entity_name} " f"in {database.name}: {error_msg}",
                exc_info=True,
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            result["error"] = error_msg
            logger.error(
                f"Unexpected error creating entity in {database.name}: {error_msg}",
                exc_info=True,
            )

        return result

    @staticmethod
    def get_entities(
        database: Database,
        entity_type: str,
        entity_name: str,
        filter_query: str = None,
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
        logger.info(f"Getting entities {entity_type}_{entity_name} from database {database.name}")

        result = {
            "success": False,
            "data": None,
            "count": 0,
            "error": None,
        }

        try:
            # Получаем OData client
            client = session_manager.get_client(database)

            # Формируем entity set name
            entity_set = f"{entity_type}_{entity_name}"

            # Получаем сущности
            params = {}
            if filter_query:
                params["$filter"] = filter_query

            entities = client.get_entities(entity_set, params=params)

            result.update(
                {
                    "success": True,
                    "data": entities.get("value", []),
                    "count": len(entities.get("value", [])),
                }
            )

            logger.info(f"Successfully retrieved {result['count']} entities " f"from {database.name}")

        except ODataError as e:
            error_msg = str(e)
            result["error"] = error_msg
            logger.error(
                f"Failed to get entities {entity_type}_{entity_name} " f"from {database.name}: {error_msg}",
                exc_info=True,
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            result["error"] = error_msg
            logger.error(
                f"Unexpected error getting entities from {database.name}: {error_msg}",
                exc_info=True,
            )

        return result

