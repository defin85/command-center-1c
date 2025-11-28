# Cluster CRUD Endpoints (API v2)

Документация по CRUD операциям с кластерами 1С в API v2.

## Базовый URL

```
http://localhost:8080/api/v2/clusters/
```

## Endpoints

### 1. Создание кластера

**POST** `/api/v2/clusters/create-cluster/`

Создает новый кластер 1С.

**Request Body:**
```json
{
  "name": "cluster-name",
  "ras_server": "localhost:1545",
  "cluster_service_url": "http://localhost:8087",
  "cluster_user": "admin",          // опционально
  "cluster_pwd": "password",        // опционально
  "description": "Description",     // опционально
  "status": "active",               // опционально, default: active
  "metadata": {}                    // опционально
}
```

**Response (201):**
```json
{
  "cluster": {
    "id": "uuid",
    "name": "cluster-name",
    "ras_server": "localhost:1545",
    "cluster_service_url": "http://localhost:8087",
    "status": "active",
    "description": "Description",
    "databases_count": 0,
    "created_at": "2025-11-28T10:00:00Z",
    "updated_at": "2025-11-28T10:00:00Z"
  },
  "message": "Cluster created successfully"
}
```

**Errors:**
- `400` - Отсутствуют обязательные поля или ошибка валидации
- `409` - Кластер с таким ras_server + name уже существует

**Пример (curl):**
```bash
curl -X POST http://localhost:8080/api/v2/clusters/create-cluster/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "prod-cluster",
    "ras_server": "localhost:1545",
    "cluster_service_url": "http://localhost:8087",
    "description": "Production cluster"
  }'
```

---

### 2. Обновление кластера

**PUT** `/api/v2/clusters/update-cluster/?cluster_id=X`
**POST** `/api/v2/clusters/update-cluster/` (cluster_id в body)

Обновляет информацию о кластере.

**Query Parameters:**
- `cluster_id` (UUID) - ID кластера (можно передать в query или body)

**Request Body:**
```json
{
  "cluster_id": "uuid",             // опционально, если в query
  "name": "new-name",               // опционально
  "description": "new description", // опционально
  "status": "maintenance",          // опционально
  "cluster_user": "admin",          // опционально
  "cluster_pwd": "new-password",    // опционально
  "metadata": {}                    // опционально
}
```

**Response (200):**
```json
{
  "cluster": {
    "id": "uuid",
    "name": "new-name",
    "status": "maintenance",
    "description": "new description",
    ...
  },
  "message": "Cluster updated successfully"
}
```

**Errors:**
- `400` - Отсутствует cluster_id или ошибка валидации
- `404` - Кластер не найден
- `409` - Конфликт уникальности (ras_server + name)

**Пример (curl):**
```bash
curl -X PUT "http://localhost:8080/api/v2/clusters/update-cluster/?cluster_id=<uuid>" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "status": "maintenance",
    "description": "Under maintenance"
  }'
```

---

### 3. Удаление кластера

**DELETE** `/api/v2/clusters/delete-cluster/?cluster_id=X`
**POST** `/api/v2/clusters/delete-cluster/` (cluster_id в body)

Удаляет кластер.

**Query Parameters:**
- `cluster_id` (UUID) - ID кластера (можно передать в query или body)

**Request Body (опционально):**
```json
{
  "cluster_id": "uuid",  // опционально, если в query
  "force": false         // опционально, default: false
}
```

**Response (200):**
```json
{
  "message": "Cluster deleted successfully",
  "cluster_id": "uuid"
}
```

**Errors:**
- `400` - Отсутствует cluster_id
- `404` - Кластер не найден
- `409` - У кластера есть базы данных и force=false

**Пример (curl):**
```bash
# Удаление без force (ошибка если есть БД)
curl -X DELETE "http://localhost:8080/api/v2/clusters/delete-cluster/?cluster_id=<uuid>" \
  -H "Authorization: Bearer <token>"

# Принудительное удаление (с БД)
curl -X POST http://localhost:8080/api/v2/clusters/delete-cluster/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "cluster_id": "<uuid>",
    "force": true
  }'
```

---

### 4. Получение баз данных кластера

**GET** `/api/v2/clusters/get-cluster-databases/?cluster_id=X`

Получает все базы данных кластера с опциональной фильтрацией.

**Query Parameters:**
- `cluster_id` (UUID, required) - ID кластера
- `status` (string, optional) - Фильтр по статусу БД (active, inactive, error, maintenance)
- `health_status` (string, optional) - Фильтр по health status (ok, degraded, down, unknown)

**Response (200):**
```json
{
  "cluster_id": "uuid",
  "cluster_name": "cluster-name",
  "databases": [
    {
      "id": "db-id",
      "name": "db-name",
      "status": "active",
      "last_check_status": "ok",
      ...
    }
  ],
  "count": 100,
  "filters": {
    "status": "active",
    "health_status": "ok"
  }
}
```

**Errors:**
- `400` - Отсутствует cluster_id
- `404` - Кластер не найден

**Примеры (curl):**
```bash
# Все базы данных кластера
curl -X GET "http://localhost:8080/api/v2/clusters/get-cluster-databases/?cluster_id=<uuid>" \
  -H "Authorization: Bearer <token>"

# Только активные и здоровые базы
curl -X GET "http://localhost:8080/api/v2/clusters/get-cluster-databases/?cluster_id=<uuid>&status=active&health_status=ok" \
  -H "Authorization: Bearer <token>"
```

---

## Общие правила

### Аутентификация

Все endpoints требуют аутентификации через JWT токен:

```
Authorization: Bearer <jwt_token>
```

### Формат ошибок

Все ошибки возвращаются в едином формате:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}  // опционально, для ошибок валидации
  }
}
```

### Коды ошибок

- `MISSING_PARAMETER` - Отсутствует обязательный параметр
- `VALIDATION_ERROR` - Ошибка валидации данных
- `CLUSTER_NOT_FOUND` - Кластер не найден
- `DUPLICATE_CLUSTER` - Кластер с таким ras_server + name уже существует
- `CLUSTER_HAS_DATABASES` - У кластера есть базы данных (при удалении без force)

### Безопасность

- Поле `cluster_pwd` - **write-only** (не возвращается в ответах)
- Пароль хранится в зашифрованном виде (EncryptedCharField)

### Оптимизация

- Используется `prefetch_related('databases')` для избежания N+1 запросов
- В `list-clusters` используется `Count()` для подсчета баз данных

---

## Тестирование

Запустить тесты:

```bash
cd orchestrator
source venv/Scripts/activate
python test_cluster_endpoints.py
```

Ожидаемый результат:

```
=== Testing create_cluster ===
Missing name: 400 - {...}
Valid creation: 201 - Cluster created successfully
Duplicate: 409 - DUPLICATE_CLUSTER

=== Testing update_cluster ===
Update: 200 - Cluster updated successfully
Not found: 404 - CLUSTER_NOT_FOUND

=== Testing get_cluster_databases ===
Get databases: 200 - Count: 0

=== Testing delete_cluster ===
Delete: 200 - Cluster deleted successfully

[OK] All tests passed!
```

---

## См. также

- [API v2 Унификация](../roadmaps/API_V2_UNIFICATION_ROADMAP.md)
- [Database CRUD Endpoints](database_crud_endpoints.md)
- [Cluster Model](../../orchestrator/apps/databases/models.py)
