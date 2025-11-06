# OData Batch Operations - Детальное руководство

## Зачем использовать $batch?

**Преимущества:**
1. **Уменьшение network overhead** - один HTTP request вместо N
2. **Атомарность** - все операции в changeset либо выполняются, либо откатываются
3. **Параллельная обработка** - сервер может обрабатывать batch эффективнее
4. **Снижение нагрузки** на 1С сервер

**Когда использовать:**
- Создание/обновление > 10 объектов
- Массовые операции (100-500 records)
- Атомарные транзакции (все или ничего)

## Batch Request Structure

```http
POST http://server:port/base/odata/standard.odata/$batch HTTP/1.1
Content-Type: multipart/mixed; boundary=batch_boundary
Authorization: Basic base64(username:password)

--batch_boundary
Content-Type: multipart/mixed; boundary=changeset_boundary

--changeset_boundary
Content-Type: application/http
Content-Transfer-Encoding: binary

POST Catalog_Users HTTP/1.1
Content-Type: application/json

{
  "Description": "User 1",
  "Code": "USER001"
}

--changeset_boundary
Content-Type: application/http
Content-Transfer-Encoding: binary

POST Catalog_Users HTTP/1.1
Content-Type: application/json

{
  "Description": "User 2",
  "Code": "USER002"
}

--changeset_boundary--
--batch_boundary--
```

## Batch Example: Create Multiple Users

```python
def create_users_batch(users_data: List[Dict], batch_size: int = 100):
    """
    Создание множества пользователей через batch операции

    Args:
        users_data: List of user dictionaries
        batch_size: Размер одного batch (default 100)

    Returns:
        List of created user IDs
    """
    created_ids = []

    # Chunking для соблюдения лимита транзакций < 15s
    for chunk in chunks(users_data, batch_size):
        batch_request = create_batch_request(chunk)
        response = requests.post(
            f"{odata_url}/$batch",
            data=batch_request,
            headers={
                'Content-Type': 'multipart/mixed; boundary=batch_boundary',
                'Authorization': f'Basic {auth_token}'
            },
            timeout=15  # КРИТИЧНО: < 15 секунд!
        )

        if response.status_code == 200:
            created_ids.extend(parse_batch_response(response))
        else:
            logger.error(f"Batch failed: {response.status_code} - {response.text}")
            raise ODataBatchError(response)

    return created_ids

def create_batch_request(items: List[Dict]) -> str:
    """Создание multipart batch request"""
    boundary = "batch_" + str(uuid.uuid4())
    changeset_boundary = "changeset_" + str(uuid.uuid4())

    lines = [f"--{boundary}"]
    lines.append(f"Content-Type: multipart/mixed; boundary={changeset_boundary}")
    lines.append("")

    for item in items:
        lines.append(f"--{changeset_boundary}")
        lines.append("Content-Type: application/http")
        lines.append("Content-Transfer-Encoding: binary")
        lines.append("")
        lines.append("POST Catalog_Users HTTP/1.1")
        lines.append("Content-Type: application/json")
        lines.append("")
        lines.append(json.dumps(item))
        lines.append("")

    lines.append(f"--{changeset_boundary}--")
    lines.append(f"--{boundary}--")

    return "\r\n".join(lines)
```

## Batch Size Limits

| Операция | Рекомендуемый размер | Максимум | Причина |
|----------|---------------------|----------|---------|
| **Create** | 50-100 | 200 | Тяжелые операции с валидацией |
| **Update** | 100-200 | 500 | Средняя нагрузка |
| **Delete** | 200-500 | 1000 | Легкие операции |
| **Read** | 500-1000 | 5000 | Только чтение |

**⚠️ ВАЖНО:**
- Один batch = одна транзакция в 1С
- Транзакция ДОЛЖНА быть < 15 секунд
- При превышении лимита - разбивай на меньшие batches

## Параллельная обработка batches

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_large_dataset(items: List[Dict], batch_size: int = 100):
    """
    Параллельная обработка больших датасетов через batches

    WARNING: Не более 3-5 параллельных соединений на одну базу 1С!
    """
    batches = list(chunks(items, batch_size))
    max_workers = min(5, len(batches))  # ОГРАНИЧЕНИЕ connection pool

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {
            executor.submit(create_users_batch, batch): i
            for i, batch in enumerate(batches)
        }

        for future in as_completed(future_to_batch):
            batch_idx = future_to_batch[future]
            try:
                result = future.result()
                results.extend(result)
                logger.info(f"Batch {batch_idx} completed: {len(result)} items")
            except Exception as e:
                logger.error(f"Batch {batch_idx} failed: {e}")
                raise

    return results
