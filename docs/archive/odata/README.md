# OData Client для 1С:Предприятие 8.3

> HTTP Client для работы с OData API 1С с connection pooling и retry logic

## Быстрый старт

### Использование ODataClient напрямую

```python
from apps.databases.odata import ODataClient

# Создать client
client = ODataClient(
    base_url="http://server/base/odata/standard.odata",
    username="Администратор",
    password="password"
)

# Health check
if client.health_check():
    print("Connection OK")

# Получить список пользователей
users = client.get_entities("Catalog_Пользователи", top=10)

# Создать пользователя
new_user = client.create_entity(
    "Catalog_Пользователи",
    {
        "Наименование": "Петров",
        "ИмяПользователя": "petrov"
    }
)

# Обновить пользователя
client.update_entity(
    "Catalog_Пользователи",
    new_user['Ref_Key'],
    {"Наименование": "Петров Иван"}
)

# Удалить пользователя
client.delete_entity("Catalog_Пользователи", new_user['Ref_Key'])

# Закрыть client
client.close()
```

### Использование SessionManager (рекомендуется)

```python
from apps.databases.odata import session_manager

# Получить client (автоматически создается или переиспользуется)
client = session_manager.get_client(
    base_id="base1",
    base_url="http://server/base1/odata/standard.odata",
    username="admin",
    password="password"
)

# Использовать client
users = client.get_entities("Catalog_Пользователи")

# SessionManager автоматически переиспользует clients
# Повторный вызов вернет тот же client instance
client2 = session_manager.get_client(
    base_id="base1",  # Тот же ID
    base_url="http://server/base1/odata/standard.odata",
    username="admin",
    password="password"
)
assert client is client2  # True - тот же объект

# Статистика
stats = session_manager.get_stats()
# {'active_clients': 1, 'total_created': 1, 'total_reused': 1, ...}

# Удалить client из пула (опционально)
session_manager.remove_client("base1")

# Или очистить весь пул
session_manager.clear_all()
```

## Архитектура

```
┌─────────────────┐
│ SessionManager  │  Singleton, Thread-safe
│   (Singleton)   │  Connection pooling
└────────┬────────┘
         │ Manages
         ▼
┌─────────────────┐
│  ODataClient    │  HTTP Client с retry logic
│   (Instance)    │  Requests.Session + HTTPAdapter
└────────┬────────┘
         │ HTTP/HTTPS
         ▼
┌─────────────────┐
│   1С OData      │  /odata/standard.odata
│      API        │
└─────────────────┘
```

## Компоненты

### 1. ODataClient

**Основной HTTP client для работы с OData.**

**Характеристики:**
- Connection pooling (requests.Session)
- Automatic retry с exponential backoff
- Comprehensive error handling
- Support для всех CRUD операций

**Методы:**
- `health_check()` - проверка доступности
- `get_entities()` - GET список
- `get_entity_by_id()` - GET одной записи
- `create_entity()` - POST создание
- `update_entity()` - PATCH обновление
- `delete_entity()` - DELETE удаление

### 2. ODataSessionManager

**Singleton менеджер пула clients.**

**Характеристики:**
- Singleton pattern (один instance на приложение)
- Thread-safe операции (Lock)
- Автоматическое переиспользование clients
- Статистика использования

**Методы:**
- `get_client()` - получить/создать client
- `remove_client()` - удалить client
- `clear_all()` - очистить весь пул
- `get_stats()` - статистика

### 3. Exceptions

**Custom исключения для error handling.**

- `ODataError` - base exception
- `ODataConnectionError` - connection failed
- `ODataAuthenticationError` - auth failed (401)
- `ODataRequestError` - HTTP error (4xx/5xx)
- `OData1CSpecificError` - 1С-specific errors (например, uniqueness)
- `ODataTimeoutError` - request timeout

### 4. Entities

**Маппинг типов сущностей 1С.**

**Типы:**
- `Catalog` - справочники
- `Document` - документы
- `InformationRegister` - регистры сведений
- `AccumulationRegister` - регистры накопления
- и т.д.

**Утилиты:**
- `get_entity_url_part()` - построить URL часть
- `parse_entity_url_part()` - распарсить URL часть

## Retry Logic

**Автоматический retry для transient errors:**

