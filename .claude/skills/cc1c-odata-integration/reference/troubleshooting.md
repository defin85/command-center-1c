# OData Troubleshooting Guide

## Common OData Error Codes

### 400 Bad Request

**Причины:**
- Неправильный формат JSON
- Отсутствуют обязательные поля
- Неверный тип данных
- Нарушение бизнес-логики 1С

**Примеры:**

```json
{
  "error": {
    "code": "BadRequest",
    "message": "Поле 'Code' не заполнено"
  }
}
```

**Решения:**

1. **Проверь структуру JSON:**
   ```python
   # Валидация перед отправкой
   required_fields = ['Description', 'Code']
   for field in required_fields:
       assert field in data, f"Missing required field: {field}"
   ```

2. **Проверь metadata для обязательных полей:**
   ```bash
   curl -u username:password \
     http://server:port/base/odata/standard.odata/$metadata
   ```

3. **Включи подробное логирование:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

---

### 401 Unauthorized

**Причины:**
- Неправильные credentials
- Истек session token
- Недостаточные права доступа

**Примеры:**

```json
{
  "error": {
    "code": "Unauthorized",
    "message": "Неверное имя пользователя или пароль"
  }
}
```

**Решения:**

1. **Проверь Basic Auth credentials:**
   ```python
   import base64

   username = "Administrator"
   password = "password"
   auth_string = f"{username}:{password}"
   auth_bytes = auth_string.encode('utf-8')
   auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')

   headers = {
       'Authorization': f'Basic {auth_b64}'
   }
   ```

2. **Проверь права пользователя в 1С:**
   - Открой консоль администрирования 1С
   - Проверь что пользователь имеет роль с правами на OData
   - Проверь что OData endpoint включен для пользователя

3. **Тестируй подключение через curl:**
   ```bash
   curl -u username:password \
     http://server:port/base/odata/standard.odata/Catalog_Users
   ```

---

### 404 Not Found

**Причины:**
- Неправильный URL endpoint
- Entity не существует
- Неправильное имя Entity
- База 1С не опубликована через OData

**Примеры:**

```json
{
  "error": {
    "code": "NotFound",
    "message": "Ресурс не найден"
  }
}
```

**Решения:**

1. **Проверь имя Entity (case-sensitive!):**
   ```python
   # ❌ НЕПРАВИЛЬНО
   url = f"{odata_url}/catalog_users"  # lowercase

   # ✅ ПРАВИЛЬНО
   url = f"{odata_url}/Catalog_Users"  # PascalCase
   ```

2. **Проверь доступные entities через metadata:**
   ```bash
   curl http://server:port/base/odata/standard.odata/$metadata \
     | grep "EntityType Name"
   ```

3. **Проверь что база опубликована:**
   - Открой 1С Конфигуратор
   - Администрирование → Публикация баз данных
   - Проверь что OData включен

---

### 409 Conflict

**Причины:**
- Duplicate key violation (Code уже существует)
- Concurrent modification (optimistic locking)
- Нарушение уникальности

**Примеры:**

```json
{
  "error": {
    "code": "Conflict",
    "message": "Объект с кодом 'USER001' уже существует"
  }
}
```

**Решения:**

1. **Проверь уникальность перед созданием:**
   ```python
   def create_user_safe(code: str, description: str):
       # Проверка существования
       existing = requests.get(
           f"{odata_url}/Catalog_Users",
           params={'$filter': f"Code eq '{code}'"}
       ).json()

       if existing['value']:
           logger.warning(f"User {code} already exists")
           return existing['value'][0]

       # Создание
       return requests.post(
           f"{odata_url}/Catalog_Users",
           json={'Code': code, 'Description': description}
       )
   ```

2. **Используй PATCH вместо POST для update:**
   ```python
   # Update existing
   response = requests.patch(
       f"{odata_url}/Catalog_Users(guid'{user_id}')",
       json={'Description': new_description}
   )
   ```

---

### 500 Internal Server Error

