# Transaction Patterns - Как соблюдать лимит < 15 секунд

## ⚠️ КРИТИЧНО: Почему < 15 секунд?

**Это НЕ рекомендация - это ЖЕСТКОЕ ОГРАНИЧЕНИЕ платформы 1С!**

**Последствия при превышении:**
1. **Automatic rollback** - транзакция откатится
2. **Блокировка других пользователей** - deadlocks
3. **Риск data corruption** - partial writes
4. **Снижение производительности** всей системы 1С
5. **Connection pool exhaustion** - новые пользователи не смогут подключиться

## Pattern 1: Chunking Large Datasets

### Проблема

```python
# ❌ ПЛОХО - одна длинная транзакция
def update_all_users(users_data: List[Dict]):
    """ОПАСНО: Может превысить 15 секунд при большом количестве users"""
    for user in users_data:  # 1000 users = 30-60 секунд!
        response = requests.patch(
            f"{odata_url}/Catalog_Users(guid'{user['id']}')",
            json=user,
            headers=headers
        )
```

### Решение

```python
# ✅ ХОРОШО - chunking с короткими транзакциями
def update_all_users_chunked(users_data: List[Dict], chunk_size: int = 50):
    """Безопасно: Каждый chunk = отдельная короткая транзакция"""
    for chunk in chunks(users_data, chunk_size):
        # Каждый batch - это отдельная транзакция < 15s
        with monitor_transaction_time("Update users chunk"):
            batch_request = create_batch_request(chunk, operation='PATCH')
            response = requests.post(
                f"{odata_url}/$batch",
                data=batch_request,
                headers=headers,
                timeout=15  # Hard timeout
            )
            process_batch_response(response)

        # Опционально: короткая пауза между chunks для снижения нагрузки
        time.sleep(0.1)
```

## Pattern 2: Iterative Processing with Progress Tracking

### Проблема

```python
# ❌ ПЛОХО - нет возможности отследить прогресс
def process_invoices(invoice_ids: List[str]):
    """Если упадет на 500-й invoice - потеряешь весь прогресс"""
    for invoice_id in invoice_ids:
        process_invoice(invoice_id)
```

### Решение

```python
# ✅ ХОРОШО - сохранение прогресса после каждого chunk
def process_invoices_safe(invoice_ids: List[str], chunk_size: int = 20):
    """
    Безопасная обработка с сохранением прогресса

    При падении можно продолжить с последнего processed_index
    """
    total = len(invoice_ids)
    processed = 0

    for i, chunk in enumerate(chunks(invoice_ids, chunk_size)):
        try:
            with monitor_transaction_time(f"Process invoices chunk {i}"):
                # Один batch = одна транзакция < 15s
                results = process_invoice_batch(chunk)

                # Сохранить прогресс в БД
                save_processing_progress(
                    task_id=current_task_id,
                    processed_count=processed + len(chunk),
                    total_count=total
                )

                processed += len(chunk)
                logger.info(f"Progress: {processed}/{total} ({processed/total*100:.1f}%)")

        except Exception as e:
            logger.error(f"Chunk {i} failed at index {processed}: {e}")
            # Продолжить со следующего chunk или прервать
            raise

    return processed
```

## Pattern 3: Two-Phase Processing (Read → Process → Write)

### Проблема

```python
# ❌ ПЛОХО - длинная транзакция с вычислениями
def calculate_and_update_prices():
    """Вычисления + запись в одной транзакции = timeout"""
    products = get_all_products()  # 1000 products
    for product in products:
        # Сложные вычисления (5-10 секунд)
        new_price = calculate_complex_price(product)
        # Запись в 1С
        update_product_price(product['id'], new_price)  # TIMEOUT!
```

### Решение

```python
# ✅ ХОРОШО - разделение на фазы
def calculate_and_update_prices_safe():
    """
    Phase 1: Read all data (быстро)
    Phase 2: Calculate offline (без транзакции)
    Phase 3: Write in small batches (короткие транзакции)
    """
    # Phase 1: Read (одна быстрая транзакция)
    products = get_all_products()

    # Phase 2: Calculate offline (БЕЗ транзакции в 1С)
    updates = []
    for product in products:
        new_price = calculate_complex_price(product)
        updates.append({
            'id': product['id'],
            'Price': new_price
        })

    # Phase 3: Write in batches (короткие транзакции)
    for chunk in chunks(updates, chunk_size=100):
        with monitor_transaction_time("Update prices batch"):
            batch_request = create_batch_request(chunk, operation='PATCH')
            response = requests.post(f"{odata_url}/$batch", ...)
```

## Pattern 4: Async Processing for Long Operations

### Проблема

```python
# ❌ ПЛОХО - синхронная обработка больших объемов
def import_large_file(file_path: str):
    """Синхронная обработка 10000 records = 60+ секунд"""
    records = parse_csv(file_path)  # 10000 records
    for record in records:
        create_object(record)  # TIMEOUT!
```

### Решение

