---
name: cc1c-odata-integration
description: "Work with 1C databases via OData protocol: create batch operations, handle transactions (< 15 seconds!), debug OData requests, implement mass data operations. Use when working with 1C integration, OData, batch operations, or when user mentions 1C databases, справочники, документы."
allowed-tools: ["Read", "Write", "Edit"]
---

# cc1c-odata-integration

## Purpose

Обеспечить правильную работу с базами 1С через OData протокол, соблюдая критические ограничения и best practices для массовых операций.

## When to Use

Используй этот skill когда:
- Работа с 1С через OData
- Создание batch операций
- Массовые операции с данными в 1С
- Debugging OData requests/responses
- Пользователь упоминает: OData, 1C, batch, справочники, документы, транзакции, $batch

## ⚠️ КРИТИЧЕСКОЕ ОГРАНИЧЕНИЕ

### Транзакции 1С < 15 секунд!

**Это НЕ рекомендация - это ЖЕСТКОЕ ОГРАНИЧЕНИЕ платформы 1С!**

**Почему важно:**
- Транзакция > 15 секунд = automatic rollback
- Блокировка других пользователей
- Риск data corruption
- Снижение производительности всей системы 1С

**Как соблюдать:**
1. **Разбивай длинные операции** на короткие транзакции
2. **Batch size ограничен** - не более 50-100 объектов в одном batch
3. **Один цикл = одна транзакция** для массовых операций
4. **Мониторь время выполнения** каждой транзакции
5. **Используй chunking** для больших объемов данных

## OData Basics для 1С

### 1. OData Endpoint Structure

```
http://{server}:{port}/{base_name}/odata/standard.odata/
```

**Примеры:**
```
http://localhost/accounting/odata/standard.odata/
http://192.168.1.100:8080/accounting_test/odata/standard.odata/
```

### 2. Authentication

1С поддерживает Basic Authentication:
```python
import requests
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth('username', 'password')
response = requests.get(url, auth=auth)
```

### 3. Metadata

Получить структуру данных:
```
GET http://server/base/odata/standard.odata/$metadata
```

Это вернет XML с описанием всех Entity Sets.

## OData Entity Names в 1С

### Naming Convention

1С использует специальный формат для имен:
- `Catalog_` + название справочника
- `Document_` + название документа
- `InformationRegister_` + название регистра
- `AccumulationRegister_` + название регистра

**Важно:** Русские названия заменяются на английские транслитерацией или специальными именами.

### Common Entity Examples

```
Справочники:
- Catalog_Users                   (Справочники.Пользователи)
- Catalog_Counterparties          (Справочники.Контрагенты)
- Catalog_Organizations           (Справочники.Организации)
- Catalog_Nomenclature            (Справочники.Номенклатура)

Документы:
- Document_SalesInvoice           (Документы.РеализацияТоваровУслуг)
- Document_PurchaseInvoice        (Документы.ПоступлениеТоваровУслуг)
- Document_PaymentOrder           (Документы.ПлатежноеПоручение)

Регистры:
- InformationRegister_Settings    (РегистрыСведений.Настройки)
- AccumulationRegister_Sales      (РегистрыНакопления.Продажи)
```

## OData Operations

### 1. Получение списка (GET Collection)

```python
# Get all items
response = requests.get(
    f"{base_url}/Catalog_Users",
    auth=auth
)

# With filters
response = requests.get(
    f"{base_url}/Catalog_Users?$filter=IsActive eq true",
    auth=auth
)

# With select (specific fields)
response = requests.get(
    f"{base_url}/Catalog_Users?$select=Code,Description",
    auth=auth
)

# With top/skip (pagination)
response = requests.get(
    f"{base_url}/Catalog_Users?$top=100&$skip=0",
    auth=auth
)
```

### 2. Получение одного объекта (GET Single)

```python
# By GUID
user_guid = "550e8400-e29b-41d4-a716-446655440000"
response = requests.get(
    f"{base_url}/Catalog_Users(guid'{user_guid}')",
    auth=auth
)
```

### 3. Создание объекта (POST)

```python
new_user = {
    "Code": "USER001",
    "Description": "Иванов Иван Иванович",
    "IsActive": True
}

response = requests.post(
    f"{base_url}/Catalog_Users",
    json=new_user,
    auth=auth
)
```

