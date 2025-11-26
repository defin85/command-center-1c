# Сравнительный анализ REST API

> Анализ реализации REST API в трёх сервисах: RAS Adapter, API Gateway, Orchestrator

**Дата:** 2025-11-25

---

## Общая архитектура

| Аспект | RAS Adapter | API Gateway | Orchestrator |
|--------|-------------|-------------|--------------|
| **Язык** | Go 1.21+ | Go 1.21+ | Python 3.11+ |
| **Фреймворк** | Gin v1.11 | Gin v1.11 | Django 4.2 + DRF 3.14 |
| **Порт** | 8088 | 8080 | 8000 |
| **Swagger** | ✅ swaggo/gin-swagger | ❌ Не интегрирован | ✅ drf-spectacular |
| **API версионирование** | `/api/v1` + `/api/v2` | `/api/v1` | `/api/v1` |

---

## Паттерны роутинга

### RAS Adapter (Go/Gin)

Две версии API работают параллельно:

**v1 (Legacy RESTful):**
```
GET  /api/v1/clusters              # Список кластеров
GET  /api/v1/clusters/:id          # Кластер по ID
GET  /api/v1/infobases             # Список баз
POST /api/v1/infobases/:id/lock    # Блокировка базы
```

**v2 (Action-based):**
```
GET  /api/v2/list-clusters?server=...
GET  /api/v2/get-cluster?cluster_id=...&server=...
POST /api/v2/lock-infobase?cluster_id=...&infobase_id=...
```

**Ключевой файл:** `go-services/ras-adapter/internal/api/rest/router.go`

```go
func NewRouter(clusterSvc, infobaseSvc, sessionSvc, logger) *gin.Engine {
    router := gin.New()
    router.Use(middleware.Logger(logger))
    router.Use(middleware.Recovery(logger))

    // Health & Swagger
    router.GET("/health", Health())
    router.GET("/swagger/*any", ginSwagger.WrapHandler(swaggerFiles.Handler))

    // API v1 routes (legacy)
    apiV1 := router.Group("/api/v1")
    {
        apiV1.GET("/clusters", GetClusters(clusterSvc))
        apiV1.POST("/infobases/:infobase_id/lock", LockInfobase(infobaseSvc))
        // ...
    }

    // API v2 routes (action-based)
    apiV2 := router.Group("/api/v2")
    v2.SetupRoutes(apiV2, clusterSvc, infobaseSvc, sessionSvc)

    return router
}
```

---

### API Gateway (Go/Gin)

Reverse proxy к Orchestrator и другим сервисам:

```
/health                    → HealthCheck (local)
/metrics                   → Prometheus metrics
/api/v1/public/status      → GetStatus (no auth)
/api/v1/databases/*        → ProxyToOrchestrator()
/api/v1/operations/*       → ProxyToOrchestrator()
/api/v1/databases/clusters/* → ProxyToOrchestrator()
```

**Ключевой файл:** `go-services/api-gateway/internal/routes/router.go`

```go
func SetupRouter(cfg *config.Config) *gin.Engine {
    router := gin.New()
    router.Use(gin.Recovery())
    router.Use(middleware.LoggerMiddleware())
    router.Use(middleware.CORSMiddleware())

    router.GET("/health", handlers.HealthCheck)

    v1 := router.Group("/api/v1")
    {
        // Public routes
        public := v1.Group("/public")
        public.GET("/status", handlers.GetStatus)

        // Protected routes
        protected := v1.Group("")
        protected.Use(auth.AuthMiddleware(jwtManager))
        protected.Use(middleware.RateLimitMiddleware(100, time.Minute))
        {
            databases := protected.Group("/databases")
            databases.GET("", handlers.ProxyToOrchestrator)
            databases.GET("/:id", handlers.ProxyToOrchestrator)
            // ...
        }
    }
    return router
}
```

---

### Orchestrator (Django DRF)

DefaultRouter + custom actions:

