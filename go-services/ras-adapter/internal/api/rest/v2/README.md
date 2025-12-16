# RAS Adapter API v2 - Action-based Endpoints

## Обзор

API v2 использует action-based подход с гибридными параметрами:
- **Query string**: ключевые идентификаторы для роутинга (cluster_id, infobase_id, session_id, server)
- **Request Body**: детали операций (массивы, сложные структуры, опциональные параметры)

## Endpoints (13 total)

### Discovery (2 endpoints)

#### 1. List Clusters
```http
GET /api/v2/list-clusters?server={host:port}
```

**Response:**
```json
{
  "clusters": [
    {
      "uuid": "cluster-uuid",
      "name": "Main Cluster",
      "host": "localhost",
      "port": 1541
    }
  ],
  "count": 1
}
```

#### 2. Get Cluster
```http
GET /api/v2/get-cluster?cluster_id={uuid}&server={host:port}
```

**Response:**
```json
{
  "cluster": {
    "uuid": "cluster-uuid",
    "name": "Main Cluster",
    "host": "localhost",
    "port": 1541
  }
}
```

---

### Infobase Management (8 endpoints)

#### 3. List Infobases
```http
GET /api/v2/list-infobases?cluster_id={uuid}
```

**Response:**
```json
{
  "infobases": [
    {
      "uuid": "infobase-uuid",
      "name": "accounting",
      "dbms": "PostgreSQL",
      "db_server": "localhost",
      "db_name": "accounting_db"
    }
  ],
  "count": 1
}
```

#### 4. Get Infobase
```http
GET /api/v2/get-infobase?cluster_id={uuid}&infobase_id={uuid}
```

**Response:**
```json
{
  "infobase": {
    "uuid": "infobase-uuid",
    "name": "accounting",
    "dbms": "PostgreSQL",
    "db_server": "localhost",
    "db_name": "accounting_db"
  }
}
```

#### 5. Create Infobase
```http
POST /api/v2/create-infobase?cluster_id={uuid}
Content-Type: application/json

{
  "name": "new_base",
  "dbms": "PostgreSQL",
  "db_server_name": "localhost",
  "db_name": "new_base_db",
  "db_user": "admin",
  "db_password": "secret",
  "locale": "ru_RU",
  "scheduled_jobs_denied": false,
  "sessions_denied": false
}
```

**Response:**
```json
{
  "success": true,
  "infobase_id": "new-infobase-uuid",
  "message": "Infobase created successfully"
}
```

#### 6. Drop Infobase
```http
POST /api/v2/drop-infobase?cluster_id={uuid}&infobase_id={uuid}
Content-Type: application/json

{
  "drop_database": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Infobase dropped successfully"
}
```

#### 7. Lock Infobase
```http
POST /api/v2/lock-infobase?cluster_id={uuid}&infobase_id={uuid}
Content-Type: application/json

{
  "db_user": "admin",
  "db_password": "secret"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Infobase locked successfully (scheduled jobs blocked)"
}
```

#### 8. Unlock Infobase
```http
POST /api/v2/unlock-infobase?cluster_id={uuid}&infobase_id={uuid}
Content-Type: application/json

{
  "db_user": "admin",
  "db_password": "secret"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Infobase unlocked successfully (scheduled jobs enabled)"
}
```

#### 9. Block Sessions
```http
POST /api/v2/block-sessions?cluster_id={uuid}&infobase_id={uuid}
Content-Type: application/json

{
  "denied_from": "2025-01-01T00:00:00Z",
  "denied_to": "2025-01-02T00:00:00Z",
  "denied_message": "Maintenance in progress",
  "permission_code": "ADMIN",
  "parameter": "",
  "db_user": "admin",
  "db_password": "secret"
}
```

**Response:**
```json
{
  "success": true,
  "message": "User sessions blocked successfully"
}
```

#### 10. Unblock Sessions
```http
POST /api/v2/unblock-sessions?cluster_id={uuid}&infobase_id={uuid}
Content-Type: application/json

{
  "db_user": "admin",
  "db_password": "secret"
}
```

**Response:**
```json
{
  "success": true,
  "message": "User sessions unblocked successfully"
}
```

---

### Session Management (3 endpoints)

#### 11. List Sessions
```http
GET /api/v2/list-sessions?cluster_id={uuid}&infobase_id={uuid}
```

**Response:**
```json
{
  "sessions": [
    {
      "uuid": "session-uuid",
      "user_name": "admin",
      "app_id": "1CV8C",
      "host": "localhost",
      "started_at": "2025-01-01T12:00:00Z"
    }
  ],
  "count": 1
}
```

#### 12. Terminate Session
```http
POST /api/v2/terminate-session?cluster_id={uuid}&infobase_id={uuid}&session_id={uuid}
```

**Response:**
```json
{
  "success": true,
  "message": "Session terminated successfully",
  "session_id": "session-uuid"
}
```

#### 13. Terminate Sessions (Bulk)
```http
POST /api/v2/terminate-sessions?cluster_id={uuid}&infobase_id={uuid}
Content-Type: application/json

{
  "session_ids": ["session-uuid-1", "session-uuid-2"]
}
```

**Note:** Если `session_ids` не указан, завершаются ВСЕ сессии для указанной базы.

**Response:**
```json
{
  "terminated_count": 2,
  "failed_count": 0,
  "failed_sessions": []
}
```

---

## Коды ошибок

### 400 Bad Request
- `MISSING_PARAMETER` - отсутствует обязательный параметр
- `INVALID_UUID` - неверный формат UUID

### 404 Not Found
- `SESSION_NOT_FOUND` - сессия не найдена

### 500 Internal Server Error
- Ошибка выполнения операции на RAS сервере

### 501 Not Implemented
- `NOT_IMPLEMENTED` - функциональность еще не реализована

---

## Примеры использования

### cURL

**Получить список кластеров:**
```bash
curl -X GET "http://localhost:8088/api/v2/list-clusters?server=localhost:1541"
```

**Заблокировать сессии базы:**
```bash
curl -X POST "http://localhost:8088/api/v2/block-sessions?cluster_id=UUID&infobase_id=UUID" \
  -H "Content-Type: application/json" \
  -d '{
    "denied_message": "Maintenance",
    "db_user": "admin",
    "db_password": "secret"
  }'
```

**Завершить все сессии:**
```bash
curl -X POST "http://localhost:8088/api/v2/terminate-sessions?cluster_id=UUID&infobase_id=UUID"
```

---

## Миграция с v1 на v2

v1 endpoints удалены. Используйте action-based API `/api/v2/*` из этого документа.

---

## Версионирование

- **v2**: Action-based API
