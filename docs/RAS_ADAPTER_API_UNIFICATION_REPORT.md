# RAS Adapter API Унификация - Архитектурный отчет

**Дата:** 2025-11-23
**Версия:** 1.0
**Статус:** Предложение архитектуры
**Автор:** Senior Software Architect

---

## Executive Summary

### Проблема
RAS Adapter API содержит архитектурные недостатки, выявленные при тестировании Week 4.5:
- DELETE endpoint использует JSON body (анти-паттерн RFC 9110)
- Длинные URL с UUID усложняют использование API
- Неочевидное поведение массовых операций
- Отсутствует единообразие между resource-based и action-based подходами

### Рекомендуемое решение
**Вариант B: Action-based API** - миграция на короткие, понятные endpoint'ы в стиле Kontur/Stripe/Twilio с параметрами через query string или body.

### Оценка effort
- **Разработка:** 5-7 дней
- **Тестирование:** 2-3 дня
- **Документация:** 1-2 дня
- **Итого:** 8-12 дней

---

## Исследование best practices

### RESTful vs Action-based подходы

| Критерий | RESTful | Action-based |
|----------|---------|--------------|
| **URL структура** | `/resources/{id}/sub-resources` | `/action-name` |
| **Длина URL** | Длинные (с UUID) | Короткие |
| **Семантика** | CRUD операции | Бизнес-действия |
| **Параметры** | В URL path | Query params/body |
| **Примеры** | GitHub API v3 | Stripe, Twilio, Kontur |

### Анализ индустриальных примеров

**Stripe API (Action-based):**
```
POST /v1/payment_intents/create
POST /v1/payment_intents/confirm
POST /v1/payment_intents/cancel
```
- Короткие, понятные endpoint'ы
- Все параметры через body
- Версионирование через URL prefix

**GitHub API (RESTful + Actions):**
```
GET /repos/{owner}/{repo}           # Resource
POST /repos/{owner}/{repo}/transfer # Action
POST /repos/{owner}/{repo}/archive  # Action
```
- Гибридный подход
- Actions как sub-resources

**Kontur Diadoc (Pure Action-based):**
```
POST /V2/GenerateInvoiceXml?boxId={id}
POST /V2/SendDocument?boxId={id}
POST /V2/SignDocument?boxId={id}
```
- Все endpoint'ы - действия
- Параметры через query string
- Очень короткие URL

### RFC 9110 и DELETE
RFC 9110 (HTTP Semantics) указывает:
- DELETE body имеет "неопределённую семантику"
- Многие прокси/библиотеки игнорируют DELETE body
- Best practice: использовать query parameters

---

## Вариант A: RESTful v2 (Эволюция текущего)

### Концепция
Сохранить RESTful структуру, но исправить архитектурные проблемы.

### Список endpoint'ов

```bash
# Clusters
GET    /api/v2/clusters?server={host:port}
GET    /api/v2/clusters/{id}?server={host:port}

# Infobases
GET    /api/v2/infobases?cluster_id={uuid}
GET    /api/v2/infobases/{id}?cluster_id={uuid}
POST   /api/v2/infobases
DELETE /api/v2/infobases/{id}?cluster_id={uuid}&drop_database=true  # FIXED
PUT    /api/v2/infobases/{id}/lock?cluster_id={uuid}
DELETE /api/v2/infobases/{id}/lock?cluster_id={uuid}
PUT    /api/v2/infobases/{id}/sessions-block?cluster_id={uuid}
DELETE /api/v2/infobases/{id}/sessions-block?cluster_id={uuid}

# Sessions
GET    /api/v2/sessions?cluster_id={uuid}&infobase_id={uuid}
DELETE /api/v2/sessions/{id}?cluster_id={uuid}&infobase_id={uuid}    # NEW
POST   /api/v2/sessions/batch/terminate                              # RENAMED
```

### Примеры curl

