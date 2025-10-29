# ibis-service: Go архитектура

> Go микросервис для работы с 1C RAS - гибридная стратегия интеграции
>
> **Статус:** ✅ РЕШЕНИЕ ПРИНЯТО - Форк ras-grpc-gw + доработка
> **Дата:** 2025-10-29
> **Версия:** 1.1

---

## 🎯 ФИНАЛЬНОЕ РЕШЕНИЕ (2025-10-29)

**Принято решение:** Форкнуть и доработать `v8platform/ras-grpc-gw`

### Почему этот подход?

✅ **Pure Go решение** - идеальная интеграция с monorepo
✅ **Уже есть 80% функционала** - кластеры, базы, сессии работают
✅ **MIT лицензия** - можем свободно дорабатывать
✅ **Минимальные ресурсы** - ~10-50 MB памяти vs Java ~100-500 MB
✅ **Быстрый старт** - <1 секунда vs Java ~5-10 секунд

### Что нужно добавить?

❌ **ExtensionsService** - установка расширений 1С:
- `InstallExtension()` - установить расширение .cfe
- `GetExtensions()` - список установленных расширений
- `UpdateExtension()` - обновить расширение
- `DeleteExtension()` - удалить расширение

### План реализации

**Week 1-2:** Форк, изучение кода, запуск локально
**Week 3-4:** Проектирование ExtensionsService (protobuf + Go)
**Week 5-6:** Изучение RAS протокола для extensions
**Week 7-8:** Реализация ExtensionsService
**Week 9-10:** Интеграция с ibis-service + тесты

---

## Оглавление

