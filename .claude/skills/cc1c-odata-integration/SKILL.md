---
name: cc1c-odata-integration
description: "Work with 1C databases via OData protocol: create batch operations, handle transactions (< 15 seconds!), debug OData requests."
allowed-tools: ["Read", "Write", "Edit"]
---

# cc1c-odata-integration

## Purpose

Обеспечить правильную работу с базами 1С через OData протокол, соблюдая критические ограничения (транзакции < 15s) и best practices.

## When to Use

Используй этот skill когда пользователь:
- Работает с 1С через OData
- Создает batch операции для массовых данных
- Реализует CRUD операции с данными 1С
- Debugging OData requests/responses/errors
- Оптимизирует производительность OData запросов
- Упоминает: OData, $batch, справочники, документы, транзакции, chunking
- Сталкивается с timeout или performance issues

## ⚠️ КРИТИЧЕСКОЕ ОГРАНИЧЕНИЕ

### Транзакции 1С < 15 секунд!

**Это ЖЕСТКОЕ ОГРАНИЧЕНИЕ платформы 1С, НЕ рекомендация!**

**Последствия при превышении:**
- Automatic rollback транзакции
- Блокировка других пользователей (deadlocks)
- Риск data corruption
- Снижение производительности всей системы

**Как соблюдать:**
1. Разбивай длинные операции на chunks (50-200 items)
2. Batch size ограничен - используй adaptive sizing
3. Мониторь время выполнения каждой транзакции
4. Используй Two-Phase Processing (Read → Compute → Write)
5. Async processing для длительных операций (Celery)

**См. детали:** `{baseDir}/reference/transaction-patterns.md`

## Quick Patterns

### Create Single

```python
response = requests.post(
    f"{odata_url}/Catalog_Users",
    json={"Code": "USER001", "Description": "Test User"},
    headers={'Authorization': f'Basic {auth_token}'},
    timeout=5
)
```

### Read with Filter

```python
response = requests.get(
    f"{odata_url}/Catalog_Users",
    params={
        '$filter': "Code eq 'USER001'",
        '$select': 'Ref_Key,Code,Description'  # Только нужные поля!
    },
    timeout=10
)
```

### Update

```python
response = requests.patch(
    f"{odata_url}/Catalog_Users(guid'{user_id}')",
    json={"Description": "Updated Description"},
    timeout=5
)
```

### Delete

```python
response = requests.delete(
    f"{odata_url}/Catalog_Users(guid'{user_id}')",
    timeout=5
)
```

## Batch Operations (Основной паттерн)

```python
def create_batch_chunked(items: List[Dict], chunk_size: int = 100):
    """Безопасное создание через chunking - каждый chunk < 15s"""
    for chunk in chunks(items, chunk_size):
        batch_request = create_batch_request(chunk)
        response = requests.post(
            f"{odata_url}/$batch",
            data=batch_request,
            headers={'Content-Type': 'multipart/mixed; boundary=batch_boundary'},
            timeout=15
        )
        if response.status_code != 200:
            raise ODataBatchError(response)
```

**См. полный пример:** `{baseDir}/examples/batch-request-example.json`  
**См. детальное руководство:** `{baseDir}/reference/batch-operations.md`

## Batch Size Guidelines

| Операция | Размер | Макс | Причина |
|----------|--------|------|---------|
| **Create** | 50-100 | 200 | Тяжелые операции с валидацией |
| **Update** | 100-200 | 500 | Средняя нагрузка |
| **Delete** | 200-500 | 1000 | Легкие операции |
| **Read** | 500-1000 | 5000 | Только чтение |

## Transaction Time Monitoring

```python
@contextmanager
def monitor_transaction_time(operation: str, limit: int = 15):
    """Мониторинг времени транзакции - ОБЯЗАТЕЛЬНО используй!"""
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        if elapsed > limit:
            logger.error(f"⚠️ CRITICAL: {operation} took {elapsed:.2f}s")
        elif elapsed > limit * 0.8:
            logger.warning(f"WARNING: {operation} took {elapsed:.2f}s")

# Usage
with monitor_transaction_time("Create users batch"):
    create_batch_chunked(users_data, chunk_size=100)
```

## OData Entity Names (1С Naming Convention)

```
Справочники:  Catalog_<Name>      → Catalog_Users
Документы:    Document_<Name>     → Document_Invoice
Регистры:     InformationRegister_<Name>
Перечисления: Enum_<Name>         → Enum_UserRole
```

**ВАЖНО:** Case-sensitive! Используй PascalCase.

## Critical Constraints

1. **Транзакции < 15 секунд** - ЖЕСТКОЕ ограничение платформы 1С
2. **Connection limits: 3-5** concurrent connections per база 1С
3. **Batch size: 50-200** для Create/Update операций
4. **Rate limiting: 100 req/min** per user (по умолчанию)
5. **Timeout handling:** Всегда используй timeout в requests (5-15s)

## Common Errors & Quick Fixes

### 400 Bad Request
```python
# Проверь обязательные поля
required_fields = ['Code', 'Description']
for field in required_fields:
    assert field in data
```

### 401 Unauthorized
```python
# Проверь Basic Auth
auth_b64 = base64.b64encode(f"{user}:{pwd}".encode()).decode()
```

### 500 Timeout
```python
# Уменьши batch size
create_batch_chunked(data, chunk_size=50)  # Было 200
```

### 503 Service Unavailable
```python
# Уменьши connections
with ThreadPoolExecutor(max_workers=3) as executor:  # Было 10
    ...
```

**Детальный troubleshooting:** `{baseDir}/reference/troubleshooting.md`

## Best Practices

1. **Always chunk large datasets** - не более 50-200 items в batch
2. **Monitor transaction time** - используй `monitor_transaction_time`
3. **Limit concurrent connections** - max 3-5 на одну базу
4. **Use $select** для ограничения полей в GET
5. **Two-phase processing** - Read → Compute → Write
6. **Exponential backoff** для retry при ошибках
7. **Validate before batch** - проверь данные перед отправкой

## References

**Skill directory:** `{baseDir}/.claude/skills/cc1c-odata-integration/`

**Детальные руководства:**
- `{baseDir}/reference/batch-operations.md` - Batch операции, error handling
- `{baseDir}/reference/transaction-patterns.md` - Паттерны коротких транзакций
- `{baseDir}/reference/troubleshooting.md` - Debugging OData ошибок

**Примеры:**
- `{baseDir}/examples/batch-request-example.json` - Полный пример $batch

**Проектная документация:**
- `docs/ODATA_INTEGRATION.md` - Общее руководство по OData
- `docs/1C_ADMINISTRATION_GUIDE.md` - Настройка 1С для OData

**Python код:**
- `orchestrator/apps/databases/odata_adapter.py` - OneCODataAdapter
- `{baseDir}/odata-examples.py` - Примеры использования

## Related Skills

- `cc1c-devops` - Управление сервисами, логи
- `cc1c-test-runner` - Тестирование OData integration
