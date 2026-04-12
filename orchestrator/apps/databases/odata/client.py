# orchestrator/apps/databases/odata/client.py
"""
OData Client для работы с 1С:Предприятие 8.3 OData API.

Поддерживает:
- CRUD операции для справочников, документов, регистров
- Connection pooling и retry logic
- Специфичный error handling для 1С
- Health checks
"""

import base64
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from .exceptions import (
    ODataConnectionError,
    ODataAuthenticationError,
    ODataRequestError,
    OData1CSpecificError,
    ODataTimeoutError
)

logger = logging.getLogger(__name__)


class ODataClient:
    """
    HTTP Client для работы с 1С OData API.

    Характеристики:
    - Connection pooling через requests.Session
    - Automatic retry с exponential backoff
    - Thread-safe (каждый instance независимый)
    - Comprehensive error handling

    Example:
        >>> client = ODataClient(
        ...     base_url="http://server/base/odata/standard.odata",
        ...     username="Администратор",
        ...     password="password"
        ... )
        >>> client.health_check()
        True
        >>> users = client.get_entities("Catalog_Пользователи")
        >>> client.close()
    """

    # Константы для retry logic
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 0.5  # 0.5s, 1s, 2s
    RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

    # Timeouts (в секундах)
    CONNECT_TIMEOUT = 5
    READ_TIMEOUT = 30

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: Optional[int] = None,
        verify_tls: bool = True,
    ):
        """
        Инициализация OData client.

        Args:
            base_url: URL OData endpoint (например, http://server/base/odata/standard.odata)
            username: Имя пользователя 1С
            password: Пароль
            timeout: Custom timeout для requests (опционально)
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.verify_tls = bool(verify_tls)
        self.timeout = (
            (self.CONNECT_TIMEOUT, timeout)
            if timeout
            else (self.CONNECT_TIMEOUT, self.READ_TIMEOUT)
        )

        # Создаем session с connection pooling
        self.session = self._create_session()

        logger.info(
            f"ODataClient initialized for {self.base_url}, user: {self.username}"
        )

    def _create_session(self) -> requests.Session:
        """
        Создать requests.Session с retry logic и connection pooling.

        Returns:
            requests.Session: Configured session
        """
        session = requests.Session()

        raw_credentials = f"{self.username}:{self.password}".encode("utf-8")
        basic_credentials = base64.b64encode(raw_credentials).decode("ascii")

        # Retry strategy
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=self.BACKOFF_FACTOR,
            status_forcelist=self.RETRY_STATUS_CODES,
            allowed_methods=["GET", "POST", "PATCH", "DELETE"]  # Retry для всех методов
        )

        # Mount adapter с retry strategy
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # Connection pool size
            pool_maxsize=20
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Default headers
        session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json;odata=nometadata',
            'User-Agent': 'CommandCenter1C-ODataClient/1.0',
            'Authorization': f'Basic {basic_credentials}',
        })

        return session

    def _build_entity_url(self, entity_name: str, entity_id: Optional[str] = None) -> str:
        """
        Построить URL для сущности.

        Args:
            entity_name: Название сущности (например, 'Catalog_Пользователи')
            entity_id: ID сущности (опционально, для GET/PATCH/DELETE конкретной записи)

        Returns:
            str: Полный URL

        Example:
            >>> self._build_entity_url("Catalog_Пользователи")
            'http://server/base/odata/standard.odata/Catalog_Пользователи'
            >>> self._build_entity_url("Catalog_Пользователи", "guid(...)")
            'http://server/base/odata/standard.odata/Catalog_Пользователи(guid'...')'
        """
        if entity_id:
            # URL-encode entity_id для безопасности
            encoded_id = quote(str(entity_id), safe='')
            url = f"{self.base_url}/{entity_name}({encoded_id})"
        else:
            url = f"{self.base_url}/{entity_name}"

        return url

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((ODataConnectionError, ODataTimeoutError)),
        reraise=True
    )
    def _make_request(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> requests.Response:
        """
        Выполнить HTTP request с error handling.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            url: Full URL
            json_data: JSON payload для POST/PATCH
            params: Query parameters для GET

        Returns:
            requests.Response: HTTP response

        Raises:
            ODataConnectionError: Не удалось подключиться
            ODataAuthenticationError: Ошибка авторизации (401)
            ODataRequestError: HTTP error (4xx, 5xx)
            ODataTimeoutError: Timeout
            OData1CSpecificError: 1С-specific error
        """
        try:
            logger.debug(f"OData request: {method} {url}")

            response = self.session.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                timeout=self.timeout,
                verify=self.verify_tls,
            )

            # Check HTTP status
            if response.status_code == 401:
                logger.error(f"Authentication failed for {self.username}")
                raise ODataAuthenticationError(
                    f"Authentication failed for user {self.username}"
                )

            if response.status_code >= 400:
                # Попробуем извлечь error message из 1С
                error_msg = self._extract_1c_error(response)

                # Проверяем на 1С-specific errors
                if "уникальность" in error_msg.lower() or "unique" in error_msg.lower():
                    logger.warning(f"1C uniqueness violation: {error_msg}")
                    raise OData1CSpecificError(error_msg)

                logger.error(
                    f"OData request failed: {response.status_code} - {error_msg}"
                )
                raise ODataRequestError(
                    message=error_msg,
                    status_code=response.status_code,
                    response_text=response.text
                )

            logger.debug(f"OData request successful: {response.status_code}")
            return response

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to {url}: {e}")
            raise ODataConnectionError(f"Failed to connect to {url}: {e}")

        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout for {url}: {e}")
            raise ODataTimeoutError(f"Request timeout for {url}: {e}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception for {url}: {e}")
            raise ODataConnectionError(f"Request failed for {url}: {e}")

    def _extract_1c_error(self, response: requests.Response) -> str:
        """
        Извлечь error message из 1С OData response.

        1С возвращает ошибки в формате:
        {
            "odata.error": {
                "code": "",
                "message": {
                    "lang": "ru",
                    "value": "Текст ошибки"
                }
            }
        }

        Args:
            response: HTTP response

        Returns:
            str: Error message
        """
        try:
            error_data = response.json()

            # Попробуем извлечь из структуры 1С
            if "odata.error" in error_data:
                message = error_data["odata.error"].get("message", {})
                if isinstance(message, dict):
                    return message.get("value", str(error_data))
                return str(message)

            # Fallback: просто вернем весь JSON
            return str(error_data)

        except Exception:
            # Если не удалось распарсить JSON, вернем raw text
            return response.text[:500]  # Ограничим длину

    def health_check(self) -> bool:
        """
        Проверить доступность OData endpoint.

        Returns:
            bool: True если endpoint доступен и авторизация работает

        Example:
            >>> client.health_check()
            True
        """
        try:
            # Простой GET запрос к root endpoint
            response = self._make_request('GET', self.base_url)
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_entities(
        self,
        entity_name: str,
        filter_query: Optional[str] = None,
        select_fields: Optional[List[str]] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить список сущностей (GET).

        Args:
            entity_name: Название сущности (например, 'Catalog_Пользователи')
            filter_query: OData $filter query (опционально)
            select_fields: Список полей для выборки (опционально)
            top: Limit записей ($top)
            skip: Offset ($skip)

        Returns:
            List[Dict]: Список сущностей

        Example:
            >>> client.get_entities(
            ...     "Catalog_Пользователи",
            ...     filter_query="Наименование eq 'Иванов'",
            ...     select_fields=["Ref_Key", "Наименование"],
            ...     top=10
            ... )
            [{'Ref_Key': 'guid...', 'Наименование': 'Иванов'}, ...]
        """
        url = self._build_entity_url(entity_name)

        # Build query parameters
        params = {}
        if filter_query:
            params['$filter'] = filter_query
        if select_fields:
            params['$select'] = ','.join(select_fields)
        if top:
            params['$top'] = top
        if skip:
            params['$skip'] = skip

        response = self._make_request('GET', url, params=params)
        data = response.json()

        # OData возвращает список в поле 'value'
        return data.get('value', [])

    def get_entity_by_id(self, entity_name: str, entity_id: str) -> Dict[str, Any]:
        """
        Получить одну сущность по ID (GET).

        Args:
            entity_name: Название сущности
            entity_id: ID сущности (обычно guid'...')

        Returns:
            Dict: Данные сущности

        Example:
            >>> client.get_entity_by_id("Catalog_Пользователи", "guid'...'")
            {'Ref_Key': 'guid...', 'Наименование': 'Иванов', ...}
        """
        url = self._build_entity_url(entity_name, entity_id)
        response = self._make_request('GET', url)
        return response.json()

    def create_entity(self, entity_name: str, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создать новую сущность (POST).

        Args:
            entity_name: Название сущности
            entity_data: Данные для создания

        Returns:
            Dict: Созданная сущность (с сгенерированным Ref_Key)

        Raises:
            OData1CSpecificError: Если нарушена уникальность кода

        Example:
            >>> client.create_entity(
            ...     "Catalog_Пользователи",
            ...     {"Наименование": "Петров", "ИмяПользователя": "petrov"}
            ... )
            {'Ref_Key': 'guid...', 'Наименование': 'Петров', ...}
        """
        url = self._build_entity_url(entity_name)
        response = self._make_request('POST', url, json_data=entity_data)
        return response.json()

    def update_entity(
        self,
        entity_name: str,
        entity_id: str,
        entity_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Обновить существующую сущность (PATCH).

        Args:
            entity_name: Название сущности
            entity_id: ID сущности
            entity_data: Данные для обновления (только измененные поля)

        Returns:
            Dict: Обновленная сущность

        Example:
            >>> client.update_entity(
            ...     "Catalog_Пользователи",
            ...     "guid'...'",
            ...     {"Наименование": "Петров Иван"}
            ... )
            {'Ref_Key': 'guid...', 'Наименование': 'Петров Иван', ...}
        """
        url = self._build_entity_url(entity_name, entity_id)
        response = self._make_request('PATCH', url, json_data=entity_data)

        # PATCH может вернуть 204 No Content
        if response.status_code == 204:
            # Если нет тела ответа, вернем входные данные
            return entity_data

        return response.json()

    def delete_entity(self, entity_name: str, entity_id: str) -> bool:
        """
        Удалить сущность (DELETE).

        Args:
            entity_name: Название сущности
            entity_id: ID сущности

        Returns:
            bool: True если удаление успешно

        Example:
            >>> client.delete_entity("Catalog_Пользователи", "guid'...'")
            True
        """
        url = self._build_entity_url(entity_name, entity_id)
        response = self._make_request('DELETE', url)

        # DELETE обычно возвращает 204 No Content
        return response.status_code in [200, 204]

    def close(self):
        """
        Закрыть session и освободить ресурсы.

        Example:
            >>> client.close()
        """
        if self.session:
            self.session.close()
            logger.info(f"ODataClient closed for {self.base_url}")

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()

    def __del__(self):
        """Cleanup при удалении объекта."""
        self.close()