1. [Резюме](#1-резюме)
2. [Контекст и проблема](#2-контекст-и-проблема)
3. [Анализ вариантов интеграции](#3-анализ-вариантов-интеграции)
4. [Выбранная стратегия](#4-выбранная-стратегия)
5. [Архитектура системы](#5-архитектура-системы)
6. [Технологический стек](#6-технологический-стек)
7. [Структура проекта](#7-структура-проекта)
8. [API Спецификация](#8-api-спецификация)
9. [Ключевые компоненты](#9-ключевые-компоненты)
10. [План реализации](#10-план-реализации)
11. [Риски и митигация](#11-риски-и-митигация)
12. [Метрики успеха](#12-метрики-успеха)

---

## 1. Резюме

### Цель

Создать Go микросервис `ibis-service` для работы с 1C Remote Administration Server (RAS), обеспечивающий прямое взаимодействие без RAC CLI и масштабируемость до 700+ баз данных.

### Ключевые решения

- **Язык:** Go 1.21+ (интеграция с monorepo)
- **Фреймворк:** Gin (REST API)
- **Архитектура:** Strategy Pattern для переключения между клиентами RAS
- **Стратегия:** Hybrid Approach - постепенный переход RAC → gRPC → Production
- **Connection Pooling:** gRPC (10-20 connections) или HTTP (MaxIdleConnsPerHost: 10)
- **Observability:** Prometheus + Structured Logging (go-services/shared)

### Гибридная стратегия (РЕКОМЕНДУЕТСЯ)

**Phase 1-2 (Week 1-6):** Continue with RAC CLI ✅
- Текущий подход стабилен
- Дает время на тестирование альтернатив
- Используется installation-service как есть

**Phase 2-3 (Week 7-12):** Test ras-grpc-gw on staging 🧪
- Тестирование v8platform/ras-grpc-gw
- Проверка стабильности и производительности
- Сравнение с RAC baseline

**Phase 3+ (Week 13+):** Choose best solution 🎯
- **IF stable:** Migrate to ras-grpc-gw (pure Go)
- **IF unstable:** Fallback to Java Bridge (fork Alkir-RAHC)

### Преимущества

1. **Консистентность стека** - все в Go (monorepo)
2. **Минимальный риск** - сначала тестируем, потом мигрируем
3. **Гибкость** - Strategy Pattern позволяет переключать клиенты
4. **Масштабируемость** - connection pooling для 700+ баз
5. **Observability** - переиспользуем go-services/shared

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

### Целевая архитектура

```
                      ┌─→ installation-service (Go + RAC) [Legacy]
Orchestrator (Django) ─┤
                      └─→ ibis-service (Go + gRPC/HTTP) ──────────→ RAS
```

**Преимущества:**
- Прямое взаимодействие с RAS
- Структурированные данные (protobuf/JSON)
- Connection pooling
- Постепенный переход без breaking changes

### Почему Go, а не Java?

| Критерий | Go | Java |
|----------|----|----|
| Интеграция с monorepo | ✅ Нативная | ⚠️ Отдельный стек |
| Потребление памяти | ✅ ~10-50 MB | ❌ ~100-500 MB (JVM) |
| Время старта | ✅ <1 секунда | ⚠️ 5-10 секунд |
| Dependency management | ✅ go.mod (простой) | ⚠️ Gradle/Maven |
| Переиспользование кода | ✅ go-services/shared | ❌ Новый codebase |
| Concurrency | ✅ Goroutines (нативные) | ⚠️ Threads/Virtual threads |

**Вердикт:** Go лучше подходит для нашего monorepo и требований к производительности.

---

## 3. Анализ вариантов интеграции

### Вариант A: JNI + CGO (JAVA ↔ Go прямая интеграция)

**Как работает:**
```
Go → CGO → JNI → Java IBIS SDK → RAS
```

**Плюсы:**
- Прямая интеграция Go + Java
- Переиспользование IBIS SDK

**Минусы:**
- ❌ Очень сложная настройка
- ❌ Проблемы с garbage collection
- ❌ Нестабильность (JNI crashes могут уронить Go процесс)
- ❌ Плохая отладка
- ❌ Сложность с cross-platform builds

**Вердикт:** ❌ **НЕ РЕКОМЕНДУЕТСЯ** - слишком сложно для production

---

### Вариант B: Java Bridge Microservice (HTTP Wrapper)

**Как работает:**
```
Go (ibis-service) → HTTP → Java Bridge → IBIS SDK → RAS
```

**Архитектура:**
```
┌─────────────────┐
│  ibis-service   │ Go + Gin (Port 8087)
│  (Go REST API)  │
└────────┬────────┘
         │ HTTP/REST
┌────────▼────────┐
│ Java Bridge     │ Spring Boot (Port 9090)
│ (IBIS Wrapper)  │
└────────┬────────┘
         │ IBIS SDK
┌────────▼────────┐
│      RAS        │ Port 1545
└─────────────────┘
```

**Плюсы:**
- ✅ Простая интеграция (HTTP REST)
- ✅ Независимое развертывание
- ✅ Можно форкнуть Alkir-RAHC (уже есть Spring Boot 3 + IBIS)
- ✅ Четкое разделение ответственности

**Минусы:**
- ⚠️ Дополнительный network hop (latency +5-10ms)
- ⚠️ Нужно поддерживать 2 сервиса
- ⚠️ JVM требует ~100-500 MB памяти

**Вердикт:** ✅ **FALLBACK OPTION** - если ras-grpc-gw нестабилен

---

### Вариант C: Java Process Executor (stdin/stdout)

**Как работает:**
```
Go → exec.Command("java -jar bridge.jar") → stdin → Java → IBIS SDK → RAS
                                           ← stdout ←
```

**Плюсы:**
- ✅ Нет JNI сложности
- ✅ Изоляция процессов

**Минусы:**
- ❌ Overhead на создание процесса
- ❌ Сложность с сериализацией stdin/stdout
- ❌ Проблемы с кодировкой (аналогично RAC)
- ❌ Нет connection pooling

**Вердикт:** ⚠️ **НЕ ОПТИМАЛЬНО** - по сути тот же RAC, только через Java

---

### Вариант D: ras-grpc-gw (Pure Go + gRPC)

**Как работает:**
```
Go (ibis-service) → gRPC → ras-grpc-gw → RAS (native protocol)
```

**Проект:** https://github.com/v8platform/ras-grpc-gw

**Архитектура:**
```
┌─────────────────┐
│  ibis-service   │ Go + Gin (Port 8087)
│  (REST API)     │
└────────┬────────┘
         │ gRPC (protobuf)
┌────────▼────────┐
│  ras-grpc-gw    │ Go service (Port 9999)
│  (gRPC Gateway) │
└────────┬────────┘
         │ RAS native protocol
┌────────▼────────┐
│      RAS        │ Port 1545
└─────────────────┘
```

**Плюсы:**
- ✅ **Pure Go** - идеальная интеграция с monorepo
- ✅ **gRPC** - структурированные данные (protobuf)
- ✅ **Connection pooling** - встроено в gRPC
- ✅ **Высокая производительность** - native Go concurrency
- ✅ **Низкое потребление памяти** (~10-20 MB)
- ✅ **Быстрый старт** (<1 секунда)
- ✅ **Активный проект** - v8platform (известная команда)

**Минусы:**
- ⚠️ **ALPHA STATUS** - проект в активной разработке
- ⚠️ **Неизвестная стабильность** - требует тестирования
- ⚠️ **Документация** - может быть неполной

**Вердикт:** 🌟 **РЕКОМЕНДУЕТСЯ ПРОТЕСТИРОВАТЬ** - лучший вариант при условии стабильности

---

## 4. Выбранная стратегия

### Hybrid Approach (Постепенная миграция)

**Философия:** Не делаем big bang rewrite, а тестируем новые технологии параллельно

### Timeline по фазам

#### Phase 1-2: Week 1-6 (Continue with RAC CLI)
**Статус:** ✅ ТЕКУЩИЙ ПОДХОД

```
Orchestrator → installation-service (RAC) → RAS
```

**Действия:**
- Продолжаем использовать RAC CLI
- Фокус на других фичах (monitoring, operations)
- Даем время на созревание ras-grpc-gw

**Метрики:**
- Baseline performance: response time, throughput
- Проблемы: encoding issues, process overhead

---

#### Phase 2-3: Week 7-12 (Test ras-grpc-gw on STAGING)
**Статус:** 🧪 ТЕСТИРОВАНИЕ

**Параллельное развертывание:**
```
┌─→ installation-service (RAC) → RAS      [Production]
Orchestrator ─┤
└─→ ibis-service (gRPC) → ras-grpc-gw → RAS [Staging]
```

**Действия:**

1. **Week 7-8: Setup**
   - Развернуть ras-grpc-gw на staging сервере
   - Настроить gRPC connection pool
   - Имплементировать ibis-service с GRPCClient
   - Добавить feature flag для переключения

2. **Week 9-10: Testing**
   - Сравнительное тестирование RAC vs gRPC
   - Load testing: 100 → 500 баз
   - Мониторинг стабильности 24/7
   - Сбор метрик производительности

3. **Week 11-12: Analysis**
   - Анализ результатов
   - Проверка edge cases
   - Решение: GO or NO-GO

**Метрики успеха (GO criteria):**
- ✅ Uptime > 99.5% за 2 недели
- ✅ Error rate < 0.1%
- ✅ Response time < RAC baseline
- ✅ Memory stable (no leaks)
- ✅ Graceful handling of RAS restarts

**Если НЕ пройдено:**
- → Переход к Fallback (Java Bridge)

---

#### Phase 3+: Week 13+ (Choose Production Solution)

**Сценарий A: ras-grpc-gw стабилен ✅**

```
Orchestrator → ibis-service (gRPC) → ras-grpc-gw → RAS
```

**Действия:**
- Week 13: Миграция 10% production трафика
- Week 14: Миграция 50% production трафика
- Week 15: Миграция 100% production трафика
- Week 16: Удаление installation-service (RAC) из pipeline

**Метрики production:**
- 500 баз параллельно
- 1,000+ ops/min
- Uptime > 99.9%

---

**Сценарий B: ras-grpc-gw нестабилен ❌**

**Fallback план:**

```
Go (ibis-service) → HTTP → Java Bridge → IBIS SDK → RAS
```

**Действия:**
- Week 13-14: Форкнуть Alkir-RAHC
- Week 15: Добавить connection pooling
- Week 16: Развернуть Java Bridge на production
- Week 17: Интегрировать ibis-service с HTTPClient

**Преимущества fallback:**
- Проверенный IBIS SDK
- Spring Boot стабильность
- Alkir-RAHC как референс

**Недостатки:**
- Дополнительный JVM процесс
- Больше памяти и latency

---

## 5. Архитектура системы

### Высокоуровневая схема (Target State)

```
┌─────────────┐
│   React     │ Port 3000
│  Frontend   │
└──────┬──────┘
       │ HTTP
┌──────▼──────┐
│ Go API      │ Port 8080
│ Gateway     │
└──────┬──────┘
       │ HTTP
┌──────▼──────────┐
│ Django          │ Port 8000
│ Orchestrator    │
└────┬────────────┘
     │
     │ HTTP REST
┌────▼────────────┐
│  ibis-service   │ Port 8087 (Go + Gin)
│  (Go REST API)  │
└────┬────────────┘
     │
     │ Strategy Pattern (interface ClusterClient)
     ├─→ RACClient    (exec rac.exe)       [Phase 1-2]
     ├─→ GRPCClient   (→ ras-grpc-gw)      [Phase 2-3 Test]
     └─→ HTTPClient   (→ Java Bridge)      [Phase 3+ Fallback]
     │
┌────▼────────┐
│     RAS     │ Port 1545
└─────────────┘
```

### Layered Architecture (ibis-service)

```
┌─────────────────────────────────────────────────┐
│            REST API Layer (Gin)                 │
│  /api/v1/clusters, /infobases, /sessions       │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│           Service Layer                         │
│  ClusterService, InfobaseService, SessionService│
│  Business logic, validation, caching            │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│          Client Layer (Strategy)                │
│                                                  │
│   ┌────────────────────────────────────┐        │
│   │  interface ClusterClient           │        │
│   └───┬────────────┬──────────────┬────┘        │
│       │            │              │             │
│  ┌────▼────┐ ┌────▼─────┐ ┌──────▼─────┐       │
│  │RAC      │ │gRPC      │ │HTTP        │       │
│  │Client   │ │Client    │ │Client      │       │
│  └─────────┘ └──────────┘ └────────────┘       │
└─────────────────────────────────────────────────┘
```

---

## 6. Технологический стек

### Go Services

| Компонент | Технология | Версия | Назначение |
|-----------|-----------|--------|------------|
| HTTP Framework | Gin | v1.9+ | REST API |
| gRPC Client | google.golang.org/grpc | v1.60+ | ras-grpc-gw communication |
| Logging | go-services/shared/logger | - | Structured logging |
| Metrics | Prometheus client | v1.18+ | Observability |
| Config | Viper | v1.18+ | Configuration |
| Connection Pooling | gRPC built-in | - | 10-20 connections |

### External Services

| Сервис | Порт | Назначение |
|--------|------|------------|
| ibis-service | 8087 | REST API для Orchestrator |
| ras-grpc-gw | 9999 | gRPC Gateway к RAS (optional) |
| Java Bridge | 9090 | HTTP Wrapper для IBIS SDK (fallback) |
| RAS | 1545 | 1C Remote Administration Server |

### Protobuf Definitions (для gRPC)

```protobuf
// ras-grpc-gw предоставляет готовые protobuf
service ClusterService {
  rpc GetClusters(GetClustersRequest) returns (GetClustersResponse);
  rpc GetInfobases(GetInfobasesRequest) returns (GetInfobasesResponse);
  rpc GetSessions(GetSessionsRequest) returns (GetSessionsResponse);
}
```

---

## 7. Структура проекта

```
go-services/
├── ibis-service/
│   ├── cmd/
│   │   └── main.go                    # Entry point
│   ├── internal/
│   │   ├── api/
│   │   │   ├── handlers/
│   │   │   │   ├── cluster.go         # GET /clusters
│   │   │   │   ├── infobase.go        # GET /infobases
│   │   │   │   └── session.go         # GET /sessions
│   │   │   ├── middleware/
│   │   │   │   ├── auth.go            # JWT validation
│   │   │   │   ├── metrics.go         # Prometheus
│   │   │   │   └── logging.go         # Request logging
│   │   │   └── router.go              # Gin router setup
│   │   ├── service/
│   │   │   ├── cluster_service.go     # Business logic
│   │   │   ├── infobase_service.go
│   │   │   └── session_service.go
│   │   ├── client/
│   │   │   ├── interface.go           # ClusterClient interface
│   │   │   ├── rac_client.go          # RAC CLI implementation
│   │   │   ├── grpc_client.go         # gRPC implementation
│   │   │   ├── http_client.go         # HTTP Bridge implementation
│   │   │   └── factory.go             # Client factory
│   │   ├── models/
│   │   │   ├── cluster.go             # Domain models
│   │   │   ├── infobase.go
│   │   │   └── session.go
│   │   └── config/
│   │       └── config.go              # Configuration
│   ├── pkg/
│   │   └── proto/                     # Generated protobuf (if gRPC)
│   ├── go.mod
│   ├── go.sum
│   ├── Dockerfile
│   └── README.md
│
├── shared/                            # Shared code (already exists)
│   ├── auth/
│   ├── logger/
│   ├── metrics/
│   └── models/
│
└── installation-service/              # Legacy (RAC CLI)
    └── ...
```

---

## 8. API Спецификация

### Compatibility

**ВАЖНО:** API должен быть **полностью совместим** с installation-service для seamless миграции.

### Endpoints

#### GET /api/v1/clusters

**Request:**
```bash
GET /api/v1/clusters?server=localhost:1545
```

**Response:**
```json
{
  "clusters": [
    {
      "uuid": "e3b0c442-98fc-1c14-b39f-92d1282048c0",
      "name": "Local cluster",
      "host": "localhost",
      "port": 1541,
      "lifetime_limit": 0,
      "security_level": 0,
      "session_fault_tolerance_level": 0
    }
  ]
}
```

---

#### GET /api/v1/infobases

**Request:**
```bash
GET /api/v1/infobases?server=localhost:1545&detailed=true
```

**Response:**
```json
{
  "infobases": [
    {
      "uuid": "e94fc632-f38d-4866-8c39-3e98a6341c88",
      "name": "dev",
      "description": "",
      "dbms": "MSSQLServer",
      "db_server": "localhost",
      "db_name": "dev_db",
      "db_user": "sa",
      "security_level": 0,
      "date_offset": 0,
      "locale": "ru_RU",
      "connection_string": "",
      "scheduled_jobs_denied": false,
      "sessions_denied": false,
      "cluster_id": "e3b0c442-98fc-1c14-b39f-92d1282048c0"
    }
  ]
}
```

---

#### GET /api/v1/sessions

**Request:**
```bash
GET /api/v1/sessions?server=localhost:1545&cluster=e3b0c442-98fc-1c14-b39f-92d1282048c0
```

**Response:**
```json
{
  "sessions": [
    {
      "session_id": 12345,
      "infobase_id": "e94fc632-f38d-4866-8c39-3e98a6341c88",
      "user_name": "Admin",
      "app_id": "1CV8C",
      "started_at": "2025-10-28T10:00:00Z",
      "last_active_at": "2025-10-28T10:30:00Z",
      "host": "192.168.1.100"
    }
  ]
}
```

---

#### GET /health

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "client_type": "grpc",
  "ras_available": true,
  "uptime_seconds": 3600
}
```

---

## 9. Ключевые компоненты

### 9.1 ClusterClient Interface (Strategy Pattern)

```go
package client

import (
    "context"
    "ibis-service/internal/models"
)

// ClusterClient defines interface for RAS communication
// Implementations: RACClient, GRPCClient, HTTPClient
type ClusterClient interface {
    // GetClusters retrieves list of clusters from RAS
    GetClusters(ctx context.Context, server string) ([]models.Cluster, error)

    // GetInfobases retrieves list of infobases for cluster
    GetInfobases(ctx context.Context, server string, clusterID string) ([]models.Infobase, error)

    // GetSessions retrieves active sessions for cluster
    GetSessions(ctx context.Context, server string, clusterID string) ([]models.Session, error)

    // Ping checks if RAS is available
    Ping(ctx context.Context, server string) error

    // Close closes connection pool
    Close() error
}
```

---

### 9.2 RACClient (Phase 1-2)

```go
package client

import (
    "context"
    "os/exec"
    "ibis-service/internal/models"
)

type RACClient struct {
    racPath string // Path to rac.exe
}

func NewRACClient(racPath string) *RACClient {
    return &RACClient{racPath: racPath}
}

func (c *RACClient) GetClusters(ctx context.Context, server string) ([]models.Cluster, error) {
    cmd := exec.CommandContext(ctx, c.racPath, server, "cluster", "list")
    output, err := cmd.Output()
    if err != nil {
        return nil, err
    }

    // Parse text output (legacy approach)
    return parseRACClusterOutput(output)
}

// ... other methods
```

---

### 9.3 GRPCClient (Phase 2-3)

```go
package client

import (
    "context"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
    pb "ibis-service/pkg/proto" // Generated from ras-grpc-gw
)

type GRPCClient struct {
    conn   *grpc.ClientConn
    client pb.ClusterServiceClient
}

func NewGRPCClient(gatewayAddr string) (*GRPCClient, error) {
    // Connection pooling built into gRPC
    conn, err := grpc.Dial(
        gatewayAddr,
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithDefaultServiceConfig(`{"loadBalancingPolicy":"round_robin"}`),
    )
    if err != nil {
        return nil, err
    }

    client := pb.NewClusterServiceClient(conn)
    return &GRPCClient{conn: conn, client: client}, nil
}

func (c *GRPCClient) GetClusters(ctx context.Context, server string) ([]models.Cluster, error) {
    req := &pb.GetClustersRequest{Server: server}
    resp, err := c.client.GetClusters(ctx, req)
    if err != nil {
        return nil, err
    }

    // Convert protobuf to domain models
    return convertProtoClusters(resp.Clusters), nil
}

func (c *GRPCClient) Close() error {
    return c.conn.Close()
}
```

**Connection Pooling:**
```go
// gRPC automatically manages connection pool
// Config:
grpc.WithDefaultServiceConfig(`{
  "loadBalancingPolicy": "round_robin",
  "methodConfig": [{
    "name": [{"service": "ClusterService"}],
    "retryPolicy": {
      "maxAttempts": 3,
      "initialBackoff": "0.1s",
      "maxBackoff": "1s",
      "backoffMultiplier": 2
    }
  }]
}`)
```

---

### 9.4 HTTPClient (Fallback)

```go
package client

import (
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

type HTTPClient struct {
    baseURL    string
    httpClient *http.Client
}

func NewHTTPClient(baseURL string) *HTTPClient {
    return &HTTPClient{
        baseURL: baseURL,
        httpClient: &http.Client{
            Timeout: 30 * time.Second,
            Transport: &http.Transport{
                MaxIdleConns:        100,
                MaxIdleConnsPerHost: 10, // Connection pooling
                IdleConnTimeout:     90 * time.Second,
            },
        },
    }
}

func (c *HTTPClient) GetClusters(ctx context.Context, server string) ([]models.Cluster, error) {
    url := fmt.Sprintf("%s/api/v1/clusters?server=%s", c.baseURL, server)

    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        return nil, err
    }

    resp, err := c.httpClient.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var result struct {
        Clusters []models.Cluster `json:"clusters"`
    }

    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, err
    }

    return result.Clusters, nil
}
```

---

### 9.5 Client Factory (Выбор клиента)

```go
package client

import (
    "fmt"
    "os"
)

type ClientType string

const (
    ClientTypeRAC  ClientType = "rac"
    ClientTypeGRPC ClientType = "grpc"
    ClientTypeHTTP ClientType = "http"
)

func NewClusterClient(clientType ClientType) (ClusterClient, error) {
    switch clientType {
    case ClientTypeRAC:
        racPath := os.Getenv("RAC_PATH")
        if racPath == "" {
            racPath = "/c/Program Files/1cv8/8.3.27.1786/bin/rac.exe"
        }
        return NewRACClient(racPath), nil

    case ClientTypeGRPC:
        gatewayAddr := os.Getenv("GRPC_GATEWAY_ADDR")
        if gatewayAddr == "" {
            gatewayAddr = "localhost:9999"
        }
        return NewGRPCClient(gatewayAddr)

    case ClientTypeHTTP:
        baseURL := os.Getenv("JAVA_BRIDGE_URL")
        if baseURL == "" {
            baseURL = "http://localhost:9090"
        }
        return NewHTTPClient(baseURL), nil

    default:
        return nil, fmt.Errorf("unknown client type: %s", clientType)
    }
}
```

**Использование:**
```go
// In main.go or config
clientType := os.Getenv("CLUSTER_CLIENT_TYPE") // "rac", "grpc", "http"
if clientType == "" {
    clientType = "rac" // Default
}

client, err := client.NewClusterClient(client.ClientType(clientType))
if err != nil {
    log.Fatal(err)
}
defer client.Close()
```

---

### 9.6 Service Layer

```go
package service

import (
    "context"
    "ibis-service/internal/client"
    "ibis-service/internal/models"
    "time"
)

type ClusterService struct {
    client client.ClusterClient
    cache  *Cache // Redis cache (optional)
}

func NewClusterService(client client.ClusterClient) *ClusterService {
    return &ClusterService{client: client}
}

func (s *ClusterService) GetClusters(ctx context.Context, server string) ([]models.Cluster, error) {
    // Check cache first
    if s.cache != nil {
        if clusters, found := s.cache.Get("clusters:" + server); found {
            return clusters.([]models.Cluster), nil
        }
    }

    // Fetch from RAS
    clusters, err := s.client.GetClusters(ctx, server)
    if err != nil {
        return nil, err
    }

    // Cache for 5 minutes
    if s.cache != nil {
        s.cache.Set("clusters:"+server, clusters, 5*time.Minute)
    }

    return clusters, nil
}
```

---

### 9.7 API Handlers

```go
package handlers

import (
    "net/http"
    "github.com/gin-gonic/gin"
    "ibis-service/internal/service"
)

type ClusterHandler struct {
    service *service.ClusterService
}

func NewClusterHandler(service *service.ClusterService) *ClusterHandler {
    return &ClusterHandler{service: service}
}

func (h *ClusterHandler) GetClusters(c *gin.Context) {
    server := c.Query("server")
    if server == "" {
        c.JSON(http.StatusBadRequest, gin.H{"error": "server parameter required"})
        return
    }

    clusters, err := h.service.GetClusters(c.Request.Context(), server)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }

    c.JSON(http.StatusOK, gin.H{"clusters": clusters})
}
```

---

## 10. План реализации

### Phase 1-2: Week 1-6 (Status Quo)

**Цель:** Continue with RAC, prepare infrastructure

**Week 1-2:**
- [ ] Setup go-services/ibis-service/ структура
- [ ] Имплементировать RACClient (перенести из installation-service)
- [ ] Создать REST API handlers (Gin)
- [ ] Добавить health check endpoint
- [ ] Unit tests для RACClient

**Week 3-4:**
- [ ] Интегрировать с Orchestrator (ClusterService)
- [ ] Feature flag для переключения installation-service ↔ ibis-service
- [ ] E2E тесты с реальным RAS
- [ ] Базовый мониторинг (Prometheus)

**Week 5-6:**
- [ ] Производственное развертывание с RACClient
- [ ] Сбор baseline метрик
- [ ] Документация API

**Deliverables:**
- ✅ ibis-service работает в production с RAC
- ✅ Полная совместимость с installation-service
- ✅ Baseline метрики собраны

---

### Phase 2-3: Week 7-12 (Test ras-grpc-gw)

**Цель:** Test gRPC alternative on staging

**Week 7-8: Setup**
- [ ] Изучить ras-grpc-gw documentation
- [ ] Развернуть ras-grpc-gw на staging сервере
- [ ] Сгенерировать Go protobuf клиент
- [ ] Имплементировать GRPCClient
- [ ] Unit tests для GRPCClient

**Week 9-10: Testing**
- [ ] Сравнительное тестирование RAC vs gRPC
  - Response time
  - Throughput (ops/min)
  - Error rate
  - Memory consumption
- [ ] Load testing: 10 → 50 → 100 → 500 баз
- [ ] Stress testing: restart RAS, network issues
- [ ] 24/7 stability monitoring

**Week 11-12: Analysis & Decision**
- [ ] Analyze test results
- [ ] Edge cases проверка
- [ ] Performance tuning если нужно
- [ ] **GO/NO-GO DECISION**

**Success Criteria (GO):**
- Uptime > 99.5% за 2 недели
- Error rate < 0.1%
- Response time < RAC baseline
- No memory leaks
- Graceful error handling

**Deliverables:**
- ✅ GRPCClient имплементирован
- ✅ Comprehensive test report
- ✅ GO/NO-GO decision made

---

### Phase 3+: Week 13+ (Production Migration)

#### Сценарий A: ras-grpc-gw SUCCESS ✅

**Week 13: Canary Deployment**
- [ ] Deploy ibis-service с GRPCClient на production
- [ ] Route 10% трафика через gRPC (feature flag)
- [ ] Monitor closely: errors, latency, uptime

**Week 14: Gradual Rollout**
- [ ] Increase to 50% трафика
- [ ] Continue monitoring

**Week 15: Full Migration**
- [ ] Route 100% трафика через gRPC
- [ ] Mark RACClient as deprecated

**Week 16: Cleanup**
- [ ] Remove installation-service from active use
- [ ] Archive legacy RAC code
- [ ] Update documentation

---

#### Сценарий B: ras-grpc-gw UNSTABLE ❌

**Week 13-14: Java Bridge Development**
- [ ] Fork Alkir-RAHC repository
- [ ] Simplify codebase (remove unnecessary features)
- [ ] Add connection pooling (Apache Commons Pool)
- [ ] Create Dockerfile

**Week 15: Integration**
- [ ] Deploy Java Bridge на staging
- [ ] Имплементировать HTTPClient в ibis-service
- [ ] E2E тесты

**Week 16-17: Production Deployment**
- [ ] Deploy Java Bridge на production
- [ ] Route 10% → 50% → 100% трафика
- [ ] Monitor JVM metrics

**Deliverables (Fallback):**
- ✅ Java Bridge service работает
- ✅ ibis-service с HTTPClient
- ✅ Connection pooling для 700+ баз

---

## 11. Риски и митигация

### Риск 1: ras-grpc-gw нестабилен (HIGH)

**Вероятность:** Medium (ALPHA проект)
**Влияние:** High (задержка на 2-3 недели)

**Митигация:**
- ✅ Fallback план готов (Java Bridge)
- ✅ Тестирование на staging перед production
- ✅ Feature flag для быстрого rollback

---

### Риск 2: Java Bridge добавляет latency (MEDIUM)

**Вероятность:** High (network hop неизбежен)
**Влияние:** Medium (+5-10ms на запрос)

**Митигация:**
- Deploy Java Bridge на том же сервере (localhost)
- HTTP/2 для снижения latency
- Connection pooling для снижения overhead

---

### Риск 3: RAS protocol изменился (LOW)

**Вероятность:** Low (стабильный протокол)
**Влияние:** High (требует обновления всех клиентов)

**Митигация:**
- Monitor 1C release notes
- Поддерживаем несколько версий клиентов
- RACClient как fallback всегда работает

---

### Риск 4: Connection pool exhaustion (MEDIUM)

**Вероятность:** Medium (700+ баз)
**Влияние:** High (requests timeout)

**Митигация:**
- Monitor connection pool metrics
- Auto-scaling на основе queue depth
- Circuit breaker для graceful degradation

---

## 12. Метрики успеха

### Performance Metrics

| Метрика | Baseline (RAC) | Target (gRPC/HTTP) | Measurement |
|---------|----------------|-------------------|-------------|
| Response time (p50) | 200ms | <150ms | Prometheus histogram |
| Response time (p99) | 500ms | <300ms | Prometheus histogram |
| Throughput | 100 ops/min | 1,000+ ops/min | Prometheus counter |
| Error rate | 1-2% | <0.1% | Prometheus counter |
| Memory usage | 50 MB | <100 MB | cAdvisor |

### Reliability Metrics

| Метрика | Target | Measurement |
|---------|--------|-------------|
| Uptime | >99.9% | Prometheus |
| Connection pool saturation | <80% | Custom metric |
| RAS ping success rate | >99.5% | Health check |

### Business Metrics

| Метрика | Phase 1-2 | Phase 3+ | Target |
|---------|-----------|----------|--------|
| Concurrent bases | 50 | 200-500 | 700+ |
| Operations per minute | 100 | 1,000+ | 5,000+ |
| Average operation time | 30s | 10s | 5s |

---

## 13. Полезные ссылки

### Проекты для изучения

- **ras-grpc-gw:** https://github.com/v8platform/ras-grpc-gw
- **Alkir-RAHC:** https://github.com/AlexeyOgurtsov/RAHC (Spring Boot 3 + IBIS)
- **1C IBIS SDK:** `com._1c.v8.ibis.admin-1.6.7/` в проекте

### Документация

- **1C RAS vs RAC:** `docs/1C_RAS_vs_RAC.md`
- **1C RAC Commands:** `docs/1C_RAC_COMMANDS.md`
- **RAS API Options:** `docs/1C_RAS_API_OPTIONS.md`
- **Java Architecture (legacy):** `docs/IBIS_SERVICE_ARCHITECTURE.md`

### Internal Resources

- **Orchestrator:** `orchestrator/apps/databases/services.py`
- **installation-service:** `go-services/installation-service/`
- **Roadmap:** `docs/ROADMAP.md` (Balanced Approach)

---

## 14. Changelog

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2025-10-28 | 1.0 | Initial Go architecture - hybrid strategy |

---

**Статус:** ✅ Утвержден для реализации (Go вариант выбран)
**Следующий шаг:** Начать Phase 1-2 (Setup ibis-service с RACClient)
**Ответственный:** Development Team
**Deadline Phase 1-2:** Week 1-6