```python
# ✅ ХОРОШО - асинхронная обработка через Celery
@celery_app.task
def import_large_file_async(file_path: str, chunk_size: int = 100):
    """
    Асинхронная обработка через task queue

    Каждый chunk обрабатывается в отдельной короткой транзакции
    """
    records = parse_csv(file_path)
    total_chunks = len(list(chunks(records, chunk_size)))

    # Создать подзадачи для каждого chunk
    job_group = group(
        import_chunk.s(chunk, i, total_chunks)
        for i, chunk in enumerate(chunks(records, chunk_size))
    )

    # Запустить параллельно (но не более 5 worker'ов!)
    result = job_group.apply_async()

    return {
        'task_id': result.id,
        'total_chunks': total_chunks,
        'status': 'processing'
    }

@celery_app.task
def import_chunk(chunk: List[Dict], chunk_idx: int, total: int):
    """Обработка одного chunk - ГАРАНТИРОВАННО < 15s"""
    with monitor_transaction_time(f"Import chunk {chunk_idx}/{total}"):
        batch_request = create_batch_request(chunk, operation='POST')
        response = requests.post(f"{odata_url}/$batch", ...)

        return {
            'chunk_idx': chunk_idx,
            'processed': len(chunk)
        }
```

## Pattern 5: Conditional Batching Based on Complexity

### Проблема

```python
# ❌ ПЛОХО - фиксированный batch size для разных типов объектов
def process_mixed_objects(objects: List[Dict]):
    """
    Простые объекты (User) vs сложные (Invoice) требуют разного batch size
    """
    for chunk in chunks(objects, chunk_size=100):  # НЕ ОПТИМАЛЬНО!
        process_batch(chunk)
```

### Решение

```python
# ✅ ХОРОШО - адаптивный batch size
def process_mixed_objects_adaptive(objects: List[Dict]):
    """
    Адаптивный batch size в зависимости от сложности объекта
    """
    # Группировка по типу
    grouped = defaultdict(list)
    for obj in objects:
        grouped[obj['_type']].append(obj)

    # Разный batch size для разных типов
    batch_sizes = {
        'Catalog_Users': 200,        # Простые объекты
        'Document_Invoice': 50,      # Сложные с валидациями
        'Document_Payment': 100,     # Средней сложности
    }

    for obj_type, items in grouped.items():
        chunk_size = batch_sizes.get(obj_type, 100)  # default 100

        for chunk in chunks(items, chunk_size):
            with monitor_transaction_time(f"Process {obj_type} batch"):
                process_batch(chunk)
```

## Мониторинг и Alerts

### Настройка мониторинга времени транзакций

```python
import logging
import time
from functools import wraps

# Настройка логгера для метрик
metrics_logger = logging.getLogger('metrics')

def track_transaction_time(func):
    """
    Decorator для отслеживания времени транзакций

    Автоматически логирует:
    - Время выполнения
    - Warning при приближении к 15s
    - Error при превышении 15s
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start

            # Метрики для Prometheus/Grafana
            metrics_logger.info(
                f"transaction_time",
                extra={
                    'function': func.__name__,
                    'elapsed': elapsed,
                    'status': 'success'
                }
            )

            # Alerts
            if elapsed > 15:
                logger.error(f"⚠️ CRITICAL: {func.__name__} took {elapsed:.2f}s (> 15s limit!)")
            elif elapsed > 12:
                logger.warning(f"WARNING: {func.__name__} took {elapsed:.2f}s (close to limit)")

            return result

        except Exception as e:
            elapsed = time.time() - start
            metrics_logger.error(
                f"transaction_failed",
                extra={
                    'function': func.__name__,
                    'elapsed': elapsed,
                    'error': str(e)
                }
            )
            raise

    return wrapper

# Usage
@track_transaction_time
def create_users_batch(users_data: List[Dict]):
    # ... implementation
    pass
```

## Best Practices Summary

1. **Chunking** - всегда разбивай большие операции на chunks (50-200 items)
2. **Monitoring** - отслеживай время каждой транзакции
3. **Progress tracking** - сохраняй прогресс после каждого chunk
4. **Two-phase** - разделяй read/compute/write на отдельные фазы
5. **Async processing** - используй Celery для длительных операций
6. **Adaptive sizing** - подбирай batch size под сложность объектов
7. **Connection limits** - не более 3-5 concurrent connections на базу
8. **Exponential backoff** - retry с увеличивающимся интервалом при ошибках

## Тестирование лимитов

```python
def test_transaction_time_limits():
    """
    Тест для проверки что операции укладываются в 15s

    Запускай после любых изменений в batch operations
    """
    # Тест с максимальным batch size
    test_data = generate_test_users(count=200)

    start = time.time()
    create_users_batch(test_data, batch_size=200)
    elapsed = time.time() - start

    assert elapsed < 15, f"Transaction took {elapsed:.2f}s (> 15s limit!)"

    # Тест с реальными данными
    real_data = fetch_production_sample(count=100)

    start = time.time()
    update_users_batch(real_data, batch_size=100)
    elapsed = time.time() - start

    assert elapsed < 12, f"Transaction took {elapsed:.2f}s (too close to 15s limit)"
```

## См. также

- `batch-operations.md` - Детальное руководство по batch операциям
- `troubleshooting.md` - Debugging timeout ошибок
- `../../docs/ODATA_INTEGRATION.md` - Общее руководство по OData