### 4. Обновление объекта (PATCH)

```python
user_guid = "550e8400-e29b-41d4-a716-446655440000"
update_data = {
    "Description": "Иванов И.И. (обновлено)",
    "IsActive": False
}

response = requests.patch(
    f"{base_url}/Catalog_Users(guid'{user_guid}')",
    json=update_data,
    auth=auth
)
```

### 5. Удаление объекта (DELETE)

```python
user_guid = "550e8400-e29b-41d4-a716-446655440000"

response = requests.delete(
    f"{base_url}/Catalog_Users(guid'{user_guid}')",
    auth=auth
)
```

## Batch Operations (КРИТИЧНО для массовых операций)

### Зачем использовать $batch?

1. **Снижение network overhead** - один HTTP request вместо сотен
2. **Атомарность** - все операции в одной транзакции
3. **Производительность** - 1С обрабатывает batch эффективнее

### Batch Request Structure

```python
import uuid
import requests

def create_batch_request(operations, base_url, auth):
    """
    Создает OData $batch request

    Args:
        operations: Список операций для выполнения
        base_url: Base URL для OData endpoint
        auth: Authentication object

    Returns:
        Response object
    """
    # Generate unique boundary
    boundary = f"batch_{uuid.uuid4()}"

    # Build batch body
    batch_body = []

    for idx, op in enumerate(operations):
        batch_body.append(f"--{boundary}")
        batch_body.append("Content-Type: application/http")
        batch_body.append("Content-Transfer-Encoding: binary")
        batch_body.append("")

        # HTTP method and URL
        batch_body.append(f"{op['method']} {op['url']} HTTP/1.1")
        batch_body.append("Content-Type: application/json")
        batch_body.append("")

        # Body (if present)
        if 'body' in op:
            batch_body.append(json.dumps(op['body']))

        batch_body.append("")

    # End boundary
    batch_body.append(f"--{boundary}--")

    # Join with CRLF
    batch_content = "\r\n".join(batch_body)

    # Send request
    headers = {
        "Content-Type": f"multipart/mixed; boundary={boundary}"
    }

    response = requests.post(
        f"{base_url}/$batch",
        data=batch_content,
        headers=headers,
        auth=auth
    )

    return response
```

### Batch Example: Create Multiple Users

```python
operations = [
    {
        'method': 'POST',
        'url': 'Catalog_Users',
        'body': {
            'Code': 'USER001',
            'Description': 'Иванов И.И.'
        }
    },
    {
        'method': 'POST',
        'url': 'Catalog_Users',
        'body': {
            'Code': 'USER002',
            'Description': 'Петров П.П.'
        }
    }
]

response = create_batch_request(operations, base_url, auth)
```

### ⚠️ Batch Size Limits

**Критично соблюдать:**
- **Максимум 50-100 операций** в одном batch
- **Время выполнения < 15 секунд**
- Для большего объема - разбивай на несколько batch requests

```python
def process_large_dataset(items, batch_size=50):
    """
    Обрабатывает большой датасет с chunking

    Соблюдает ограничение транзакций < 15 секунд
    """
    chunks = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

    results = []
    for chunk_idx, chunk in enumerate(chunks):
        print(f"Processing chunk {chunk_idx + 1}/{len(chunks)}")

        operations = []
        for item in chunk:
            operations.append({
                'method': 'POST',
                'url': 'Catalog_Users',
                'body': item
            })

        response = create_batch_request(operations, base_url, auth)
        results.append(response)

        # Optional: small delay between chunks
        time.sleep(0.5)

    return results
```

## OneCODataAdapter Class

### Implementation Example