```bash
# Удаление базы (исправлен DELETE)
curl -X DELETE "http://localhost:8088/api/v2/infobases/ae1e5ea8-96e9-45cb-8363-8e4473daa269?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab&drop_database=true"

# Блокировка базы (PUT для идемпотентности)
curl -X PUT "http://localhost:8088/api/v2/infobases/ae1e5ea8-96e9-45cb-8363-8e4473daa269/lock?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab"

# Точечное завершение сеанса (новый endpoint)
curl -X DELETE "http://localhost:8088/api/v2/sessions/session-uuid?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab&\
infobase_id=ae1e5ea8-96e9-45cb-8363-8e4473daa269"
```

### Плюсы и минусы

**Плюсы:**
- ✅ Минимальные изменения в коде
- ✅ Знакомый RESTful подход
- ✅ Соответствие RFC 9110
- ✅ Четкая иерархия ресурсов

**Минусы:**
- ❌ URL остаются длинными (UUID в path)
- ❌ Сложность с nested resources
- ❌ Неудобно для action-oriented операций

### Оценка
- **Effort:** 3-4 дня
- **Maintainability:** 7/10
- **Simplicity:** 6/10

---

## Вариант B: Action-based API (Рекомендуемый)

### Концепция
Полный переход на action-based endpoint'ы в стиле Kontur/Stripe.

**Гибридный подход к параметрам (как у Kontur):**
- **Query string**: ключевые идентификаторы для роутинга (cluster_id, infobase_id)
- **Body**: детали операций (массивы, сложные структуры, опциональные параметры)

### Список endpoint'ов

```bash
# Discovery
GET  /api/v2/list-clusters?server={host:port}
GET  /api/v2/get-cluster?cluster_id={uuid}&server={host:port}

# Infobase Management
GET  /api/v2/list-infobases?cluster_id={uuid}
GET  /api/v2/get-infobase?cluster_id={uuid}&infobase_id={uuid}
POST /api/v2/create-infobase?cluster_id={uuid}
POST /api/v2/drop-infobase?cluster_id={uuid}&infobase_id={uuid}
POST /api/v2/lock-infobase?cluster_id={uuid}&infobase_id={uuid}
POST /api/v2/unlock-infobase?cluster_id={uuid}&infobase_id={uuid}
POST /api/v2/block-sessions?cluster_id={uuid}&infobase_id={uuid}
POST /api/v2/unblock-sessions?cluster_id={uuid}&infobase_id={uuid}

# Session Management
GET  /api/v2/list-sessions?cluster_id={uuid}&infobase_id={uuid}
POST /api/v2/terminate-session?cluster_id={uuid}&infobase_id={uuid}&session_id={uuid}
POST /api/v2/terminate-sessions?cluster_id={uuid}&infobase_id={uuid}  # batch
```

### Примеры curl

```bash
# Удаление базы (опция через body)
curl -X POST "http://localhost:8088/api/v2/drop-infobase?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab&\
infobase_id=ae1e5ea8-96e9-45cb-8363-8e4473daa269" \
  -H "Content-Type: application/json" \
  -d '{"drop_database": true}'

# Блокировка базы (без body - простая операция)
curl -X POST "http://localhost:8088/api/v2/lock-infobase?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab&\
infobase_id=ae1e5ea8-96e9-45cb-8363-8e4473daa269"

# Блокировка сеансов (детали через body)
curl -X POST "http://localhost:8088/api/v2/block-sessions?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab&\
infobase_id=ae1e5ea8-96e9-45cb-8363-8e4473daa269" \
  -H "Content-Type: application/json" \
  -d '{
    "denied_from": "2025-11-23T18:00:00",
    "denied_to": "2025-11-23T22:00:00",
    "denied_message": "Техническое обслуживание",
    "permission_code": "123456"
  }'

# Точечное завершение сеанса (ID через query string)
curl -X POST "http://localhost:8088/api/v2/terminate-session?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab&\
infobase_id=ae1e5ea8-96e9-45cb-8363-8e4473daa269&\
session_id=bd0704a7-3c03-4813-a29d-3b08d89c198c"

# Массовое завершение сеансов (массив через body)
curl -X POST "http://localhost:8088/api/v2/terminate-sessions?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab&\
infobase_id=ae1e5ea8-96e9-45cb-8363-8e4473daa269" \
  -H "Content-Type: application/json" \
  -d '{
    "session_ids": [
      "bd0704a7-3c03-4813-a29d-3b08d89c198c",
      "e3322514-ab12-4c34-9876-1234567890ab"
    ]
  }'

# Создание базы (сложная структура через body)
curl -X POST "http://localhost:8088/api/v2/create-infobase?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_new_database",
    "dbms": "PostgreSQL",
    "db_server": "localhost",
    "db_name": "test_new_database_db",
    "db_user": "postgres",
    "db_pwd": "postgres",
    "locale": "ru_RU",
    "create_database": true
  }'
```

