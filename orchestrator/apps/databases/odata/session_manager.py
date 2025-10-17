# orchestrator/apps/databases/odata/session_manager.py
"""
Session Manager для пула OData clients.

Реализует:
- Singleton pattern для global instance
- Thread-safe операции
- Connection pooling (reuse clients для одной базы)
- Статистика использования
"""

import logging
import threading
from typing import Dict, Optional

from .client import ODataClient

logger = logging.getLogger(__name__)


class ODataSessionManager:
    """
    Singleton менеджер для пула OData clients.

    Характеристики:
    - Один client на базу (reuse для efficiency)
    - Thread-safe через Lock
    - Автоматическое создание clients по требованию
    - Статистика использования

    Example:
        >>> manager = ODataSessionManager()
        >>> client = manager.get_client("base1", "http://...", "user", "pass")
        >>> # ... используем client
        >>> manager.remove_client("base1")  # Опционально
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern - только один instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Инициализация пула."""
        # Избегаем повторной инициализации для Singleton
        if not hasattr(self, '_initialized'):
            self._clients: Dict[str, ODataClient] = {}
            self._client_lock = threading.Lock()
            self._stats = {
                'total_created': 0,
                'total_reused': 0,
                'total_removed': 0
            }
            self._initialized = True
            logger.info("ODataSessionManager initialized")

    def get_client(
        self,
        base_id: str,
        base_url: str,
        username: str,
        password: str,
        timeout: Optional[int] = None
    ) -> ODataClient:
        """
        Получить или создать OData client для базы.

        Args:
            base_id: Уникальный ID базы
            base_url: OData endpoint URL
            username: Имя пользователя
            password: Пароль
            timeout: Custom timeout (опционально)

        Returns:
            ODataClient: Existing или новый client

        Example:
            >>> manager = ODataSessionManager()
            >>> client = manager.get_client(
            ...     "base1",
            ...     "http://server/base1/odata/standard.odata",
            ...     "admin",
            ...     "password"
            ... )
        """
        with self._client_lock:
            # Проверяем есть ли уже client для этой базы
            if base_id in self._clients:
                logger.debug(f"Reusing existing OData client for base: {base_id}")
                self._stats['total_reused'] += 1
                return self._clients[base_id]

            # Создаем новый client
            logger.info(f"Creating new OData client for base: {base_id}")
            client = ODataClient(
                base_url=base_url,
                username=username,
                password=password,
                timeout=timeout
            )

            self._clients[base_id] = client
            self._stats['total_created'] += 1

            return client

    def remove_client(self, base_id: str) -> bool:
        """
        Удалить client из пула и закрыть его.

        Args:
            base_id: ID базы

        Returns:
            bool: True если client был удален

        Example:
            >>> manager.remove_client("base1")
            True
        """
        with self._client_lock:
            if base_id in self._clients:
                client = self._clients.pop(base_id)
                client.close()
                self._stats['total_removed'] += 1
                logger.info(f"Removed OData client for base: {base_id}")
                return True

            logger.warning(f"No OData client found for base: {base_id}")
            return False

    def clear_all(self):
        """
        Удалить все clients из пула.

        Example:
            >>> manager.clear_all()
        """
        with self._client_lock:
            logger.info(f"Clearing all OData clients ({len(self._clients)} total)")

            for base_id, client in self._clients.items():
                try:
                    client.close()
                except Exception as e:
                    logger.error(f"Error closing client for {base_id}: {e}")

            count = len(self._clients)
            self._clients.clear()
            self._stats['total_removed'] += count

            logger.info("All OData clients cleared")

    def get_stats(self) -> Dict:
        """
        Получить статистику использования пула.

        Returns:
            dict: {
                'active_clients': int,
                'total_created': int,
                'total_reused': int,
                'total_removed': int
            }

        Example:
            >>> manager.get_stats()
            {
                'active_clients': 5,
                'total_created': 10,
                'total_reused': 50,
                'total_removed': 5
            }
        """
        with self._client_lock:
            return {
                'active_clients': len(self._clients),
                'total_created': self._stats['total_created'],
                'total_reused': self._stats['total_reused'],
                'total_removed': self._stats['total_removed']
            }

    def __del__(self):
        """Cleanup при удалении manager."""
        self.clear_all()


# Global singleton instance
session_manager = ODataSessionManager()