**Причины:**
- Ошибка в бизнес-логике 1С
- Transaction timeout (> 15 секунд!)
- Недостаточно памяти на сервере
- Deadlock в БД

**Примеры:**

```json
{
  "error": {
    "code": "InternalServerError",
    "message": "Ошибка выполнения запроса"
  }
}
```

**Решения:**

1. **Проверь логи сервера 1С:**
   - Технологический журнал 1С
   - Event Viewer Windows (если сервер на Windows)

2. **Уменьши batch size если timeout:**
   ```python
   # ❌ Слишком большой batch
   create_users_batch(data, batch_size=500)  # TIMEOUT!

   # ✅ Безопасный размер
   create_users_batch(data, batch_size=50)
   ```

3. **Добавь retry с exponential backoff:**
   ```python
   from tenacity import retry, wait_exponential, stop_after_attempt

   @retry(
       wait=wait_exponential(min=1, max=10),
       stop=stop_after_attempt(3)
   )
   def create_user_with_retry(data: Dict):
       response = requests.post(f"{odata_url}/Catalog_Users", json=data)
       response.raise_for_status()
       return response.json()
   ```

---

### 503 Service Unavailable

**Причины:**
- Сервер 1С перегружен
- Превышен connection pool
- Maintenance mode
- Network issues

**Примеры:**

```json
{
  "error": {
    "code": "ServiceUnavailable",
    "message": "Сервис временно недоступен"
  }
}
```

**Решения:**

1. **Уменьши количество параллельных соединений:**
   ```python
   # ❌ Слишком много workers
   with ThreadPoolExecutor(max_workers=20) as executor:  # TOO MUCH!
       ...

   # ✅ Безопасное количество
   with ThreadPoolExecutor(max_workers=5) as executor:
       ...
   ```

2. **Добавь rate limiting:**
   ```python
   from ratelimit import limits, sleep_and_retry

   # Не более 10 запросов в минуту
   @sleep_and_retry
   @limits(calls=10, period=60)
   def create_user_rate_limited(data: Dict):
       return requests.post(f"{odata_url}/Catalog_Users", json=data)
   ```

3. **Проверь connection pool settings:**
   ```python
   from requests.adapters import HTTPAdapter
   from requests.packages.urllib3.util.retry import Retry

   session = requests.Session()
   retry_strategy = Retry(
       total=3,
       backoff_factor=1,
       status_forcelist=[429, 500, 502, 503, 504]
   )
   adapter = HTTPAdapter(
       max_retries=retry_strategy,
       pool_connections=5,  # ОГРАНИЧЕНИЕ!
       pool_maxsize=5
   )
   session.mount("http://", adapter)
   session.mount("https://", adapter)
   ```

---

## Debugging Techniques

### 1. Включи подробное логирование

```python
import logging
import http.client as http_client

# Логирование HTTP requests/responses
http_client.HTTPConnection.debuglevel = 1

# Настройка логгера
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("requests").setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)
```

### 2. Используй Fiddler/Charles для перехвата трафика

**Настройка proxy:**

```python
proxies = {
    'http': 'http://localhost:8888',   # Fiddler proxy
    'https': 'http://localhost:8888'
}

response = requests.get(
    f"{odata_url}/Catalog_Users",
    proxies=proxies,
    verify=False  # Только для debugging!
)
```

### 3. Тестирование через curl

```bash
# GET request
curl -v -u username:password \
  http://server:port/base/odata/standard.odata/Catalog_Users

# POST request
curl -v -u username:password \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"Code":"TEST001","Description":"Test User"}' \
  http://server:port/base/odata/standard.odata/Catalog_Users

# PATCH request
curl -v -u username:password \
  -H "Content-Type: application/json" \
  -X PATCH \
  -d '{"Description":"Updated Description"}' \
  http://server:port/base/odata/standard.odata/Catalog_Users(guid'...')

# DELETE request
curl -v -u username:password \
  -X DELETE \
  http://server:port/base/odata/standard.odata/Catalog_Users(guid'...')
```

### 4. Проверка response headers