```
/health                           → health_check
/api/token/                       → JWT obtain
/api/token/refresh/               → JWT refresh
/api/v1/databases/                → DatabaseViewSet (CRUD)
/api/v1/databases/{id}/health-check/  → Custom action
/api/v1/databases/bulk-health-check/  → Async (202)
/api/v1/operations/               → BatchOperationViewSet
/api/v1/operations/{id}/callback  → Worker callback
/api/v1/operations/{id}/stream    → SSE streaming
/api/v1/templates/                → OperationTemplateViewSet
/api/docs/                        → Swagger UI
```

**Ключевой файл:** `orchestrator/config/urls.py`

```python
urlpatterns = [
    path('health', health_check, name='health_check'),
    path('api/token/', TokenObtainPairView.as_view()),
    path('api/token/refresh/', TokenRefreshView.as_view()),
    path('api/v1/', include('apps.databases.urls')),
    path('api/v1/operations/', include('apps.operations.urls')),
    path('api/v1/templates/', include('apps.templates.urls')),
    path('api/docs/', SpectacularSwaggerView.as_view()),
]
```

**Ключевой файл:** `orchestrator/apps/databases/urls.py`

```python
router = DefaultRouter()
router.register('databases', DatabaseViewSet)
router.register('groups', DatabaseGroupViewSet)
router.register('clusters', ClusterViewSet)

urlpatterns = router.urls
```

---

## Middleware стек

| Middleware | RAS Adapter | API Gateway | Orchestrator |
|------------|-------------|-------------|--------------|
| **Logging** | ✅ Zap + маскировка паролей | ✅ Logrus | ✅ Django |
| **Recovery** | ✅ Custom panic handler | ✅ gin.Recovery() | ✅ Django |
| **CORS** | ❌ | ✅ Custom | ✅ django-cors-headers |
| **Auth** | ❌ | ✅ JWT (shared/auth) | ✅ ServiceJWTAuthentication |
| **Rate Limit** | ❌ | ✅ In-memory (100 req/min) | ❌ |

### RAS Adapter Middleware

**Logger с маскировкой паролей** (`internal/api/middleware/logger.go`):
```go
func Logger(logger *zap.Logger) gin.HandlerFunc {
    return func(c *gin.Context) {
        start := time.Now()
        c.Next()

        logger.Info("request completed",
            zap.String("method", c.Request.Method),
            zap.String("path", c.Request.URL.Path),
            zap.String("query", sanitizeQuery(query)),  // Маскирует password, token, api_key
            zap.Int("status", c.Writer.Status()),
            zap.Duration("latency", time.Since(start)),
        )
    }
}
```

### API Gateway Middleware

**JWT Authentication** (`go-services/shared/auth/middleware.go`):
```go
func AuthMiddleware(jwtManager *JWTManager) gin.HandlerFunc {
    return func(c *gin.Context) {
        authHeader := c.GetHeader("Authorization")
        // Extract "Bearer <token>"
        token := strings.TrimPrefix(authHeader, "Bearer ")

        claims, err := jwtManager.ValidateToken(token)
        if err != nil {
            c.JSON(401, gin.H{"error": "Invalid or expired token"})
            c.Abort()
            return
        }

        c.Set("user_id", claims.UserID)
        c.Set("roles", claims.Roles)
        c.Next()
    }
}
```

**Rate Limiting** (`internal/middleware/ratelimit.go`):
```go
func RateLimitMiddleware(requestsPerWindow int, window time.Duration) gin.HandlerFunc {
    return func(c *gin.Context) {
        clientID := getClientID(c)  // user_id или IP

        if !limiter.allow(clientID) {
            c.JSON(429, gin.H{"error": "Rate limit exceeded"})
            c.Abort()
            return
        }
        c.Next()
    }
}
```

### Orchestrator Authentication