- **Max retries:** 3
- **Backoff factor:** 0.5s (0.5s, 1s, 2s)
- **Retry status codes:** 429, 500, 502, 503, 504
- **Retry methods:** GET, POST, PATCH, DELETE

**Retry на уровне requests.Session (HTTPAdapter):**
```python
retry_strategy = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504]
)
```

**Дополнительный retry на уровне методов (tenacity):**
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type((ODataConnectionError, ODataTimeoutError))
)
def _make_request(...):
    ...
```

## Error Handling

### 1С-specific errors

**Client автоматически распознает 1С ошибки:**

```python
try:
    client.create_entity("Catalog_Пользователи", {...})
except OData1CSpecificError as e:
    # 1С-specific error (например, нарушение уникальности кода)
    print(f"1С error: {e}")
except ODataRequestError as e:
    # Общая HTTP error
    print(f"HTTP {e.status_code}: {e.response_text}")
```

**Формат 1С ошибки:**
```json
{
  "odata.error": {
    "code": "",
    "message": {
      "lang": "ru",
      "value": "Элемент справочника 'Пользователи' с таким кодом уже существует"
    }
  }
}
```

## Timeouts

**По умолчанию:**
- **Connect timeout:** 5 секунд
- **Read timeout:** 30 секунд

**Custom timeout:**
```python
client = ODataClient(
    base_url="...",
    username="...",
    password="...",
    timeout=60  # 60 секунд read timeout
)
```

## Thread Safety

### ODataClient
- **НЕ thread-safe** - каждый thread должен иметь свой instance
- Session pooling встроен в requests.Session

### ODataSessionManager
- **Thread-safe** - использует Lock для всех операций
- Безопасно использовать из multiple threads

## Performance Tips

### 1. Используй SessionManager для reuse

```python
# ❌ Плохо - создает новый client каждый раз
for base in bases:
    client = ODataClient(...)
    client.get_entities(...)
    client.close()

# ✅ Хорошо - переиспользует clients
for base in bases:
    client = session_manager.get_client(base.id, ...)
    client.get_entities(...)
```

### 2. Используй $select для фильтрации полей

```python
# ❌ Плохо - получаем все поля
users = client.get_entities("Catalog_Пользователи")

# ✅ Хорошо - только нужные поля
users = client.get_entities(
    "Catalog_Пользователи",
    select_fields=["Ref_Key", "Наименование", "ИмяПользователя"]
)
```

### 3. Используй pagination для больших списков

```python
# Получить первые 100 пользователей
users = client.get_entities("Catalog_Пользователи", top=100, skip=0)

# Следующие 100
users = client.get_entities("Catalog_Пользователи", top=100, skip=100)
```

## Testing

**Базовый test с mock:**

```python
from unittest.mock import Mock, patch
from apps.databases.odata import ODataClient

@patch('apps.databases.odata.client.requests.Session')
def test_health_check(mock_session):
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.return_value.request.return_value = mock_response

    # Test
    client = ODataClient("http://test", "user", "pass")
    assert client.health_check() == True
```

## Debugging

**Включить debug logging:**

```python
import logging

# Включить логи для OData client
logging.getLogger('apps.databases.odata').setLevel(logging.DEBUG)

# Включить логи для requests
logging.getLogger('urllib3').setLevel(logging.DEBUG)
```

## Limitations

### Транзакции
- **КРИТИЧНО:** Транзакции в 1С НЕ должны превышать 15 секунд
- Разбивай длинные операции на короткие транзакции
- Используй pagination для массовых операций

### OData Version
- Client реализован для **OData v3** (1С стандарт)
- Некоторые OData v4 features могут не работать

### Batch Operations
- Текущая версия НЕ поддерживает OData $batch
- Для массовых операций используй циклы с pagination

## Roadmap

### Phase 1 (Current)
- ✅ Basic CRUD operations
- ✅ Connection pooling
- ✅ Retry logic
- ✅ Error handling

### Phase 2 (Planned)
- ⏳ OData $batch support
- ⏳ Advanced filtering ($expand, $orderby)
- ⏳ Comprehensive test coverage

### Phase 3 (Future)
- ⏳ Async support (aiohttp)
- ⏳ Query builder
- ⏳ Response caching

## Примеры использования

См. также:
- `orchestrator/apps/databases/tests/test_odata_client.py` - unit tests
- `orchestrator/apps/databases/services.py` - integration с Django models

## Лицензия

Part of CommandCenter1C project.