```python
response = requests.get(f"{odata_url}/Catalog_Users")

# Полезные headers
print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")
print(f"Server: {response.headers.get('Server')}")
print(f"X-Request-Id: {response.headers.get('X-Request-Id')}")  # Для трейсинга

# Response time
print(f"Elapsed: {response.elapsed.total_seconds()}s")
```

### 5. Автоматическое логирование всех requests

```python
import requests
from functools import wraps

def log_odata_request(func):
    """Decorator для автоматического логирования OData запросов"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Логирование request
        logger.debug(f"OData Request: {func.__name__}")
        logger.debug(f"Args: {args}")
        logger.debug(f"Kwargs: {kwargs}")

        start_time = time.time()

        try:
            response = func(*args, **kwargs)
            elapsed = time.time() - start_time

            # Логирование response
            logger.debug(f"Status: {response.status_code}")
            logger.debug(f"Elapsed: {elapsed:.2f}s")

            if response.status_code >= 400:
                logger.error(f"Error response: {response.text}")

            return response

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Request failed after {elapsed:.2f}s: {e}")
            raise

    return wrapper

# Usage
@log_odata_request
def create_user(data: Dict):
    return requests.post(f"{odata_url}/Catalog_Users", json=data)
```

---

## Performance Issues

### Problem: Slow OData requests

**Диагностика:**

```python
import time

def diagnose_slow_request():
    """Диагностика медленных OData запросов"""

    # 1. Проверь сетевую задержку
    start = time.time()
    response = requests.get(f"{odata_url}/$metadata")
    network_latency = time.time() - start
    print(f"Network latency: {network_latency:.2f}s")

    # 2. Проверь время выполнения простого запроса
    start = time.time()
    response = requests.get(
        f"{odata_url}/Catalog_Users",
        params={'$top': 1}
    )
    simple_query_time = time.time() - start
    print(f"Simple query time: {simple_query_time:.2f}s")

    # 3. Проверь время выполнения сложного запроса
    start = time.time()
    response = requests.get(
        f"{odata_url}/Catalog_Users",
        params={
            '$filter': "Description like '%test%'",
            '$expand': 'Owner',
            '$top': 100
        }
    )
    complex_query_time = time.time() - start
    print(f"Complex query time: {complex_query_time:.2f}s")

    # Анализ
    if network_latency > 1:
        print("⚠️ High network latency - проверь подключение к серверу")
    if simple_query_time > 2:
        print("⚠️ Slow simple queries - проверь нагрузку на сервер 1С")
    if complex_query_time > 10:
        print("⚠️ Slow complex queries - оптимизируй $filter и $expand")
```

**Решения:**

1. **Используй $select для ограничения полей:**
   ```python
   # ❌ Медленно - возвращает все поля
   response = requests.get(f"{odata_url}/Catalog_Users")

   # ✅ Быстро - только нужные поля
   response = requests.get(
       f"{odata_url}/Catalog_Users",
       params={'$select': 'Ref_Key,Description,Code'}
   )
   ```

2. **Используй $top и $skip для пагинации:**
   ```python
   def fetch_all_users_paginated(page_size: int = 100):
       """Пагинация для больших результатов"""
       skip = 0
       all_users = []

       while True:
           response = requests.get(
               f"{odata_url}/Catalog_Users",
               params={
                   '$top': page_size,
                   '$skip': skip
               }
           )

           users = response.json()['value']
           if not users:
               break

           all_users.extend(users)
           skip += page_size

       return all_users
   ```

3. **Избегай сложных $filter на больших таблицах:**
   ```python
   # ❌ Медленно - full table scan
   params = {'$filter': "Description like '%test%'"}

   # ✅ Быстрее - точное совпадение
   params = {'$filter': "Code eq 'USER001'"}
   ```

---

## См. также

- `batch-operations.md` - Batch операции и error handling
- `transaction-patterns.md` - Паттерны для коротких транзакций
- `../../docs/ODATA_INTEGRATION.md` - Общее руководство по OData