**ServiceJWTAuthentication** (`apps/core/authentication.py`):
```python
class ServiceJWTAuthentication(JWTAuthentication):
    """Поддержка service-to-service tokens без создания user в БД"""

    def get_user(self, validated_token):
        user_id = validated_token.get(self.get_user_id_claim())

        # Service tokens: "service:api-gateway"
        if isinstance(user_id, str) and user_id.startswith('service:'):
            service_name = user_id.replace('service:', '', 1)
            return ServiceUser(service_name)  # Без DB lookup

        return super().get_user(validated_token)
```

---

## Валидация входных данных

### Go сервисы (RAS Adapter, API Gateway)

**Query параметры — ручная валидация:**
```go
// go-services/ras-adapter/internal/api/rest/v2/validation.go

func validateRequiredQueryParams(c *gin.Context, params ...string) bool {
    for _, param := range params {
        if c.Query(param) == "" {
            c.JSON(http.StatusBadRequest, ErrorResponse{
                Error: param + " is required",
                Code:  "MISSING_PARAMETER",
            })
            return false
        }
    }
    return true
}

func validateUUIDParams(c *gin.Context, params ...string) bool {
    for _, param := range params {
        if value := c.Query(param); value != "" && !isValidUUID(value) {
            c.JSON(http.StatusBadRequest, ErrorResponse{
                Error: param + " must be a valid UUID",
                Code:  "INVALID_UUID",
            })
            return false
        }
    }
    return true
}
```

**Request body — Gin binding с тегами:**
```go
type CreateInfobaseRequest struct {
    Name     string `json:"name" binding:"required"`
    DBMS     string `json:"dbms" binding:"required"`
    DBName   string `json:"db_name" binding:"required"`
    DBUser   string `json:"db_user"`
    DBPassword string `json:"db_password"`
}

// В handler:
var req CreateInfobaseRequest
if err := c.ShouldBindJSON(&req); err != nil {
    c.JSON(400, ErrorResponse{Error: "Invalid request body", Details: err.Error()})
    return
}
```

### Django DRF (Orchestrator)

**Serializer валидация (автоматическая):**
```python
# apps/databases/serializers.py

class DatabaseSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)  # Security!
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Database
        fields = ['id', 'name', 'host', 'port', 'password', 'status', ...]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Name too short")
        return value

    def validate(self, attrs):
        # Cross-field validation
        if attrs.get('port') and attrs['port'] < 1:
            raise serializers.ValidationError("Port must be positive")
        return attrs
```

---

## Формат ответов

### RAS Adapter v2 (структурированный)

```json
// Success - List
{
    "clusters": [{"uuid": "...", "name": "Main Cluster", "host": "localhost"}],
    "count": 1
}

// Success - Create
{
    "success": true,
    "infobase_id": "a1b2c3d4-...",
    "message": "Infobase created successfully"
}

// Success - Action
{
    "success": true,
    "message": "Infobase locked successfully"
}

// Error - Validation
{
    "error": "cluster_id is required",
    "code": "MISSING_PARAMETER"
}

// Error - Server
{
    "error": "Failed to retrieve clusters",
    "details": "connection refused"
}
```

### API Gateway (простой)

```json
// Health
{
    "status": "healthy",
    "service": "api-gateway",
    "timestamp": "2025-01-15T10:30:00Z",
    "version": "0.1.0"
}

// Error
{"error": "Authorization header required"}
{"error": "Rate limit exceeded"}
{"error": "Failed to proxy request"}
```

### Orchestrator DRF (стандартный)

```json
// List с пагинацией
{
    "count": 150,
    "next": "http://localhost:8000/api/v1/databases/?page=2",
    "previous": null,
    "results": [
        {"id": 1, "name": "accounting", "status": "active", ...}
    ]
}

// Single object
{
    "id": 1,
    "name": "accounting",
    "host": "192.168.1.100",
    "status": "active",
    "status_display": "Активна",
    "created_at": "2025-01-15T10:00:00Z"
}

// Async operation (202 Accepted)
{
    "task_id": "abc123-...",
    "status": "queued",
    "total_databases": 50
}

// Error - Not found
{"detail": "Not found."}

// Error - Validation
{"name": ["This field is required."], "port": ["Must be positive."]}

// Error - Permission
{"detail": "Authentication credentials were not provided."}
```