### Плюсы и минусы

**Плюсы:**
- ✅ Очень короткие и понятные URL
- ✅ Легко читать и использовать
- ✅ Естественно для action-oriented операций
- ✅ Гибридный подход к параметрам (как у Kontur)
- ✅ Ключевые ID через query string (удобно для логирования/мониторинга)
- ✅ Детали через body (чистый JSON для сложных структур)
- ✅ Проще документировать
- ✅ Соответствует стилю Kontur API

**Минусы:**
- ❌ Отход от RESTful стандартов
- ❌ GET с фильтрами менее элегантны
- ❌ Больше endpoint'ов

### Оценка
- **Effort:** 5-7 дней
- **Maintainability:** 9/10
- **Simplicity:** 9/10

---

## Вариант C: Hybrid (Компромисс)

### Концепция
RESTful для CRUD операций, Action-based для бизнес-действий.

### Список endpoint'ов

```bash
# Resources (RESTful)
GET    /api/v2/clusters?server={host:port}
GET    /api/v2/clusters/{id}?server={host:port}
GET    /api/v2/infobases?cluster_id={uuid}
GET    /api/v2/infobases/{id}?cluster_id={uuid}
POST   /api/v2/infobases
DELETE /api/v2/infobases/{id}?cluster_id={uuid}&drop_database=true
GET    /api/v2/sessions?cluster_id={uuid}&infobase_id={uuid}

# Actions (Action-based)
POST /api/v2/lock-infobase
POST /api/v2/unlock-infobase
POST /api/v2/block-sessions
POST /api/v2/unblock-sessions
POST /api/v2/terminate-session
POST /api/v2/terminate-sessions
```

### Примеры curl

```bash
# CRUD: Получить информацию о базе (RESTful)
curl "http://localhost:8088/api/v2/infobases/ae1e5ea8-96e9-45cb-8363-8e4473daa269?\
cluster_id=6df8f45e-93a0-4e8f-b0c7-d123456789ab"

# ACTION: Заблокировать базу (Action-based)
curl -X POST "http://localhost:8088/api/v2/lock-infobase" \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_id": "6df8f45e-93a0-4e8f-b0c7-d123456789ab",
    "infobase_id": "ae1e5ea8-96e9-45cb-8363-8e4473daa269"
  }'
```

### Плюсы и минусы

**Плюсы:**
- ✅ Баланс между подходами
- ✅ CRUD остается RESTful
- ✅ Actions имеют короткие URL
- ✅ Гибкость

**Минусы:**
- ❌ Непоследовательность API
- ❌ Сложнее документировать
- ❌ Два разных стиля в одном API
- ❌ Путаница для разработчиков

### Оценка
- **Effort:** 4-5 дней
- **Maintainability:** 6/10
- **Simplicity:** 5/10

---

## Миграционная стратегия (для Варианта B)

### Подход: Параллельная поддержка v1 и v2

### Архитектура

```go
// router.go
func NewRouter(...) *gin.Engine {
    router := gin.New()

    // Health check (общий)
    router.GET("/health", Health())

    // API v1 (legacy) - текущая реализация
    v1 := router.Group("/api/v1")
    setupV1Routes(v1, services)

    // API v2 (action-based) - новая реализация
    v2 := router.Group("/api/v2")
    setupV2Routes(v2, services)

    return router
}
```