```python
import requests
from requests.auth import HTTPBasicAuth
import logging

logger = logging.getLogger(__name__)


class OneCODataAdapter:
    """
    Adapter для работы с 1С через OData

    Особенности:
    - Соблюдает ограничение транзакций < 15 секунд
    - Автоматический chunking для больших операций
    - Retry logic для temporary failures
    - Детальное логирование
    """

    def __init__(self, base_url: str, username: str, password: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = self.auth

    def get_metadata(self):
        """Получить metadata"""
        url = f"{self.base_url}/$metadata"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def get_collection(self, entity: str, filters: dict = None, select: list = None,
                      top: int = None, skip: int = None):
        """
        Получить коллекцию объектов

        Args:
            entity: Имя entity (e.g., 'Catalog_Users')
            filters: Словарь с фильтрами
            select: Список полей для выборки
            top: Количество записей
            skip: Пропустить записей
        """
        url = f"{self.base_url}/{entity}"
        params = {}

        if filters:
            filter_str = " and ".join([f"{k} eq '{v}'" for k, v in filters.items()])
            params['$filter'] = filter_str

        if select:
            params['$select'] = ",".join(select)

        if top:
            params['$top'] = top

        if skip:
            params['$skip'] = skip

        logger.info(f"GET {entity} with params: {params}")
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_single(self, entity: str, guid: str):
        """Получить один объект по GUID"""
        url = f"{self.base_url}/{entity}(guid'{guid}')"
        logger.info(f"GET single {entity}: {guid}")
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def create(self, entity: str, data: dict):
        """Создать объект"""
        url = f"{self.base_url}/{entity}"
        logger.info(f"POST {entity}: {data}")
        response = self.session.post(url, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def update(self, entity: str, guid: str, data: dict):
        """Обновить объект"""
        url = f"{self.base_url}/{entity}(guid'{guid}')"
        logger.info(f"PATCH {entity} {guid}: {data}")
        response = self.session.patch(url, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def delete(self, entity: str, guid: str):
        """Удалить объект"""
        url = f"{self.base_url}/{entity}(guid'{guid}')"
        logger.info(f"DELETE {entity}: {guid}")
        response = self.session.delete(url, timeout=self.timeout)
        response.raise_for_status()

    def batch_operation(self, operations: list, max_batch_size: int = 50):
        """
        Выполнить batch операции

        ⚠️ КРИТИЧНО: Автоматически разбивает на chunks если > max_batch_size

        Args:
            operations: Список операций
            max_batch_size: Максимальный размер одного batch (по умолчанию 50)

        Returns:
            Список результатов
        """
        if len(operations) > max_batch_size:
            logger.warning(
                f"Operations count ({len(operations)}) exceeds max batch size ({max_batch_size}). "
                f"Will split into multiple batches."
            )

            # Split into chunks
            chunks = [
                operations[i:i + max_batch_size]
                for i in range(0, len(operations), max_batch_size)
            ]

            results = []
            for idx, chunk in enumerate(chunks):
                logger.info(f"Processing batch {idx + 1}/{len(chunks)}")
                result = self._execute_batch(chunk)
                results.append(result)

            return results
        else:
            return [self._execute_batch(operations)]

    def _execute_batch(self, operations: list):
        """Выполнить один batch request"""
        import uuid

        boundary = f"batch_{uuid.uuid4()}"
        batch_body = []

        for op in operations:
            batch_body.append(f"--{boundary}")
            batch_body.append("Content-Type: application/http")
            batch_body.append("Content-Transfer-Encoding: binary")
            batch_body.append("")
            batch_body.append(f"{op['method']} {op['url']} HTTP/1.1")
            batch_body.append("Content-Type: application/json")
            batch_body.append("")

            if 'body' in op:
                import json
                batch_body.append(json.dumps(op['body']))

            batch_body.append("")

        batch_body.append(f"--{boundary}--")
        batch_content = "\r\n".join(batch_body)

        headers = {
            "Content-Type": f"multipart/mixed; boundary={boundary}"
        }

        url = f"{self.base_url}/$batch"
        logger.info(f"Executing batch with {len(operations)} operations")

        response = self.session.post(
            url,
            data=batch_content,
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.text
```

### Usage Example

```python
# Initialize adapter
adapter = OneCODataAdapter(
    base_url="http://localhost/accounting/odata/standard.odata",
    username="admin",
    password="password"
)

# Get users
users = adapter.get_collection(
    entity="Catalog_Users",
    filters={"IsActive": True},
    select=["Code", "Description"],
    top=100
)

# Create user
new_user = adapter.create(
    entity="Catalog_Users",
    data={
        "Code": "USER001",
        "Description": "Иванов И.И."
    }
)

# Batch create (automatically chunks if needed)
operations = [
    {
        'method': 'POST',
        'url': 'Catalog_Users',
        'body': {'Code': f'USER{i:03d}', 'Description': f'User {i}'}
    }
    for i in range(1, 201)  # 200 users - will be split into 4 batches
]

results = adapter.batch_operation(operations, max_batch_size=50)
```