---

## OpenAPI/Swagger интеграция

| Сервис | Инструмент | Endpoint | Генерация |
|--------|-----------|----------|-----------|
| RAS Adapter | swaggo/gin-swagger | `/swagger/index.html` | Из аннотаций в коде |
| Orchestrator | drf-spectacular | `/api/docs/` | Автоматическая из ViewSets |
| API Gateway | — | — | Manual в `contracts/` |

### RAS Adapter — Swagger аннотации

```go
// go-services/ras-adapter/internal/api/rest/v2/handlers_cluster.go

// ListClusters retrieves all clusters from RAS server
// @Summary      List clusters
// @Description  Get list of all 1C clusters from RAS server
// @Tags         Clusters
// @Accept       json
// @Produce      json
// @Param        server    query     string  true  "RAS server address (host:port)"
// @Success      200  {object}  ClustersResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /list-clusters [get]
func ListClusters(svc ClusterService) gin.HandlerFunc {
    return func(c *gin.Context) {
        // ...
    }
}
```

### Orchestrator — drf-spectacular

```python
# apps/databases/views.py

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

class DatabaseViewSet(viewsets.ModelViewSet):

    @extend_schema(
        summary="Health check для одной базы",
        description="Проверяет доступность базы 1С через OData",
        responses={
            200: OpenApiResponse(description="Health check выполнен"),
            404: OpenApiResponse(description="База не найдена")
        }
    )
    @action(detail=True, methods=['post'], url_path='health-check')
    def health_check(self, request, pk=None):
        # ...
```

### Contract-First подход

```
contracts/
├── ras-adapter/openapi.yaml      # Спецификация RAS Adapter
├── api-gateway/openapi.yaml      # Спецификация API Gateway
└── scripts/
    ├── validate-specs.sh         # Валидация
    ├── generate-all.sh           # Генерация клиентов
    └── check-breaking-changes.sh # Проверка breaking changes
```

---

## Структура файлов

### RAS Adapter

```
go-services/ras-adapter/
├── cmd/
│   ├── main.go                    # Entry point
│   └── docs.go                    # Swagger metadata
├── internal/
│   ├── api/
│   │   ├── middleware/
│   │   │   ├── logger.go          # Logging + password masking
│   │   │   └── recovery.go        # Panic recovery
│   │   └── rest/
│   │       ├── router.go          # Main router
│   │       ├── health.go          # Health endpoint
│   │       ├── clusters.go        # v1 cluster handlers
│   │       ├── infobases.go       # v1 infobase handlers
│   │       └── v2/
│   │           ├── routes.go      # v2 route registration
│   │           ├── types.go       # Request/Response DTOs
│   │           ├── interfaces.go  # Service interfaces
│   │           ├── validation.go  # Validation helpers
│   │           ├── handlers_cluster.go
│   │           ├── handlers_infobase.go
│   │           └── handlers_session.go
│   ├── config/config.go
│   ├── models/
│   └── service/
├── docs/
│   ├── swagger.json
│   └── swagger.yaml
└── go.mod
```

### API Gateway

```
go-services/api-gateway/
├── cmd/main.go                    # Entry point
├── internal/
│   ├── handlers/
│   │   ├── health.go              # Health endpoints
│   │   └── databases.go           # ProxyToOrchestrator
│   ├── middleware/
│   │   ├── logger.go              # Request logging
│   │   └── ratelimit.go           # Rate limiting
│   └── routes/
│       └── router.go              # Main router
├── configs/config.yaml
└── go.mod
```

### Orchestrator