### Минимизация дублирования кода

```go
// internal/api/rest/v2/handlers.go
package v2

import (
    "github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
    v1handlers "github.com/commandcenter1c/commandcenter/ras-adapter/internal/api/rest/v1"
)

// LockInfobase - action-based wrapper над v1 логикой
func LockInfobase(svc *service.InfobaseService) gin.HandlerFunc {
    return func(c *gin.Context) {
        var req LockInfobaseRequest
        if err := c.ShouldBindJSON(&req); err != nil {
            c.JSON(400, gin.H{"error": err.Error()})
            return
        }

        // Переиспользуем бизнес-логику из service layer
        err := svc.LockInfobase(req.ClusterID, req.InfobaseID)
        if err != nil {
            c.JSON(500, gin.H{"error": err.Error()})
            return
        }

        c.JSON(200, gin.H{"success": true})
    }
}
```

### Timeline реализации

| Фаза | Описание | Длительность | Статус |
|------|----------|--------------|--------|
| **Phase 1** | Реализация v2 handlers | 3 дня | Week 5.1 |
| **Phase 2** | Тестирование v2 API | 2 дня | Week 5.2 |
| **Phase 3** | Документация OpenAPI | 1 день | Week 5.2 |
| **Phase 4** | Миграция клиентов | 2 дня | Week 5.3 |
| **Phase 5** | Deprecation v1 | - | Week 8+ |

### Breaking changes

**Подход:** Soft migration
- v1 остается работать без изменений
- v2 доступен параллельно
- Клиенты мигрируют по готовности
- v1 deprecated через 3 месяца
- v1 удален через 6 месяцев

### Версионирование в headers (опционально)

```bash
# Альтернатива URL версионированию
curl -X POST "http://localhost:8088/lock-infobase" \
  -H "API-Version: 2" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

---

## Сравнительная таблица

| Критерий | Вариант A (RESTful v2) | Вариант B (Action-based) | Вариант C (Hybrid) |
|----------|-------------------------|---------------------------|---------------------|
| **Простота использования** | 6/10 | 9/10 | 5/10 |
| **Краткость URL** | 4/10 | 10/10 | 7/10 |
| **Соответствие стандартам** | 10/10 | 6/10 | 8/10 |
| **Maintainability** | 7/10 | 9/10 | 6/10 |
| **Backwards compatibility** | 8/10 | 10/10 | 7/10 |
| **Effort (дни)** | 3-4 | 5-7 | 4-5 |
| **Consistency** | 10/10 | 10/10 | 4/10 |
| **ИТОГО** | 59/80 | 70/80 | 51/80 |

---

## Рекомендация

### Выбор: Вариант B (Action-based API с гибридными параметрами)

### Обоснование

1. **Простота использования** - короткие, понятные endpoint'ы существенно упрощают работу с API
2. **Соответствие требованиям** - заказчик явно просил "короткие и внятные endpoint'ы как у Kontur"
3. **Гибридный подход к параметрам** - как в Kontur API:
   - Ключевые ID (cluster_id, infobase_id) через query string
   - Детали операций (массивы, структуры) через body
4. **Единообразие** - все endpoint'ы следуют одному паттерну
5. **Maintainability** - легче добавлять новые действия
6. **Современный подход** - используется в Stripe, Twilio, Kontur
7. **Нет production клиентов** - можем позволить breaking changes

### Критерии выбора

- ✅ Простота > Соответствие RESTful стандартам
- ✅ Developer Experience > Академическая чистота
- ✅ Pragmatic > Purist подход
- ✅ Соответствие бизнес-логике 1С (action-oriented)
- ✅ Гибридные параметры > "Все через body" или "Все через query"

### Преимущества гибридного подхода

**Query string для ключевых ID:**
- Видны в логах и мониторинге (GET /api/v2/lock-infobase?cluster_id=...&infobase_id=...)
- Удобно для copy-paste в документации
- Легко добавлять в curl без JSON escaping
- Роутинг понятен из URL

**Body для деталей:**
- Сложные структуры (массивы session_ids)
- Опциональные параметры (denied_from, denied_to, denied_message)
- Валидация через JSON schema
- Не загромождает URL

---

## Next Steps

### Week 5.1 (2-3 дня)
1. Создать структуру v2 handlers
2. Реализовать все action-based endpoint'ы
3. Переиспользовать service layer из v1

### Week 5.2 (2-3 дня)
1. Написать интеграционные тесты
2. Создать OpenAPI спецификацию
3. Обновить Postman коллекцию

### Week 5.3 (1-2 дня)
1. Обновить документацию
2. Создать migration guide
3. Развернуть на staging

### Week 6+
1. Мониторинг использования v1 vs v2
2. Постепенная миграция клиентов
3. Deprecation notices для v1

---

## Примеры кода реализации

### 1. Структура проекта

```
go-services/ras-adapter/
├── internal/
│   ├── api/
│   │   ├── rest/
│   │   │   ├── router.go          # Общий роутер
│   │   │   ├── v1/                # Legacy API
│   │   │   │   ├── handlers.go
│   │   │   │   └── routes.go
│   │   │   └── v2/                # New action-based API
│   │   │       ├── handlers.go
│   │   │       ├── routes.go
│   │   │       └── types.go
│   │   └── middleware/
│   └── service/                   # Общий service layer
```

### 2. Пример v2 handler

```go
// internal/api/rest/v2/handlers.go
package v2