```

## Error Handling в Batch Operations

```python
def parse_batch_response(response: requests.Response) -> List[str]:
    """
    Парсинг batch response с обработкой ошибок

    Batch response может содержать mix успешных и неуспешных операций!
    """
    created_ids = []
    errors = []

    # Парсинг multipart response
    content_type = response.headers['Content-Type']
    boundary = content_type.split('boundary=')[1]

    parts = response.text.split(f'--{boundary}')

    for part in parts[1:-1]:  # Skip первый и последний (пустые)
        if 'HTTP/1.1 201' in part:  # Created
            # Extract ID from Location header или response body
            match = re.search(r"guid'([^']+)'", part)
            if match:
                created_ids.append(match.group(1))
        elif 'HTTP/1.1 4' in part or 'HTTP/1.1 5' in part:  # Error
            error_match = re.search(r'"error":\s*{([^}]+)}', part)
            if error_match:
                errors.append(json.loads('{' + error_match.group(1) + '}'))

    if errors:
        logger.warning(f"Batch completed with {len(errors)} errors: {errors}")

    return created_ids
```

## Monitoring Transaction Time

```python
import time
from contextlib import contextmanager

@contextmanager
def monitor_transaction_time(operation_name: str, critical_threshold: int = 15):
    """
    Мониторинг времени выполнения транзакции

    Args:
        operation_name: Название операции для логов
        critical_threshold: Критический порог в секундах (default 15)
    """
    start_time = time.time()

    try:
        yield
    finally:
        elapsed_time = time.time() - start_time

        if elapsed_time > critical_threshold:
            logger.error(
                f"⚠️ CRITICAL: {operation_name} took {elapsed_time:.2f}s "
                f"(> {critical_threshold}s limit!)"
            )
        elif elapsed_time > critical_threshold * 0.8:
            logger.warning(
                f"WARNING: {operation_name} took {elapsed_time:.2f}s "
                f"(close to {critical_threshold}s limit)"
            )
        else:
            logger.info(f"{operation_name} completed in {elapsed_time:.2f}s")

# Usage
with monitor_transaction_time("Create 100 users batch"):
    create_users_batch(users_data, batch_size=100)
```

## Best Practices

1. **Always chunk large datasets** - не пытайся обработать 1000 records в одном batch
2. **Monitor transaction time** - используй `monitor_transaction_time` context manager
3. **Limit concurrent connections** - max 3-5 на одну базу 1С
4. **Handle partial failures** - batch может быть частично успешным
5. **Use exponential backoff** для retry при ошибках
6. **Test batch size empirically** - оптимальный размер зависит от сложности объектов

## Common Batch Errors

### Error: "Transaction timeout"

```
{
  "error": {
    "code": "TransactionTimeout",
    "message": "Транзакция превысила максимально допустимое время выполнения"
  }
}
```

**Решение:**
- Уменьши batch_size (100 → 50)
- Проверь сложность валидаций на стороне 1С
- Разбей на более мелкие chunks

### Error: "Too many concurrent connections"

```
{
  "error": {
    "code": "ConnectionPoolExhausted",
    "message": "Превышено количество одновременных подключений"
  }
}
```

**Решение:**
- Уменьши `max_workers` в ThreadPoolExecutor
- Проверь connection limits на сервере 1С
- Используй connection pooling с ограничением

### Error: "Validation failed in batch item"

```
{
  "error": {
    "code": "ValidationError",
    "message": "Ошибка заполнения реквизита 'Code'"
  }
}
```

**Решение:**
- Проверь данные перед отправкой batch
- Используй `parse_batch_response` для выявления конкретного item
- Логируй index элемента в batch для debugging

## См. также

- `transaction-patterns.md` - Паттерны для коротких транзакций
- `troubleshooting.md` - Debugging OData ошибок
- `../examples/batch-request-example.json` - Полный пример batch request