```
orchestrator/
├── config/
│   ├── urls.py                    # Main URL config
│   ├── settings/
│   │   ├── base.py                # REST_FRAMEWORK settings
│   │   └── development.py
│   └── wsgi.py
├── apps/
│   ├── health.py                  # Health endpoints
│   ├── core/
│   │   └── authentication.py      # ServiceJWTAuthentication
│   ├── databases/
│   │   ├── urls.py                # Router registration
│   │   ├── views.py               # ViewSets
│   │   ├── serializers.py         # Serializers
│   │   ├── models.py
│   │   └── services.py
│   ├── operations/
│   │   ├── urls.py
│   │   ├── views.py               # Callbacks, SSE
│   │   └── serializers.py
│   └── templates/
│       ├── views.py
│       └── engine/
└── requirements.txt
```

---

## Ключевые особенности

### RAS Adapter

1. **Две версии API** — v1 (RESTful) и v2 (Action-based) работают параллельно
2. **Гибридные параметры v2** — ID в query string, детали в body
3. **Dependency Injection** — через interfaces для тестируемости
4. **Маскировка паролей** — в логах автоматически скрываются sensitive данные
5. **Swagger из аннотаций** — swaggo генерирует документацию из комментариев

### API Gateway

1. **Чистый reverse proxy** — не содержит бизнес-логики
2. **Трансформация путей** — `/databases/clusters` → `/clusters` для Django
3. **Trailing slash** — автоматически добавляет для совместимости с Django
4. **JWT + Rate Limit** — централизованная защита для всех сервисов
5. **Shared auth package** — общий код аутентификации в `go-services/shared/auth/`

### Orchestrator

1. **DRF ViewSets** — автоматический CRUD + custom actions
2. **Nested serializers** — для связанных объектов
3. **ServiceJWTAuthentication** — service-to-service без DB lookup
4. **SSE Streaming** — real-time обновления через Redis Pub/Sub
5. **drf-spectacular** — автоматическая OpenAPI документация
6. **Celery интеграция** — async операции возвращают 202 Accepted

---

## HTTP Status коды

| Код | Использование |
|-----|---------------|
| 200 | Успешный GET/PUT/DELETE |
| 201 | Успешный POST (создание) |
| 202 | Accepted (async операция в очереди) |
| 204 | No Content (OPTIONS, DELETE без тела) |
| 400 | Bad Request (валидация) |
| 401 | Unauthorized (нет токена) |
| 403 | Forbidden (недостаточно прав) |
| 404 | Not Found |
| 429 | Too Many Requests (rate limit) |
| 500 | Internal Server Error |
| 502 | Bad Gateway (upstream недоступен) |

---

## Примеры запросов

### RAS Adapter v2

```bash
# Список кластеров
curl "http://localhost:8088/api/v2/list-clusters?server=localhost:1545"

# Создание базы
curl -X POST "http://localhost:8088/api/v2/create-infobase?cluster_id=550e8400-..." \
  -H "Content-Type: application/json" \
  -d '{"name": "accounting", "dbms": "PostgreSQL", "db_name": "acc_db"}'

# Блокировка базы
curl -X POST "http://localhost:8088/api/v2/lock-infobase?cluster_id=...&infobase_id=..." \
  -H "Content-Type: application/json" \
  -d '{"db_user": "admin", "db_password": "secret"}'
```

### API Gateway → Orchestrator

```bash
# Через Gateway (с JWT)
curl "http://localhost:8080/api/v1/databases/" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."

# Напрямую к Orchestrator
curl "http://localhost:8000/api/v1/databases/"
```

### Orchestrator

```bash
# Получить JWT токен
curl -X POST "http://localhost:8000/api/token/" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'

# Список баз с пагинацией
curl "http://localhost:8000/api/v1/databases/?page=1&page_size=20" \
  -H "Authorization: Bearer ..."

# Health check базы
curl -X POST "http://localhost:8000/api/v1/databases/1/health-check/" \
  -H "Authorization: Bearer ..."

# Bulk health check (async)
curl -X POST "http://localhost:8000/api/v1/databases/bulk-health-check/" \
  -H "Authorization: Bearer ..." \
  -H "Content-Type: application/json" \
  -d '{"database_ids": [1, 2, 3]}'
# Response: 202 {"task_id": "...", "status": "queued"}
```

---

**Версия:** 1.0
**Последнее обновление:** 2025-11-25