type BlockSessionsRequest struct {
    ClusterID      string    `json:"cluster_id" binding:"required,uuid"`
    InfobaseID     string    `json:"infobase_id" binding:"required,uuid"`
    DeniedFrom     time.Time `json:"denied_from"`
    DeniedTo       time.Time `json:"denied_to"`
    DeniedMessage  string    `json:"denied_message"`
    PermissionCode string    `json:"permission_code"`
}

func BlockSessions(svc *service.InfobaseService) gin.HandlerFunc {
    return func(c *gin.Context) {
        var req BlockSessionsRequest
        if err := c.ShouldBindJSON(&req); err != nil {
            c.JSON(400, ErrorResponse(err))
            return
        }

        params := service.BlockSessionsParams{
            ClusterID:      req.ClusterID,
            InfobaseID:     req.InfobaseID,
            DeniedFrom:     req.DeniedFrom,
            DeniedTo:       req.DeniedTo,
            DeniedMessage:  req.DeniedMessage,
            PermissionCode: req.PermissionCode,
        }

        if err := svc.BlockSessions(params); err != nil {
            c.JSON(500, ErrorResponse(err))
            return
        }

        c.JSON(200, SuccessResponse("Sessions blocked successfully"))
    }
}
```

### 3. OpenAPI спецификация (фрагмент)

```yaml
openapi: 3.0.0
info:
  title: RAS Adapter API v2
  version: 2.0.0
  description: Action-based API for 1C RAS management

paths:
  /api/v2/lock-infobase:
    post:
      summary: Lock an infobase
      operationId: lockInfobase
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - cluster_id
                - infobase_id
              properties:
                cluster_id:
                  type: string
                  format: uuid
                infobase_id:
                  type: string
                  format: uuid
      responses:
        '200':
          description: Infobase locked successfully
        '400':
          description: Bad request
        '500':
          description: Internal server error
```

---

## Заключение

Переход на action-based API (Вариант B) представляет оптимальное решение для RAS Adapter:

1. **Улучшает Developer Experience** через короткие, понятные endpoint'ы
2. **Соответствует требованиям заказчика** (стиль Kontur API)
3. **Упрощает поддержку** благодаря единообразию
4. **Не нарушает существующих интеграций** через параллельную поддержку v1
5. **Реализуем за 5-7 дней** с полным тестированием

Рекомендую начать реализацию в Week 5.1 с поэтапной миграцией клиентов.

---

**Документ подготовлен:** Senior Software Architect
**Дата:** 2025-11-23
**Версия:** 1.0