## Debugging OData Requests

### 1. Включи подробное логирование

```python
import logging

# Enable debug logging for requests
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('urllib3').setLevel(logging.DEBUG)
```

### 2. Проверь response status

```python
response = requests.get(url, auth=auth)

print(f"Status: {response.status_code}")
print(f"Headers: {response.headers}")
print(f"Body: {response.text}")
```

### 3. Common Error Codes

```
200 OK          - Success
201 Created     - Object created
204 No Content  - Delete successful
400 Bad Request - Invalid data format
401 Unauthorized - Auth failed
404 Not Found   - Entity or object not found
500 Internal Server Error - 1C internal error
```

### 4. Тестирование через curl

```bash
# Get metadata
curl -u username:password \
  "http://localhost/base/odata/standard.odata/\$metadata"

# Get collection
curl -u username:password \
  "http://localhost/base/odata/standard.odata/Catalog_Users"

# Create object
curl -u username:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"Code":"USER001","Description":"Test User"}' \
  "http://localhost/base/odata/standard.odata/Catalog_Users"
```

## Best Practices

### 1. Always Use Chunking for Large Operations

```python
def safe_batch_operation(items, entity, operation='POST'):
    """
    Безопасная batch операция с соблюдением всех ограничений
    """
    BATCH_SIZE = 50  # Максимум 50 операций в batch

    for i in range(0, len(items), BATCH_SIZE):
        chunk = items[i:i + BATCH_SIZE]

        operations = [
            {
                'method': operation,
                'url': entity,
                'body': item
            }
            for item in chunk
        ]

        # Execute batch
        result = adapter.batch_operation(operations)

        # Log progress
        logger.info(f"Processed {min(i + BATCH_SIZE, len(items))}/{len(items)}")
```

### 2. Monitor Transaction Time

```python
import time

def timed_batch_operation(operations):
    """Операция с мониторингом времени"""
    start_time = time.time()

    result = adapter.batch_operation(operations)

    elapsed = time.time() - start_time

    if elapsed > 10:
        logger.warning(f"Transaction took {elapsed:.2f}s - approaching 15s limit!")

    return result
```

### 3. Error Handling

```python
def robust_batch_operation(operations, max_retries=3):
    """Batch операция с retry logic"""
    for attempt in range(max_retries):
        try:
            return adapter.batch_operation(operations)
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            if attempt == max_retries - 1:
                raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 500:
                # Server error - retry
                logger.warning(f"Server error on attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise
            else:
                # Client error - don't retry
                raise
```

## Testing

### Integration Test Example

```python
import pytest
from unittest.mock import Mock, patch

def test_batch_operation_chunking():
    """Тест что batch правильно разбивается на chunks"""
    adapter = OneCODataAdapter(
        base_url="http://test",
        username="test",
        password="test"
    )

    # Create 150 operations (should be split into 3 chunks of 50)
    operations = [
        {
            'method': 'POST',
            'url': 'Catalog_Users',
            'body': {'Code': f'USER{i:03d}'}
        }
        for i in range(150)
    ]

    with patch.object(adapter, '_execute_batch') as mock_execute:
        mock_execute.return_value = "OK"

        results = adapter.batch_operation(operations, max_batch_size=50)

        # Should call _execute_batch 3 times
        assert mock_execute.call_count == 3

        # Each call should have 50 operations
        for call in mock_execute.call_args_list:
            assert len(call[0][0]) == 50
```

## References

- OData examples: `.claude/skills/cc1c-odata-integration/odata-examples.py`
- OData specification: https://www.odata.org/documentation/
- 1C OData docs: https://its.1c.ru/db/v83doc#bookmark:dev:TI000001472
- Project conventions: `CLAUDE.md`

## Related Skills

При работе с OData также используй:
- `cc1c-service-builder` - для создания новых операций с 1С
- `cc1c-test-runner` - для тестирования OData интеграций
- `cc1c-devops` - для отладки connection issues
- `cc1c-navigator` - для поиска существующих OData адаптеров

---

**Version:** 1.0
**Last Updated:** 2025-01-17
**Changelog:**
- 1.0 (2025-01-17): Initial release with OneCODataAdapter and batch operations examples
