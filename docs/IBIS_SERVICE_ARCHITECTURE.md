# ibis-service: Архитектурный план

> Java микросервис для работы с 1C RAS через официальный IBIS API
>
> **Статус:** Утвержден для реализации
> **Дата:** 2025-10-28
> **Версия:** 1.0

---

## Оглавление

1. [Резюме](#1-резюме)
2. [Контекст и проблема](#2-контекст-и-проблема)
3. [Технологический стек](#3-технологический-стек)
4. [Архитектура системы](#4-архитектура-системы)
5. [Структура проекта](#5-структура-проекта)
6. [API Спецификация](#6-api-спецификация)
7. [Ключевые компоненты](#7-ключевые-компоненты)
8. [План реализации](#8-план-реализации)
9. [Риски и митигация](#9-риски-и-митигация)
10. [Метрики успеха](#10-метрики-успеха)
11. [Полезные ссылки](#11-полезные-ссылки)

---

## 1. Резюме

### Цель

Создать новый Java микросервис `ibis-service` для работы с 1C Remote Administration Server (RAS) через официальный IBIS API SDK, который будет работать параллельно с существующим `installation-service` (Go + RAC CLI).

### Ключевые решения

- **Фреймворк:** Spring Boot 3.2 + Java 17 LTS
- **Build:** Gradle (Kotlin DSL)
- **Архитектура:** Layered (Controller → Service → Client) с Connection Pooling
- **API:** REST, полная совместимость с installation-service
- **Observability:** Actuator + Prometheus + Structured Logging
- **Deployment:** Docker (bootBuildImage)

### Преимущества

1. **Прямое взаимодействие с RAS** - без запуска rac.exe, без парсинга текста
2. **Лучшая производительность** - структурированные данные вместо text parsing
3. **Connection Pooling** - эффективная работа с 700+ базами
4. **Enterprise-ready** - Spring Boot ecosystem, proven solution
5. **Proven approach** - проект Alkir-RAHC уже использует Spring Boot 3 + IBIS SDK

### Timeline

**5 недель до production-ready:**
- Phase 1 (Week 1-2): MVP Foundation
- Phase 2 (Week 3-4): Production Features
- Phase 3 (Week 5): Observability & Hardening

---

## 2. Контекст и проблема

### Текущая архитектура

```
Orchestrator (Django) → installation-service (Go) → rac.exe → RAS (1545)
```

**Проблемы текущего подхода:**
- Запуск внешнего процесса `rac.exe` для каждого запроса
- Парсинг text output (проблемы с кодировкой Windows-1251)
- Нет connection pooling
- Overhead на создание процесса

### Решение

Создать параллельный сервис с прямым IBIS API:

```
                      ┌─→ installation-service (Go + RAC) → rac.exe → RAS
Orchestrator (Django) ─┤
                      └─→ ibis-service (Java + IBIS API) ────────────→ RAS
```

**Преимущества:**
- Прямое взаимодействие с RAS (без rac.exe)
- Структурированные данные (Java objects)
- Connection pooling для масштабирования
- Постепенный переход без breaking changes

### Доступные ресурсы

У нас уже есть:
- **1C IBIS SDK v1.6.7** в папке `com._1c.v8.ibis.admin-1.6.7/`
- JAR библиотеки (239 KB основная библиотека)
- Примеры кода в `samples/console/`
- Javadoc документация
- Готовое решение Alkir-RAHC на GitHub для референса

---

## 3. Технологический стек

### 3.1 Обоснованный выбор

#### Spring Boot 3.2+ ✅

**Выбрано:** Spring Boot 3.2 (latest stable)

**Обоснование:**
- **Mature ecosystem:** Огромное community (50K+ stars на GitHub)
- **Spring Boot Actuator:** Встроенные health checks, metrics
- **Enterprise-ready:** Подходит для production систем с 700+ базами
- **Совместимость:** Alkir-RAHC успешно использует Spring Boot 3.x
- **Observability:** Интеграция с Prometheus из коробки

**Альтернативы рассмотрены и отклонены:**
- **Quarkus:** Выигрыш в startup time не критичен для long-running service
- **Micronaut:** Меньшее community, сложнее найти готовые решения

#### Java 17 LTS ✅

**Обоснование:**
- **LTS support:** Long-Term Support до 2029 года
- **Совместимость:** IBIS SDK v1.6.7 требует Java 11+, работает с Java 17
- **Современные features:** Records, Sealed classes, Pattern matching
- **Performance:** Улучшенный GC, лучшая производительность чем Java 11

#### Gradle (Kotlin DSL) ✅

**Обоснование:**
- **Build speed:** 2-5x быстрее Maven для incremental builds
- **Kotlin DSL:** Type-safe конфигурация, лучше чем XML
- **Multi-module support:** Отлично масштабируется
- **Spring Boot integration:** bootBuildImage из коробки
- **Proven:** Alkir-RAHC использует Gradle + Kotlin DSL

### 3.2 Зависимости

```kotlin
// build.gradle.kts
dependencies {
    // Spring Boot Core
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    implementation("org.springframework.boot:spring-boot-starter-validation")

    // 1C IBIS API (local JARs)
    implementation(files("libs/com._1c.v8.ibis.admin-1.6.7.jar"))
    implementation(files("libs/com._1c.v8.core-1.0.30-SNAPSHOT.jar"))
    implementation(files("libs/com._1c.v8.ibis-1.1.1-SNAPSHOT.jar"))
    implementation(files("libs/com._1c.v8.ibis.swp-1.1.1-SNAPSHOT.jar"))
    implementation(files("libs/com._1c.v8.swp-1.0.3-SNAPSHOT.jar"))
    implementation(files("libs/com._1c.v8.swp.netty-1.0.3-SNAPSHOT.jar"))
    implementation(files("libs/netty-3.2.6.Final.jar"))

    // Connection Pooling
    implementation("org.apache.commons:commons-pool2:2.11.1")

    // Observability
    implementation("io.micrometer:micrometer-registry-prometheus")

    // Utilities
    implementation("org.projectlombok:lombok")
    annotationProcessor("org.projectlombok:lombok")

    // API Documentation
    implementation("org.springdoc:springdoc-openapi-starter-webmvc-ui:2.3.0")

    // Testing
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.mockito:mockito-core")
    testImplementation("org.testcontainers:testcontainers:1.19.3")
}
```

---

## 4. Архитектура системы

### 4.1 High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     ibis-service (Java 17 + Spring Boot 3.2)   │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐     REST API Layer                         │
│  │   Controller    │  ← Health, Infobases, Clusters, Sessions  │
│  │  (@RestController) │                                          │
│  └────────┬────────┘                                             │
│           │ DTOs (Request/Response)                              │
│           ▼                                                      │
│  ┌─────────────────┐     Business Logic Layer                   │
│  │    Service      │  ← Operations, Validation, Orchestration  │
│  │   (@Service)    │                                             │
│  └────────┬────────┘                                             │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────┐            │
│  │         RasClient (IBIS API Wrapper)            │            │
│  │  ┌──────────────────────────────────────────┐   │            │
│  │  │      RasConnectionPool                   │   │            │
│  │  │  ┌───────────┐  ┌───────────┐  ┌──────┐ │   │            │
│  │  │  │ Connection│  │ Connection│  │ ...  │ │   │            │
│  │  │  │  (Active) │  │   (Idle)  │  │      │ │   │            │
│  │  │  └───────────┘  └───────────┘  └──────┘ │   │            │
│  │  │  - borrow()                               │   │            │
│  │  │  - return()                               │   │            │
│  │  │  - health check                           │   │            │
│  │  └──────────────────────────────────────────┘   │            │
│  │                                                   │            │
│  │  Core Operations:                                │            │
│  │  - getClusters()                                 │            │
│  │  - getInfoBasesShort(clusterId)                  │            │
│  │  - getInfoBaseInfo(clusterId, infoBaseId)        │            │
│  │  - getSessions(clusterId)                        │            │
│  │  - terminateSession(clusterId, sessionId)        │            │
│  └─────────────────────────────────────────────────┘            │
│           │                                                      │
│           │ IBIS Protocol (Netty)                                │
│           ▼                                                      │
│  ┌─────────────────┐                                             │
│  │  IBIS SDK       │  ← com._1c.v8.ibis.admin-1.6.7.jar         │
│  │  (1C Libraries) │                                             │
│  └────────┬────────┘                                             │
└───────────┼────────────────────────────────────────────────────┘
            │
            │ TCP/IP (Port 1545)
            ▼
   ┌─────────────────┐
   │   1C RAS        │  ← 700+ Clusters
   │  (Remote Admin  │
   │    Server)      │
   └─────────────────┘

Observability:
├── Spring Boot Actuator (/actuator/health, /actuator/metrics)
├── Prometheus Metrics  (connection_pool_*, api_requests_*)
└── Structured Logging  (JSON format via Logback)
```

### 4.2 Integration Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    CommandCenter1C System                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │    Orchestrator (Django REST API)                        │    │
│  │                                                            │    │
│  │    - ClusterService.sync_infobases()                      │    │
│  │    - InstallationServiceClient (HTTP requests)            │    │
│  └───────────┬──────────────────────────┬────────────────────┘    │
│              │                          │                          │
│              │ HTTP (8086)              │ HTTP (8087)              │
│              ▼                          ▼                          │
│  ┌────────────────────┐    ┌─────────────────────────┐            │
│  │ installation-service│   │   ibis-service          │            │
│  │                     │    │                         │            │
│  │ Go + RAC CLI        │    │ Java + IBIS SDK         │            │
│  │ Port: 8086          │    │ Port: 8087              │            │
│  └──────────┬──────────┘    └────────────┬────────────┘            │
│             │                            │                          │
│             │ spawn rac.exe              │ IBIS Protocol            │
│             ▼                            ▼                          │
│        ┌────────┐                   ┌─────────┐                    │
│        │rac.exe │──────────────────▶│   RAS   │                    │
│        └────────┘   Text Protocol    │ :1545   │                    │
│                                      └─────────┘                    │
│                                                                      │
│  Deployment:                                                        │
│  - Docker Compose (development)                                    │
│  - Kubernetes (production)                                         │
└──────────────────────────────────────────────────────────────────┘
```

**Стратегия перехода:**
1. **Phase 1:** Оба сервиса работают параллельно
2. **Phase 2:** Orchestrator использует ibis-service для новых операций
3. **Phase 3:** Постепенная миграция всех операций на ibis-service
4. **Phase 4:** installation-service используется только для legacy endpoints

---

## 5. Структура проекта

```
ibis-service/
├── build.gradle.kts                 # Gradle build configuration (Kotlin DSL)
├── settings.gradle.kts              # Gradle settings
├── gradle/
│   └── wrapper/                     # Gradle wrapper files
├── gradlew                          # Gradle wrapper script (Unix)
├── gradlew.bat                      # Gradle wrapper script (Windows)
│
├── Dockerfile                       # Docker image build
├── docker-compose.yml               # Local development setup
├── .dockerignore                    # Docker ignore file
│
├── README.md                        # Project documentation
├── ARCHITECTURE.md                  # This file (copied from docs/)
├── CHANGELOG.md                     # Version history
│
├── libs/                            # 1C IBIS SDK JARs (local dependencies)
│   ├── com._1c.v8.ibis.admin-1.6.7.jar
│   ├── com._1c.v8.core-1.0.30-SNAPSHOT.jar
│   ├── com._1c.v8.ibis-1.1.1-SNAPSHOT.jar
│   ├── com._1c.v8.ibis.swp-1.1.1-SNAPSHOT.jar
│   ├── com._1c.v8.swp-1.0.3-SNAPSHOT.jar
│   ├── com._1c.v8.swp.netty-1.0.3-SNAPSHOT.jar
│   └── netty-3.2.6.Final.jar
│
└── src/
    ├── main/
    │   ├── java/com/commandcenter/ibis/
    │   │   │
    │   │   ├── IbisServiceApplication.java       # Spring Boot main class
    │   │   │
    │   │   ├── config/                           # Configuration classes
    │   │   │   ├── IbisProperties.java           # @ConfigurationProperties (application.yml)
    │   │   │   ├── ConnectionPoolConfig.java     # Connection pool beans
    │   │   │   ├── ObservabilityConfig.java      # Metrics, logging
    │   │   │   └── OpenApiConfig.java            # Swagger/OpenAPI configuration
    │   │   │
    │   │   ├── controller/                       # REST Controllers (API endpoints)
    │   │   │   ├── HealthController.java         # GET /api/v1/health
    │   │   │   ├── InfobaseController.java       # GET /api/v1/infobases
    │   │   │   ├── ClusterController.java        # GET /api/v1/clusters
    │   │   │   └── SessionController.java        # GET/DELETE /api/v1/sessions
    │   │   │
    │   │   ├── service/                          # Business Logic Layer
    │   │   │   ├── InfobaseService.java          # Infobase operations
    │   │   │   ├── ClusterService.java           # Cluster operations
    │   │   │   └── SessionService.java           # Session management
    │   │   │
    │   │   ├── client/                           # IBIS API Integration Layer
    │   │   │   ├── RasConnectionPool.java        # Object pool for IAgentAdminConnection
    │   │   │   ├── RasConnectionFactory.java     # Factory for creating connections
    │   │   │   ├── RasClient.java                # Low-level IBIS API wrapper
    │   │   │   └── RasClientException.java       # Custom exceptions
    │   │   │
    │   │   ├── dto/                              # Data Transfer Objects
    │   │   │   ├── request/
    │   │   │   │   ├── InfobaseListRequest.java  # Query parameters for GET /infobases
    │   │   │   │   ├── ClusterListRequest.java
    │   │   │   │   └── SessionTerminateRequest.java
    │   │   │   └── response/
    │   │   │       ├── InfobaseListResponse.java # Response for GET /infobases
    │   │   │       ├── InfobaseInfo.java         # Single infobase DTO
    │   │   │       ├── ClusterInfo.java          # Single cluster DTO
    │   │   │       ├── SessionInfo.java          # Single session DTO
    │   │   │       └── ErrorResponse.java        # Standard error format
    │   │   │
    │   │   ├── exception/                        # Exception handling
    │   │   │   ├── GlobalExceptionHandler.java   # @ControllerAdvice
    │   │   │   ├── RasConnectionException.java   # RAS connection errors
    │   │   │   └── RasAuthenticationException.java # Authentication errors
    │   │   │
    │   │   └── util/                             # Utilities
    │   │       ├── IbisMapper.java               # IBIS objects → DTOs mapping
    │   │       └── ValidationUtils.java          # Validation helpers
    │   │
    │   └── resources/
    │       ├── application.yml                   # Default configuration
    │       ├── application-dev.yml               # Development profile
    │       ├── application-prod.yml              # Production profile
    │       ├── logback-spring.xml                # Logging configuration
    │       └── banner.txt                        # Spring Boot startup banner
    │
    └── test/
        └── java/com/commandcenter/ibis/
            ├── IbisServiceApplicationTests.java   # Spring Boot context test
            │
            ├── controller/                        # Controller unit tests
            │   ├── InfobaseControllerTest.java
            │   ├── ClusterControllerTest.java
            │   └── SessionControllerTest.java
            │
            ├── service/                           # Service unit tests
            │   ├── InfobaseServiceTest.java
            │   ├── ClusterServiceTest.java
            │   └── SessionServiceTest.java
            │
            ├── client/                            # Client unit tests
            │   ├── RasConnectionPoolTest.java
            │   └── RasClientTest.java
            │
            └── integration/                       # Integration tests
                ├── InfobaseApiIntegrationTest.java
                └── HealthCheckIntegrationTest.java
```

---

## 6. API Спецификация

### 6.1 Design Principles

**Совместимость с installation-service:**
- Те же URL paths
- Тот же формат request/response
- Те же HTTP status codes
- Seamless migration для Orchestrator

**REST best practices:**
- HTTP verbs: GET, POST, DELETE
- Status codes: 2xx success, 4xx client errors, 5xx server errors
- JSON Content-Type
- Query parameters для фильтрации

### 6.2 Endpoints

#### GET /api/v1/health

**Описание:** Проверка состояния сервиса

**Query Parameters:** Нет

**Response 200 OK:**
```json
{
  "status": "UP",
  "timestamp": "2025-10-28T12:34:56Z",
  "components": {
    "ibisConnectionPool": {
      "status": "UP",
      "details": {
        "active": 3,
        "idle": 7,
        "total": 10,
        "maxTotal": 20
      }
    },
    "diskSpace": {
      "status": "UP"
    }
  }
}
```

**Response 503 Service Unavailable:**
```json
{
  "status": "DOWN",
  "timestamp": "2025-10-28T12:34:56Z",
  "components": {
    "ibisConnectionPool": {
      "status": "DOWN",
      "details": {
        "error": "Failed to connect to RAS"
      }
    }
  }
}
```

---

#### GET /api/v1/clusters

**Описание:** Получение списка кластеров

**Query Parameters:**
- `server` (required): RAS server address (format: "host:port")
  - Example: `localhost:1545`

**Response 200 OK:**
```json
{
  "status": "success",
  "clusters": [
    {
      "uuid": "81f8db64-f9d5-4cb6-b2f8-c6107f95f4e3",
      "name": "Local cluster",
      "host": "localhost",
      "port": 1541,
      "expirationTimeout": 60,
      "lifetimeLimit": 0
    }
  ],
  "total_count": 1,
  "duration_ms": 120,
  "timestamp": "2025-10-28T12:34:56Z"
}
```

**Response 502 Bad Gateway:**
```json
{
  "status": "error",
  "error": "ras_connection_failed",
  "message": "Failed to connect to RAS server localhost:1545: Connection refused",
  "timestamp": "2025-10-28T12:34:56Z",
  "path": "/api/v1/clusters"
}
```

---

#### GET /api/v1/infobases

**Описание:** Получение списка инфобаз

**Query Parameters:**
- `server` (required): RAS server address
- `cluster_user` (optional): Cluster admin username
- `cluster_pwd` (optional): Cluster admin password
- `detailed` (optional): Get full infobase info (default: `false`)
  - `false`: Fast, returns IInfoBaseInfoShort (minimal info)
  - `true`: Slow, returns full IInfoBaseInfo (all properties)

**Response 200 OK (detailed=false):**
```json
{
  "status": "success",
  "cluster_id": "81f8db64-f9d5-4cb6-b2f8-c6107f95f4e3",
  "cluster_name": "Local cluster",
  "total_count": 150,
  "infobases": [
    {
      "uuid": "abc123-def456-...",
      "name": "Accounting_Company1",
      "description": "Бухгалтерия Компания 1"
    },
    {
      "uuid": "def456-ghi789-...",
      "name": "Accounting_Company2",
      "description": ""
    }
  ],
  "duration_ms": 234,
  "timestamp": "2025-10-28T12:34:56Z"
}
```

**Response 200 OK (detailed=true):**
```json
{
  "status": "success",
  "cluster_id": "81f8db64-f9d5-4cb6-b2f8-c6107f95f4e3",
  "cluster_name": "Local cluster",
  "total_count": 150,
  "infobases": [
    {
      "uuid": "abc123-def456-...",
      "name": "Accounting_Company1",
      "description": "Бухгалтерия Компания 1",
      "dbms": "PostgreSQL",
      "db_server": "pg-server.local:5432",
      "db_name": "accounting_db",
      "db_user": "postgres",
      "security_level": 1,
      "connection_string": "",
      "locale": "ru_RU",
      "date_offset": 0,
      "scheduled_jobs_denied": false,
      "sessions_denied": false
    }
  ],
  "duration_ms": 1450,
  "timestamp": "2025-10-28T12:34:56Z"
}
```

**Response 401 Unauthorized:**
```json
{
  "status": "error",
  "error": "authentication_required",
  "message": "Cluster requires authentication. Provide cluster_user and cluster_pwd",
  "timestamp": "2025-10-28T12:34:56Z",
  "path": "/api/v1/infobases"
}
```

---

#### GET /api/v1/sessions

**Описание:** Получение списка активных сессий

**Query Parameters:**
- `server` (required): RAS server address
- `cluster_id` (required): Cluster UUID
- `cluster_user` (optional): Cluster admin username
- `cluster_pwd` (optional): Cluster admin password
- `infobase_id` (optional): Filter by specific infobase UUID

**Response 200 OK:**
```json
{
  "status": "success",
  "cluster_id": "81f8db64-f9d5-4cb6-b2f8-c6107f95f4e3",
  "sessions": [
    {
      "sid": "session-123-456-...",
      "infobase_id": "abc123-def456-...",
      "infobase_name": "Accounting_Company1",
      "user_name": "Administrator",
      "started_at": "2025-10-28T10:00:00Z",
      "app_id": "1CV8",
      "host": "workstation-01",
      "blocked_by_db_ms": 0,
      "blocked_by_ls": 0
    }
  ],
  "total_count": 45,
  "duration_ms": 310,
  "timestamp": "2025-10-28T12:34:56Z"
}
```

---

#### DELETE /api/v1/sessions/{session_id}

**Описание:** Принудительное завершение сессии

**Path Parameters:**
- `session_id`: Session ID (sid)

**Query Parameters:**
- `server` (required): RAS server address
- `cluster_id` (required): Cluster UUID
- `cluster_user` (optional): Cluster admin username
- `cluster_pwd` (optional): Cluster admin password

**Response 200 OK:**
```json
{
  "status": "success",
  "message": "Session terminated successfully",
  "session_id": "session-123-456-...",
  "timestamp": "2025-10-28T12:34:56Z"
}
```

**Response 404 Not Found:**
```json
{
  "status": "error",
  "error": "session_not_found",
  "message": "Session session-123-456-... not found in cluster 81f8db64-...",
  "timestamp": "2025-10-28T12:34:56Z",
  "path": "/api/v1/sessions/session-123-456-..."
}
```

---

### 6.3 Error Response Format

**Standard Error Response:**
```json
{
  "status": "error",
  "error": "error_code",
  "message": "Human-readable error message",
  "timestamp": "2025-10-28T12:34:56Z",
  "path": "/api/v1/endpoint"
}
```

**HTTP Status Codes:**
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (authentication failed)
- `404` - Not Found (cluster/infobase/session not found)
- `500` - Internal Server Error (unexpected error)
- `502` - Bad Gateway (failed to connect to RAS)
- `503` - Service Unavailable (RAS service down)
- `504` - Gateway Timeout (RAS request timeout)

**Error Codes:**
| Code | Description |
|------|-------------|
| `invalid_parameters` | Missing or invalid query parameters |
| `authentication_required` | Cluster requires admin credentials |
| `authentication_failed` | Invalid cluster credentials |
| `ras_connection_failed` | Cannot connect to RAS server |
| `ras_timeout` | RAS request timeout |
| `cluster_not_found` | Cluster UUID not found |
| `infobase_not_found` | Infobase UUID not found |
| `session_not_found` | Session not found |
| `internal_error` | Unexpected server error |

---

## 7. Ключевые компоненты

### 7.1 RasConnectionPool

**Назначение:** Управление пулом соединений к RAS для эффективного использования ресурсов

**Функциональность:**
- Создание и поддержка пула IAgentAdminConnection
- Автоматический reconnect при потере соединения
- Health checks для проверки состояния connections
- Thread-safe операции borrow/return
- Metrics для мониторинга (active, idle, total)

**Конфигурация (application.yml):**
```yaml
ibis:
  connection-pool:
    min-idle: 2                    # Минимум idle connections
    max-total: 20                  # Максимум total connections
    max-wait-millis: 5000          # Timeout на получение connection
    test-on-borrow: true           # Проверять connection перед выдачей
    test-while-idle: true          # Проверять idle connections
    time-between-eviction: 30000   # Health check interval (ms)
    max-idle-time: 300000          # Max idle time before eviction (5 min)
```

**Реализация (Object Pool Pattern):**
```java
@Component
@Slf4j
public class RasConnectionPool {
    private final GenericObjectPool<RasConnection> pool;

    public RasConnectionPool(RasConnectionFactory factory, IbisProperties properties) {
        GenericObjectPoolConfig<RasConnection> config = new GenericObjectPoolConfig<>();
        config.setMinIdle(properties.getConnectionPool().getMinIdle());
        config.setMaxTotal(properties.getConnectionPool().getMaxTotal());
        config.setMaxWaitMillis(properties.getConnectionPool().getMaxWaitMillis());
        config.setTestOnBorrow(properties.getConnectionPool().isTestOnBorrow());
        config.setTestWhileIdle(properties.getConnectionPool().isTestWhileIdle());
        config.setTimeBetweenEvictionRunsMillis(
            properties.getConnectionPool().getTimeBetweenEviction()
        );

        this.pool = new GenericObjectPool<>(factory, config);
    }

    public RasConnection borrowConnection(String server) throws Exception {
        log.debug("Borrowing RAS connection for server: {}", server);
        RasConnection conn = pool.borrowObject();
        log.debug("Borrowed connection. Active: {}, Idle: {}",
            pool.getNumActive(), pool.getNumIdle());
        return conn;
    }

    public void returnConnection(RasConnection conn) {
        log.debug("Returning RAS connection to pool");
        pool.returnObject(conn);
        log.debug("Returned connection. Active: {}, Idle: {}",
            pool.getNumActive(), pool.getNumIdle());
    }

    public PoolStats getStats() {
        return PoolStats.builder()
            .active(pool.getNumActive())
            .idle(pool.getNumIdle())
            .total(pool.getNumActive() + pool.getNumIdle())
            .maxTotal(pool.getMaxTotal())
            .build();
    }

    @PreDestroy
    public void destroy() {
        log.info("Closing RAS connection pool");
        pool.close();
    }
}
```

**RasConnectionFactory:**
```java
@Component
@Slf4j
public class RasConnectionFactory extends BasePooledObjectFactory<RasConnection> {
    private final IAgentAdminConnectorFactory connectorFactory;
    private final long connectionTimeout;

    @Override
    public RasConnection create() throws Exception {
        log.debug("Creating new RAS connection");
        IAgentAdminConnector connector = connectorFactory.createConnector(connectionTimeout);
        return new RasConnection(connector);
    }

    @Override
    public PooledObject<RasConnection> wrap(RasConnection conn) {
        return new DefaultPooledObject<>(conn);
    }

    @Override
    public boolean validateObject(PooledObject<RasConnection> p) {
        RasConnection conn = p.getObject();
        try {
            // Health check: try to get clusters
            conn.getConnection().getClusters();
            log.debug("Connection validation: OK");
            return true;
        } catch (Exception e) {
            log.warn("Connection validation failed: {}", e.getMessage());
            return false;
        }
    }

    @Override
    public void destroyObject(PooledObject<RasConnection> p) throws Exception {
        RasConnection conn = p.getObject();
        log.debug("Destroying RAS connection");
        conn.close();
    }
}
```

**Metrics (Micrometer):**
```java
@Component
@Slf4j
public class ConnectionPoolMetrics {
    private final RasConnectionPool pool;
    private final MeterRegistry registry;

    @PostConstruct
    public void registerMetrics() {
        Gauge.builder("ibis.connection.pool.active", pool, p -> p.getStats().getActive())
            .description("Active RAS connections")
            .register(registry);

        Gauge.builder("ibis.connection.pool.idle", pool, p -> p.getStats().getIdle())
            .description("Idle RAS connections")
            .register(registry);

        Gauge.builder("ibis.connection.pool.total", pool, p -> p.getStats().getTotal())
            .description("Total RAS connections")
            .register(registry);
    }
}
```

---

### 7.2 RasClient

**Назначение:** Low-level wrapper над IBIS SDK с автоматическим управлением connection lifecycle

**Ответственность:**
- Abstraction над IBIS API
- Автоматическое borrow/return connections из пула
- Retry logic при временных сбоях
- Конвертация IBIS exceptions в custom exceptions
- Метрики для monitoring

**Реализация:**
```java
@Component
@Slf4j
public class RasClient {
    private final RasConnectionPool pool;
    private final Counter requestCounter;
    private final Timer requestTimer;

    public RasClient(RasConnectionPool pool, MeterRegistry registry) {
        this.pool = pool;
        this.requestCounter = Counter.builder("ibis.ras.requests")
            .description("Total RAS API requests")
            .register(registry);
        this.requestTimer = Timer.builder("ibis.ras.request.duration")
            .description("RAS API request duration")
            .register(registry);
    }

    public List<IClusterInfo> getClusters(String server) {
        return executeWithConnection(server, conn -> {
            log.debug("Getting clusters from RAS: {}", server);
            List<IClusterInfo> clusters = conn.getClusters();
            log.info("Retrieved {} clusters from {}", clusters.size(), server);
            return clusters;
        });
    }

    public List<IInfoBaseInfoShort> getInfobasesShort(
        String server,
        UUID clusterId,
        String clusterUser,
        String clusterPwd
    ) {
        return executeWithConnection(server, conn -> {
            log.debug("Getting short infobases list: cluster={}", clusterId);

            // Authenticate if credentials provided
            if (clusterUser != null && !clusterUser.isEmpty()) {
                log.debug("Authenticating cluster: user={}", clusterUser);
                conn.authenticate(clusterId, clusterUser, clusterPwd);
            }

            List<IInfoBaseInfoShort> infobases = conn.getInfoBasesShort(clusterId);
            log.info("Retrieved {} infobases (short) from cluster {}",
                infobases.size(), clusterId);
            return infobases;
        });
    }

    public IInfoBaseInfo getInfobaseInfo(
        String server,
        UUID clusterId,
        UUID infobaseId,
        String clusterUser,
        String clusterPwd
    ) {
        return executeWithConnection(server, conn -> {
            log.debug("Getting full infobase info: cluster={}, infobase={}",
                clusterId, infobaseId);

            if (clusterUser != null && !clusterUser.isEmpty()) {
                conn.authenticate(clusterId, clusterUser, clusterPwd);
            }

            IInfoBaseInfo info = conn.getInfoBaseInfo(clusterId, infobaseId);
            log.info("Retrieved full info for infobase: {}", info.getName());
            return info;
        });
    }

    public List<ISessionInfo> getSessions(
        String server,
        UUID clusterId,
        String clusterUser,
        String clusterPwd
    ) {
        return executeWithConnection(server, conn -> {
            log.debug("Getting sessions: cluster={}", clusterId);

            if (clusterUser != null && !clusterUser.isEmpty()) {
                conn.authenticate(clusterId, clusterUser, clusterPwd);
            }

            List<ISessionInfo> sessions = conn.getSessions(clusterId);
            log.info("Retrieved {} sessions from cluster {}", sessions.size(), clusterId);
            return sessions;
        });
    }

    public void terminateSession(
        String server,
        UUID clusterId,
        String sessionId,
        String clusterUser,
        String clusterPwd
    ) {
        executeWithConnection(server, conn -> {
            log.info("Terminating session: cluster={}, session={}", clusterId, sessionId);

            if (clusterUser != null && !clusterUser.isEmpty()) {
                conn.authenticate(clusterId, clusterUser, clusterPwd);
            }

            conn.terminateSession(clusterId, sessionId);
            log.info("Session terminated successfully: {}", sessionId);
            return null;
        });
    }

    // Generic wrapper для всех операций
    private <T> T executeWithConnection(String server, RasOperation<T> operation) {
        RasConnection connection = null;

        return requestTimer.record(() -> {
            try {
                requestCounter.increment();

                // Borrow connection from pool
                connection = pool.borrowConnection(server);

                // Execute operation
                T result = operation.execute(connection.getConnection());

                return result;

            } catch (AgentAdminException e) {
                log.error("RAS API error: {}", e.getMessage(), e);
                throw new RasClientException(
                    "RAS API error: " + e.getMessage(),
                    e
                );
            } catch (Exception e) {
                log.error("Unexpected error: {}", e.getMessage(), e);
                throw new RasClientException(
                    "Unexpected error: " + e.getMessage(),
                    e
                );
            } finally {
                // Always return connection to pool
                if (connection != null) {
                    pool.returnConnection(connection);
                }
            }
        });
    }

    @FunctionalInterface
    private interface RasOperation<T> {
        T execute(IAgentAdminConnection conn) throws AgentAdminException;
    }
}
```

**Custom Exceptions:**
```java
public class RasClientException extends RuntimeException {
    public RasClientException(String message) {
        super(message);
    }

    public RasClientException(String message, Throwable cause) {
        super(message, cause);
    }
}

public class RasConnectionException extends RasClientException {
    public RasConnectionException(String message, Throwable cause) {
        super(message, cause);
    }
}

public class RasAuthenticationException extends RasClientException {
    public RasAuthenticationException(String message) {
        super(message);
    }
}
```

---

### 7.3 InfobaseService

**Назначение:** Business logic для операций с инфобазами

**Ответственность:**
- Validation входных параметров
- Orchestration нескольких RAS операций
- Mapping IBIS objects → DTOs
- Exception handling и retry logic
- Business rules enforcement

**Реализация:**
```java
@Service
@Slf4j
public class InfobaseService {
    private final RasClient rasClient;
    private final IbisMapper mapper;

    public InfobaseListResponse getInfobases(InfobaseListRequest request) {
        log.info("Getting infobases: server={}, detailed={}",
            request.getServer(), request.isDetailed());

        // 1. Validate parameters
        validateServerAddress(request.getServer());

        // 2. Get cluster info
        List<IClusterInfo> clusters = rasClient.getClusters(request.getServer());
        if (clusters.isEmpty()) {
            throw new RasClientException("No clusters found on server: " + request.getServer());
        }

        IClusterInfo cluster = clusters.get(0); // Use first cluster
        UUID clusterId = cluster.getUuid();

        // 3. Get infobases (short or detailed)
        if (request.isDetailed()) {
            return getDetailedInfobases(request, clusterId, cluster.getName());
        } else {
            return getShortInfobases(request, clusterId, cluster.getName());
        }
    }

    private InfobaseListResponse getShortInfobases(
        InfobaseListRequest request,
        UUID clusterId,
        String clusterName
    ) {
        long startTime = System.currentTimeMillis();

        List<IInfoBaseInfoShort> ibList = rasClient.getInfobasesShort(
            request.getServer(),
            clusterId,
            request.getClusterUser(),
            request.getClusterPwd()
        );

        long duration = System.currentTimeMillis() - startTime;

        return InfobaseListResponse.builder()
            .status("success")
            .clusterId(clusterId.toString())
            .clusterName(clusterName)
            .totalCount(ibList.size())
            .infobases(mapper.toInfoDtoListShort(ibList))
            .durationMs(duration)
            .timestamp(Instant.now())
            .build();
    }

    private InfobaseListResponse getDetailedInfobases(
        InfobaseListRequest request,
        UUID clusterId,
        String clusterName
    ) {
        long startTime = System.currentTimeMillis();

        // Step 1: Get short list (fast)
        List<IInfoBaseInfoShort> shortList = rasClient.getInfobasesShort(
            request.getServer(),
            clusterId,
            request.getClusterUser(),
            request.getClusterPwd()
        );

        // Step 2: Get detailed info for each infobase (slow)
        List<InfobaseInfo> detailedList = new ArrayList<>();
        for (IInfoBaseInfoShort shortInfo : shortList) {
            try {
                IInfoBaseInfo fullInfo = rasClient.getInfobaseInfo(
                    request.getServer(),
                    clusterId,
                    shortInfo.getUuid(),
                    request.getClusterUser(),
                    request.getClusterPwd()
                );
                detailedList.add(mapper.toInfoDto(fullInfo));
            } catch (Exception e) {
                log.warn("Failed to get detailed info for infobase {}: {}",
                    shortInfo.getName(), e.getMessage());
                // Fallback to short info
                detailedList.add(mapper.toInfoDtoShort(shortInfo));
            }
        }

        long duration = System.currentTimeMillis() - startTime;

        return InfobaseListResponse.builder()
            .status("success")
            .clusterId(clusterId.toString())
            .clusterName(clusterName)
            .totalCount(detailedList.size())
            .infobases(detailedList)
            .durationMs(duration)
            .timestamp(Instant.now())
            .build();
    }

    private void validateServerAddress(String server) {
        if (server == null || server.trim().isEmpty()) {
            throw new IllegalArgumentException("Server address is required");
        }

        // Validate format: host:port
        if (!server.matches("^[a-zA-Z0-9.-]+:\\d+$")) {
            throw new IllegalArgumentException(
                "Invalid server address format. Expected: host:port"
            );
        }
    }
}
```

---

### 7.4 IbisMapper

**Назначение:** Конвертация IBIS API objects в DTOs

**Реализация:**
```java
@Component
public class IbisMapper {

    public InfobaseInfo toInfoDto(IInfoBaseInfo ibis) {
        return InfobaseInfo.builder()
            .uuid(ibis.getUuid().toString())
            .name(ibis.getName())
            .description(ibis.getDescription())
            .dbms(ibis.getDBMS())
            .dbServer(ibis.getDBServerName())
            .dbName(ibis.getDBName())
            .dbUser(ibis.getDBUser())
            .securityLevel(ibis.getSecurityLevel())
            .connectionString(ibis.getConnectionString())
            .locale(ibis.getLocale())
            .dateOffset(ibis.getDateOffset())
            .scheduledJobsDenied(ibis.getScheduledJobsDenied())
            .sessionsDenied(ibis.getSessionsDenied())
            .build();
    }

    public InfobaseInfo toInfoDtoShort(IInfoBaseInfoShort ibis) {
        return InfobaseInfo.builder()
            .uuid(ibis.getUuid().toString())
            .name(ibis.getName())
            .description(ibis.getDescription())
            .build();
    }

    public List<InfobaseInfo> toInfoDtoList(List<IInfoBaseInfo> ibisList) {
        return ibisList.stream()
            .map(this::toInfoDto)
            .collect(Collectors.toList());
    }

    public List<InfobaseInfo> toInfoDtoListShort(List<IInfoBaseInfoShort> ibisList) {
        return ibisList.stream()
            .map(this::toInfoDtoShort)
            .collect(Collectors.toList());
    }

    public ClusterInfo toClusterDto(IClusterInfo ibis) {
        return ClusterInfo.builder()
            .uuid(ibis.getUuid().toString())
            .name(ibis.getName())
            .host(ibis.getHost())
            .port(ibis.getMainPort())
            .expirationTimeout(ibis.getExpirationTimeout())
            .lifetimeLimit(ibis.getLifetimeLimit())
            .build();
    }

    public SessionInfo toSessionDto(ISessionInfo ibis) {
        return SessionInfo.builder()
            .sid(ibis.getSid())
            .infobaseId(ibis.getInfoBase().toString())
            .userName(ibis.getUserName())
            .startedAt(ibis.getStartedAt())
            .appId(ibis.getAppID())
            .host(ibis.getHost())
            .blockedByDbMs(ibis.getBlockedByDbms())
            .blockedByLs(ibis.getBlockedByLS())
            .build();
    }
}
```

---

## 8. План реализации

### Phase 1: MVP Foundation (Week 1-2)

**Цель:** Базовый working prototype с основным функционалом

#### Week 1: Project Setup & Core Infrastructure (5 дней)

**Day 1-2: Project Setup**
- [ ] Создать Gradle проект (Kotlin DSL)
- [ ] Настроить Spring Boot 3.2 starter dependencies
- [ ] Скопировать IBIS JARs в `libs/`
- [ ] Написать `build.gradle.kts` с dependencies
- [ ] Настроить application.yml (базовая конфигурация)
- [ ] Написать Dockerfile
- [ ] Создать docker-compose.yml для локальной разработки
- [ ] Smoke test: `./gradlew build` успешно собирается

**Day 3-4: Core Infrastructure**
- [ ] Реализовать RasConnection wrapper (без pooling)
- [ ] Реализовать RasClient с базовыми методами:
  - `getClusters(server)`
  - `getInfobasesShort(server, clusterId, user, pwd)`
- [ ] Создать DTOs:
  - ClusterInfo
  - InfobaseInfo (minimal)
  - ErrorResponse
- [ ] Настроить GlobalExceptionHandler
- [ ] Unit tests для RasClient

**Day 5: Health Check**
- [ ] Реализовать HealthController
- [ ] GET /api/v1/health endpoint
- [ ] Health indicator для RAS connectivity
- [ ] Integration test для health check

**Deliverable Week 1:**
- ✅ Проект собирается без ошибок
- ✅ RasClient может подключиться к RAS
- ✅ Health check endpoint работает

---

#### Week 2: Basic API Implementation (5 дней)

**Day 1-2: Clusters API**
- [ ] Реализовать ClusterService
- [ ] Реализовать ClusterController
- [ ] GET /api/v1/clusters endpoint
- [ ] Unit tests для ClusterService
- [ ] Integration test: GET /api/v1/clusters

**Day 3-4: Infobases API (Short)**
- [ ] Реализовать InfobaseService.getInfobases(detailed=false)
- [ ] Реализовать InfobaseController
- [ ] GET /api/v1/infobases?detailed=false endpoint
- [ ] Request validation (@Valid, @NotNull)
- [ ] Unit tests для InfobaseService
- [ ] Integration test: GET /api/v1/infobases

**Day 5: Documentation & Testing**
- [ ] Добавить SpringDoc OpenAPI
- [ ] Swagger UI доступен на /swagger-ui.html
- [ ] README.md с инструкциями по запуску
- [ ] Manual testing против реального RAS
- [ ] Fix bugs найденные при тестировании

**Deliverable Week 2:**
- ✅ GET /api/v1/clusters работает
- ✅ GET /api/v1/infobases?detailed=false работает
- ✅ Swagger UI доступен
- ✅ Docker image собирается

---

### Phase 2: Production Features (Week 3-4)

**Цель:** Connection pooling, extended API, production-ready

#### Week 3: Connection Pooling (5 дней)

**Day 1-2: Object Pool Implementation**
- [ ] Добавить Apache Commons Pool dependency
- [ ] Реализовать RasConnectionFactory
- [ ] Реализовать RasConnectionPool с конфигурацией
- [ ] Обновить RasClient для использования пула
- [ ] Unit tests для pool

**Day 3: Pool Configuration & Health Checks**
- [ ] application.yml: connection pool settings
- [ ] Health check для пула (active/idle connections)
- [ ] Metrics для пула (Micrometer + Prometheus)
- [ ] Graceful shutdown для пула

**Day 4-5: Load Testing**
- [ ] JMeter test plan: 20 concurrent requests
- [ ] Stress test: 50 concurrent requests
- [ ] Validate: no connection leaks
- [ ] Tune pool parameters based on results
- [ ] Document optimal settings

**Deliverable Week 3:**
- ✅ Connection pool работает корректно
- ✅ 20+ concurrent requests без ошибок
- ✅ Metrics экспортируются в Prometheus
- ✅ Zero connection leaks

---

#### Week 4: Extended API (5 дней)

**Day 1-2: Detailed Infobases**
- [ ] InfobaseService.getInfobases(detailed=true)
- [ ] Parallel fetching для detailed info
- [ ] Fallback to short info при ошибке
- [ ] Integration test: GET /api/v1/infobases?detailed=true
- [ ] Performance test: 100 infobases

**Day 3: Sessions API**
- [ ] Реализовать SessionService
- [ ] Реализовать SessionController
- [ ] GET /api/v1/sessions endpoint
- [ ] DELETE /api/v1/sessions/{id} endpoint
- [ ] Unit tests
- [ ] Integration tests

**Day 4: Security & Configuration**
- [ ] application-dev.yml profile
- [ ] application-prod.yml profile
- [ ] Secure logging (mask passwords)
- [ ] Rate limiting (optional)
- [ ] Environment variable overrides

**Day 5: Testing & Bug Fixing**
- [ ] Test coverage > 70%
- [ ] Integration tests для всех endpoints
- [ ] Manual testing полного flow
- [ ] Fix all critical bugs

**Deliverable Week 4:**
- ✅ Full API compatibility с installation-service
- ✅ Test coverage > 70%
- ✅ Profiles configured (dev/prod)
- ✅ All endpoints работают корректно

---

### Phase 3: Observability & Hardening (Week 5)

**Цель:** Monitoring, documentation, production hardening

#### Week 5: Production Readiness (5 дней)

**Day 1-2: Observability**
- [ ] Structured logging (JSON format, Logback)
- [ ] Prometheus metrics endpoint
- [ ] Key metrics:
  - `ibis.connection.pool.*`
  - `ibis.ras.requests.*`
  - `ibis.api.requests.*`
- [ ] Grafana dashboard template
- [ ] Alerting rules template

**Day 3: Documentation**
- [ ] README.md: comprehensive guide
- [ ] ARCHITECTURE.md: this document
- [ ] API.md: OpenAPI spec export
- [ ] DEPLOYMENT.md: deployment guide
- [ ] TROUBLESHOOTING.md: common issues

**Day 4: Production Hardening**
- [ ] Graceful shutdown implementation
- [ ] Connection pool tuning (based on load tests)
- [ ] Error handling review
- [ ] Security review (no secrets in logs)
- [ ] Performance optimization

**Day 5: Load Testing & Release**
- [ ] Load test: 100 concurrent requests
- [ ] Stress test: до failure point
- [ ] Document performance characteristics
- [ ] Create release v1.0.0
- [ ] Deploy to staging environment

**Deliverable Week 5:**
- ✅ Production-ready service
- ✅ Full documentation
- ✅ Monitoring configured
- ✅ Load tested and tuned
- ✅ Release v1.0.0 created

---

### Success Criteria

**Phase 1 (MVP):**
- ✅ Service запускается и отвечает на requests
- ✅ GET /api/v1/infobases возвращает список из 10+ баз
- ✅ Response time < 500ms для short info
- ✅ Docker image собирается

**Phase 2 (Production):**
- ✅ Connection pool: 20 concurrent requests без ошибок
- ✅ Detailed info: response time < 2s для 100 баз
- ✅ Test coverage > 70%
- ✅ Zero connection leaks за 1 час работы

**Phase 3 (Hardening):**
- ✅ Prometheus metrics available
- ✅ Grafana dashboard deployed
- ✅ Swagger UI working
- ✅ Load test: 100 concurrent, 99% success rate
- ✅ Full documentation

---

## 9. Риски и митигация

### Риск 1: IBIS SDK Performance под нагрузкой

**Описание:** Неизвестно как IBIS SDK ведет себя при 50+ concurrent connections к RAS

**Вероятность:** Medium (30-50%)
**Влияние:** High (блокирует масштабирование)

**Митигация:**
1. **Phase 2 Week 3:** Load testing с постепенным увеличением:
   - 10 concurrent → 20 → 50 → 100
   - Мониторинг heap memory, thread count
2. **Conservative pool settings:** Начать с `max-total=20`
3. **Circuit breaker:** Защита RAS при overload
4. **Fallback plan:** Если pooling не работает:
   - Вернуться к одиночным connections
   - Использовать queue для throttling

**Индикаторы проблемы:**
- Memory leaks (heap растет без остановки)
- Thread exhaustion (deadlocks)
- Slow response times (> 5s для simple requests)

---

### Риск 2: Memory Leaks в IBIS SDK

**Описание:** IBIS SDK использует Netty 3.2.6 (2011 год) - старая версия, возможны memory leaks

**Вероятность:** Low (10-20%)
**Влияние:** High (требует restarts)

**Митигация:**
1. **Code review:** Обязательное использование try-finally для connections
2. **Health checks:** Periodic validation для обнаружения "зависших" connections
3. **Monitoring:**
   - Prometheus metric: `jvm.memory.used`
   - Alert при > 80% heap usage
4. **Graceful restart:** При критичных метриках памяти
5. **Heap dump analysis:** При подозрении на leak

**Fallback plan:**
- Scheduled nightly restart (если leak медленный)
- Upgrade to newer IBIS SDK version (если доступна)

---

### Риск 3: Несовместимость IBIS SDK с Java 17

**Описание:** IBIS SDK v1.6.7 документация говорит о Java 5+, тестировался с Java 8/11

**Вероятность:** Low (5-10%)
**Влияние:** Medium (придется downgrade Java)

**Митигация:**
1. **Phase 1 Day 1:** Smoke test на Java 17:
   - Запустить sample console application
   - Проверить основные операции
2. **Fallback plan:** Использовать Java 11 LTS (support до 2027)
3. **Docker image:** Зафиксировать версию JDK в Dockerfile

**Тест для проверки:**
```bash
# Day 1 smoke test
cd com._1c.v8.ibis.admin-1.6.7/samples/console
export JAVA_HOME=/path/to/jdk-17
ant compile
ant run
# Если работает → OK
# Если ошибки → downgrade to Java 11
```

---

### Риск 4: Обратная совместимость API

**Описание:** Orchestrator (Django) ожидает точно такой же response format как у installation-service

**Вероятность:** Medium (30%)
**Влияние:** Medium (требует изменения Orchestrator)

**Митигация:**
1. **Phase 1 Week 2:** Integration tests против Orchestrator:
   ```python
   # Test: Orchestrator.ClusterService.sync_infobases()
   # Should work with both services seamlessly
   ```
2. **API Versioning:** `/api/v1` vs `/api/v2`
3. **Feature toggle:** Config для переключения между services:
   ```yaml
   # Orchestrator config
   cluster:
     backend: ibis-service  # or installation-service
   ```
4. **Documentation:** Четко документировать все API changes

---

### Риск 5: RAS сервер недоступен

**Описание:** RAS может быть down, network issues, firewall

**Вероятность:** Medium (регулярно в production)
**Влияние:** High (service не работает)

**Митигация:**
1. **Health check:** `/actuator/health` показывает RAS connectivity
2. **Retry logic:** 3 retries с exponential backoff
3. **Circuit breaker:** После N failures - fail fast
4. **Graceful degradation:** Return cached data (if applicable)
5. **Monitoring:** Alert при RAS down

**Error response:**
```json
{
  "status": "error",
  "error": "ras_connection_failed",
  "message": "Cannot connect to RAS server localhost:1545: Connection refused",
  "retries": 3,
  "timestamp": "2025-10-28T12:34:56Z"
}
```

---

## 10. Метрики успеха

### 10.1 Phase 1 (MVP) - Week 2

**Functionality:**
- ✅ Service запускается без ошибок
- ✅ Health check: `/api/v1/health` returns HTTP 200
- ✅ Clusters API: `/api/v1/clusters` returns cluster list
- ✅ Infobases API: `/api/v1/infobases` returns 10+ infobases

**Performance:**
- ✅ Response time < 500ms для GET /api/v1/infobases (short)
- ✅ Response time < 2s для GET /api/v1/clusters

**Quality:**
- ✅ Zero crashes за 1 час работы
- ✅ Docker image < 300 MB
- ✅ Build time < 2 minutes

---

### 10.2 Phase 2 (Production) - Week 4

**Functionality:**
- ✅ All endpoints working: /clusters, /infobases, /sessions
- ✅ Detailed infobases: `?detailed=true` works
- ✅ Session termination: DELETE /sessions/{id} works

**Performance:**
- ✅ Connection pool handles 20 concurrent requests
- ✅ Response time < 2s для detailed info (100 infobases)
- ✅ Throughput: 50+ requests/second

**Reliability:**
- ✅ Zero connection leaks за 1 час continuous load
- ✅ Graceful shutdown: all connections closed properly
- ✅ Health check reflects connection pool state

**Quality:**
- ✅ Test coverage > 70% (unit + integration)
- ✅ Zero critical bugs
- ✅ Documentation complete

---

### 10.3 Phase 3 (Hardening) - Week 5

**Observability:**
- ✅ Prometheus metrics endpoint working
- ✅ Grafana dashboard shows key metrics:
  - Request rate
  - Response time (p50, p95, p99)
  - Connection pool stats
  - Error rate
- ✅ Structured logging (JSON format)
- ✅ Log levels configurable via environment

**Performance:**
- ✅ Load test: 100 concurrent requests
  - Success rate > 99%
  - p95 response time < 3s
  - p99 response time < 5s
- ✅ Stress test: Peak throughput 100+ req/s
- ✅ Memory stable (no leaks) за 8 hours

**Production Readiness:**
- ✅ Deployment guide complete
- ✅ Troubleshooting guide available
- ✅ Kubernetes manifests ready
- ✅ CI/CD pipeline configured

---

### 10.4 KPIs для production monitoring

**Availability:**
- Target: 99.5% uptime
- Metric: `up{job="ibis-service"}`

**Performance:**
- Target: p95 response time < 2s
- Metric: `ibis_api_requests_duration_seconds{quantile="0.95"}`

**Reliability:**
- Target: Error rate < 1%
- Metric: `rate(ibis_api_requests_total{status="error"}[5m])`

**Resource Usage:**
- Target: Heap memory < 80%
- Metric: `jvm_memory_used_bytes / jvm_memory_max_bytes`

**Connection Pool:**
- Target: Active connections < 80% of max
- Metric: `ibis_connection_pool_active / ibis_connection_pool_max`

---

## 11. Полезные ссылки

### Найденные готовые решения

**Alkir-RAHC (GitHub):**
- URL: https://github.com/DigiLabsru/alkir-rahc
- Description: Remote Administration Hamster Cage - Spring Boot + IBIS SDK
- Stack: Spring Boot 3.x, Gradle (Kotlin DSL), Java
- Функциональность: REST API + JSON-RPC для работы с RAS
- **Вывод:** Проверенное решение, можно использовать как референс

**MinimaJack Repository:**
- URL: https://github.com/MinimaJack/repository
- Description: Maven repository с JAR-ами IBIS SDK (неофициальный)
- **Внимание:** Легальность использования под вопросом (требует лицензию 1C)

---

### Spring Boot лучшие практики

**Spring Boot Best Practices:**
- URL: https://github.com/abhisheksr01/spring-boot-microservice-best-practices
- Topics: Layered architecture, exception handling, testing

**Baeldung Spring Boot:**
- URL: https://www.baeldung.com/spring-boot
- Topics: Comprehensive Spring Boot tutorials

**Spring Boot Production-Ready Features:**
- URL: https://docs.spring.io/spring-boot/docs/current/reference/html/actuator.html
- Topics: Actuator, metrics, health checks

---

### Connection Pooling

**Apache Commons Pool:**
- URL: https://commons.apache.org/proper/commons-pool/
- Description: Generic object pooling implementation
- Guide: https://www.baeldung.com/java-connection-pooling

**Object Pool Pattern:**
- URL: https://en.wikipedia.org/wiki/Object_pool_pattern
- Description: Design pattern for resource management

---

### Observability

**Micrometer:**
- URL: https://micrometer.io/docs
- Description: Metrics facade (Prometheus integration)

**Prometheus:**
- URL: https://prometheus.io/
- Docs: https://prometheus.io/docs/introduction/overview/

**Grafana:**
- URL: https://grafana.com/
- Dashboards: https://grafana.com/grafana/dashboards/

---

### Инструменты

**Gradle:**
- URL: https://gradle.org/
- Docs: https://docs.gradle.org/current/userguide/userguide.html
- Kotlin DSL: https://docs.gradle.org/current/userguide/kotlin_dsl.html

**SpringDoc OpenAPI:**
- URL: https://springdoc.org/
- Swagger UI integration для Spring Boot 3

**JMeter:**
- URL: https://jmeter.apache.org/
- Description: Load testing tool

---

### Документация 1C

**1C Administrative Service API:**
- Официальный URL: https://1c-dn.com/library/1c_enterprise_8_administrative_service_api/
- **Требует:** Регистрация продукта с номером и PIN-кодом
- Содержит: Javadoc, примеры, best practices

---

## 12. Приложения

### A. Пример конфигурации (application.yml)

```yaml
# application.yml (default)
server:
  port: 8087
  shutdown: graceful

spring:
  application:
    name: ibis-service
  lifecycle:
    timeout-per-shutdown-phase: 30s

# IBIS Configuration
ibis:
  # Default RAS server (can be overridden by request parameter)
  ras:
    default-server: localhost:1545
    connection-timeout: 30000  # 30 seconds

  # Connection Pool
  connection-pool:
    min-idle: 2
    max-total: 20
    max-wait-millis: 5000
    test-on-borrow: true
    test-while-idle: true
    time-between-eviction: 30000
    max-idle-time: 300000  # 5 minutes

# Actuator (Health & Metrics)
management:
  endpoints:
    web:
      exposure:
        include: health,metrics,prometheus
  endpoint:
    health:
      show-details: when-authorized
  metrics:
    export:
      prometheus:
        enabled: true

# Logging
logging:
  level:
    com.commandcenter.ibis: INFO
    org.springframework.web: WARN
  pattern:
    console: '%d{yyyy-MM-dd HH:mm:ss} - %logger{36} - %msg%n'

# Swagger/OpenAPI
springdoc:
  api-docs:
    path: /api-docs
  swagger-ui:
    path: /swagger-ui.html
```

```yaml
# application-dev.yml (development)
logging:
  level:
    com.commandcenter.ibis: DEBUG
    com._1c.v8.ibis: DEBUG

ibis:
  connection-pool:
    max-total: 5  # Lower for dev
```

```yaml
# application-prod.yml (production)
server:
  shutdown: graceful

ibis:
  connection-pool:
    min-idle: 5
    max-total: 50

logging:
  level:
    com.commandcenter.ibis: INFO
  pattern:
    console: '{"timestamp":"%d{yyyy-MM-dd HH:mm:ss}","level":"%level","logger":"%logger","message":"%msg"}%n'
```

---

### B. Dockerfile

```dockerfile
# Multi-stage build
FROM eclipse-temurin:17-jdk-alpine AS builder

WORKDIR /app

# Copy Gradle wrapper and build files
COPY gradle gradle
COPY gradlew .
COPY build.gradle.kts .
COPY settings.gradle.kts .

# Copy source code and libs
COPY src src
COPY libs libs

# Build application (skip tests for faster build)
RUN ./gradlew clean bootJar -x test

# Runtime image
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Copy JAR from builder stage
COPY --from=builder /app/build/libs/*.jar app.jar

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8087/actuator/health || exit 1

# Expose port
EXPOSE 8087

# Run application
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

### C. docker-compose.yml

```yaml
version: '3.8'

services:
  # 1C RAS Server (mock or real)
  ras:
    image: # TODO: Add RAS Docker image if available
    ports:
      - "1545:1545"
    networks:
      - ibis-network

  # ibis-service
  ibis-service:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ibis-service
    ports:
      - "8087:8087"
    environment:
      - SPRING_PROFILES_ACTIVE=dev
      - IBIS_RAS_DEFAULT_SERVER=ras:1545
    depends_on:
      - ras
    networks:
      - ibis-network
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:8087/actuator/health"]
      interval: 30s
      timeout: 3s
      retries: 3

  # Prometheus (monitoring)
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    networks:
      - ibis-network

  # Grafana (dashboards)
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus
    networks:
      - ibis-network

networks:
  ibis-network:
    driver: bridge

volumes:
  prometheus_data:
  grafana_data:
```

---

### D. Prometheus configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ibis-service'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets: ['ibis-service:8087']
```

---

## Changelog

### v1.0 (2025-10-28)
- Initial architectural plan
- Technology stack selection: Spring Boot 3.2 + Java 17
- API specification (compatibility with installation-service)
- Connection pooling design
- 3-phase implementation plan (5 weeks)
- Risk analysis and mitigation strategies

---

## Заключение

Этот архитектурный план представляет детальный подход к созданию production-ready Java микросервиса `ibis-service` для работы с 1C RAS через официальный IBIS API.

**Ключевые преимущества решения:**
1. ✅ **Proven approach:** Alkir-RAHC доказывает работоспособность
2. ✅ **Performance:** Прямой IBIS API быстрее чем RAC CLI
3. ✅ **Scalability:** Connection pooling для 700+ баз
4. ✅ **Maintainability:** Spring Boot ecosystem, знакомый стек
5. ✅ **Observability:** Встроенный monitoring

**Timeline:** 5 недель до production-ready (реально достижимо)

**Next Steps:**
1. Утверждение плана пользователем
2. Phase 1 Week 1: Project setup
3. Phase 1 Week 2: Basic API
4. Phase 2: Production features
5. Phase 3: Production hardening

---

**Prepared by:** Claude (Anthropic AI)
**Date:** 2025-10-28
**Version:** 1.0
**Status:** ✅ Готов к реализации
