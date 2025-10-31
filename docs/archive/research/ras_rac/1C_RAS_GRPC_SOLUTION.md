# ras-grpc-gw: gRPC Gateway для RAS 1С ⭐

## 🎯 Что это?

**ras-grpc-gw** - это Open Source Go-проект, который предоставляет **gRPC API** для работы с RAS 1С:Предприятие напрямую, **БЕЗ использования rac.exe**.

**Репозиторий:** https://github.com/v8platform/ras-grpc-gw
**Лицензия:** MIT
**Язык:** Go (96.9%)
**Статус:** ⚠️ ALPHA (не рекомендуется для production)

---

## ✅ Преимущества для CommandCenter1C

### 1. Написан на Go
- Легко интегрируется с нашим Go Installation Service
- Можно использовать как библиотеку или как отдельный сервис
- Нативная типизация (protocol buffers)

### 2. gRPC API
- Структурированные данные (без парсинга текста)
- Высокая производительность
- Поддержка streaming
- Автогенерация клиентов

### 3. Прямое взаимодействие с RAS
- НЕ требует rac.exe
- НЕ требует лицензии 1C
- НЕ требует Java
- Нет проблем с кодировкой Windows-1251

### 4. Open Source + MIT
- Можно изучить код
- Можно модифицировать под свои нужды
- Активная разработка (последний релиз 2021)

---

## 📋 Реализованный функционал

### AuthService - Авторизация
```protobuf
- AuthenticateCluster    // Авторизация администратора кластера
- AuthenticateInfobase   // Авторизация на информационной базе
- AuthenticateAgent      // Авторизация администратора на агенте
```

### ClustersService - Управление кластерами
```protobuf
- GetClusters            // ✅ Получение списка кластеров
- GetClusterInfo         // Получение информации о кластере
- RegCluster             // Регистрация нового кластера
- UnregCluster           // Отмена регистрации кластера
```

### InfobasesService - Информационные базы
```protobuf
- GetShortInfobases      // ✅ Получение списка информационных баз
- GetInfobaseSessions    // Получение списка сессий базы
```

### SessionsService - Сессии кластера
```protobuf
- GetSessions            // Получение списка сессий кластера
```

---

## 🚀 Как использовать

### Вариант 1: Docker контейнер (Рекомендуется)

```bash
# Запустить gRPC прокси рядом с RAS
docker run -d --name ras-grpc-gw \
  -p 3002:3002 \
  v8platform/ras-grpc-gw:latest \
  1cserver:1545
```

**Архитектура:**
```
┌─────────────────┐
│ Go Installation │
│    Service      │
└────────┬────────┘
         │ gRPC (3002)
┌────────▼────────┐
│  ras-grpc-gw    │ ← Docker контейнер
│   (Go proxy)    │
└────────┬────────┘
         │ RAS protocol (1545)
┌────────▼────────┐
│   RAS Server    │ ← Служба 1С
└─────────────────┘
```

### Вариант 2: Использовать как Go библиотеку

```go
package main

import (
    "context"
    "log"

    "google.golang.org/grpc"
    "google.golang.org/grpc/metadata"
    clustersv1 "github.com/v8platform/protos/gen/ras/service/api/v1"
    infobasesv1 "github.com/v8platform/protos/gen/ras/service/api/v1"
)

func main() {
    // Подключение к gRPC серверу
    conn, err := grpc.Dial("localhost:3002", grpc.WithInsecure())
    if err != nil {
        log.Fatalf("Failed to connect: %v", err)
    }
    defer conn.Close()

    // Создать клиент для работы с кластерами
    clustersClient := clustersv1.NewClustersServiceClient(conn)

    // Создать контекст с endpoint_id
    ctx := metadata.AppendToOutgoingContext(context.Background(), "endpoint_id", "1")

    // Получить список кластеров
    clustersResp, err := clustersClient.GetClusters(ctx, &clustersv1.GetClustersRequest{})
    if err != nil {
        log.Fatalf("Failed to get clusters: %v", err)
    }

    log.Printf("Found %d clusters", len(clustersResp.Clusters))

    for _, cluster := range clustersResp.Clusters {
        log.Printf("Cluster: %s (ID: %s)", cluster.Name, cluster.Id)

        // Создать клиент для работы с базами
        infobasesClient := infobasesv1.NewInfobasesServiceClient(conn)

        // Получить список информационных баз кластера
        infobasesResp, err := infobasesClient.GetShortInfobases(ctx,
            &infobasesv1.GetShortInfobasesRequest{
                ClusterId: cluster.Id,
            })

        if err != nil {
            log.Printf("Failed to get infobases: %v", err)
            continue
        }

        log.Printf("  Found %d infobases", len(infobasesResp.Infobases))

        for _, infobase := range infobasesResp.Infobases {
            log.Printf("    - %s (ID: %s)", infobase.Name, infobase.Id)
        }
    }
}
```

### Вариант 3: CLI с grpcurl

```bash
# Получить список кластеров
grpcurl -protoset ./protos/protoset.bin \
  -plaintext \
  -H endpoint_id:1 \
  -d '{}' \
  localhost:3002 \
  ras.service.api.v1.ClustersService/GetClusters

# Получить список информационных баз
grpcurl -protoset ./protos/protoset.bin \
  -plaintext \
  -H endpoint_id:1 \
  -d '{"cluster_id": "e9261ed1-c9d0-40e5-8222-c7996493d507"}' \
  localhost:3002 \
  ras.service.api.v1.InfobasesService/GetShortInfobases
```

---

## 📦 Интеграция с CommandCenter1C

### Архитектура решения

```
┌──────────────────────────────────────────────────────────┐
│                    Docker Compose                         │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────────┐      ┌──────────────────┐           │
│  │ Go Installation │ gRPC │   ras-grpc-gw    │           │
│  │    Service      │─────▶│   (Go proxy)     │           │
│  │  (Port 5555)    │ 3002 │   Docker         │           │
│  └─────────┬───────┘      └────────┬─────────┘           │
│            │                       │                      │
│            │ Redis                 │ RAS 1545             │
│            ▼                       ▼                      │
│  ┌─────────────────┐      ┌──────────────────┐           │
│  │     Redis       │      │  RAS Server 1С   │ (external)│
│  └─────────────────┘      └──────────────────┘           │
│                                                            │
└──────────────────────────────────────────────────────────┘
                    │
                    ▼
          ┌──────────────────┐
          │ Django           │
          │ Orchestrator     │
          └──────────────────┘
```

### Обновленный docker-compose.yml

```yaml
services:
  # Добавить новый сервис
  ras-grpc-gw:
    image: v8platform/ras-grpc-gw:latest
    container_name: commandcenter-ras-grpc
    ports:
      - "3002:3002"
    command: 1cserver:1545  # Адрес вашего RAS сервера
    networks:
      - commandcenter-network
    healthcheck:
      test: ["CMD", "grpc_health_probe", "-addr=:3002"]
      interval: 30s
      timeout: 5s
      retries: 3

  # Go Installation Service с зависимостью от ras-grpc-gw
  installation-service:
    build:
      context: ./installation-service
      dockerfile: Dockerfile
    container_name: commandcenter-installation-service
    environment:
      - RAS_GRPC_ADDRESS=ras-grpc-gw:3002
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
      - ras-grpc-gw
    networks:
      - commandcenter-network
```

### Go код для Installation Service

```go
// installation-service/internal/cluster/grpc_manager.go

package cluster

import (
    "context"
    "fmt"
    "log"

    "google.golang.org/grpc"
    "google.golang.org/grpc/metadata"
    clustersv1 "github.com/v8platform/protos/gen/ras/service/api/v1"
    infobasesv1 "github.com/v8platform/protos/gen/ras/service/api/v1"
)

type GRPCClusterManager struct {
    conn             *grpc.ClientConn
    clustersClient   clustersv1.ClustersServiceClient
    infobasesClient  infobasesv1.InfobasesServiceClient
    endpointID       string
}

func NewGRPCClusterManager(address string) (*GRPCClusterManager, error) {
    conn, err := grpc.Dial(address, grpc.WithInsecure())
    if err != nil {
        return nil, fmt.Errorf("failed to connect to ras-grpc-gw: %w", err)
    }

    return &GRPCClusterManager{
        conn:            conn,
        clustersClient:  clustersv1.NewClustersServiceClient(conn),
        infobasesClient: infobasesv1.NewInfobasesServiceClient(conn),
        endpointID:      "1", // Можно генерировать уникальный
    }, nil
}

func (m *GRPCClusterManager) Close() error {
    return m.conn.Close()
}

func (m *GRPCClusterManager) ctx() context.Context {
    return metadata.AppendToOutgoingContext(
        context.Background(),
        "endpoint_id", m.endpointID,
    )
}

// GetInfobaseList получает список всех информационных баз
func (m *GRPCClusterManager) GetInfobaseList() ([]InfobaseInfo, error) {
    // Шаг 1: Получить список кластеров
    clustersResp, err := m.clustersClient.GetClusters(m.ctx(),
        &clustersv1.GetClustersRequest{})
    if err != nil {
        return nil, fmt.Errorf("failed to get clusters: %w", err)
    }

    var allInfobases []InfobaseInfo

    // Шаг 2: Для каждого кластера получить базы
    for _, cluster := range clustersResp.Clusters {
        infobasesResp, err := m.infobasesClient.GetShortInfobases(m.ctx(),
            &infobasesv1.GetShortInfobasesRequest{
                ClusterId: cluster.Id,
            })

        if err != nil {
            log.Printf("Warning: failed to get infobases for cluster %s: %v",
                cluster.Id, err)
            continue
        }

        // Шаг 3: Преобразовать в наш формат
        for _, ib := range infobasesResp.Infobases {
            allInfobases = append(allInfobases, InfobaseInfo{
                UUID:        ib.Id,
                Name:        ib.Name,
                Description: ib.Descr,
                ClusterID:   cluster.Id,
            })
        }
    }

    return allInfobases, nil
}

type InfobaseInfo struct {
    UUID        string
    Name        string
    Description string
    ClusterID   string
}
```

### Использование в главном коде

```go
// installation-service/cmd/main.go

func main() {
    // Инициализация gRPC менеджера кластера
    clusterManager, err := cluster.NewGRPCClusterManager("ras-grpc-gw:3002")
    if err != nil {
        log.Fatalf("Failed to create cluster manager: %v", err)
    }
    defer clusterManager.Close()

    // Получить список всех баз
    infobases, err := clusterManager.GetInfobaseList()
    if err != nil {
        log.Fatalf("Failed to get infobase list: %v", err)
    }

    log.Printf("Found %d infobases in total", len(infobases))

    // Отправить список в Redis для Django
    for _, ib := range infobases {
        log.Printf("- %s (UUID: %s)", ib.Name, ib.UUID)
        // TODO: Отправить в Redis
    }
}
```

---

## ⚠️ Важные замечания

### 1. ALPHA версия

Проект в статусе ALPHA:
- **НЕ рекомендуется** для промышленной эксплуатации
- Возможны ошибки и нестабильная работа
- API может измениться

**Рекомендация:** Сначала протестировать на dev/staging окружении

### 2. Endpoint Management

`endpoint_id` - это уникальный идентификатор сессии работы с RAS:
- Нужно передавать в метаданных каждого gRPC запроса
- Одна сессия = один endpoint
- При переподключении endpoints сбрасываются

### 3. Ограниченный функционал

Пока реализованы только базовые операции:
- ❌ Нет методов для управления сеансами (terminate)
- ❌ Нет методов для управления блокировками
- ❌ Нет методов для настройки кластера
- ✅ Есть получение списка баз (нам этого достаточно)

### 4. Зависимости

Требуется:
- Go 1.17+
- gRPC библиотеки
- Protocol Buffers компилятор (для разработки)

---

## 📊 Сравнение с другими подходами

| Критерий | rac.exe | Java API | ras-grpc-gw |
|----------|---------|----------|-------------|
| **Язык** | CLI | Java | Go |
| **Лицензия** | ✅ Не нужна | ❌ Требуется | ✅ Не нужна (MIT) |
| **Сложность** | ⭐ Низкая | ⭐⭐⭐ Высокая | ⭐⭐ Средняя |
| **Парсинг** | ❌ Текст | ✅ Объекты | ✅ Protobuf |
| **Производительность** | ⭐⭐ Средняя | ⭐⭐⭐ Высокая | ⭐⭐⭐ Высокая |
| **Надёжность** | ⭐⭐ Средняя | ⭐⭐⭐ Высокая | ⭐⭐ ALPHA |
| **Интеграция с Go** | ❌ exec.Command | ❌ JNI | ✅ Нативная |
| **Open Source** | ❌ Нет | ❌ Проприетарный | ✅ MIT |
| **Production ready** | ✅ Да | ✅ Да | ⚠️ ALPHA |

---

## 🎯 Рекомендация для CommandCenter1C

### Phase 1-2 (Текущая): rac.exe ✅
Причины:
- Стабильная реализация
- Быстро запустить
- Низкий риск

### Phase 2.5 (Testing): ras-grpc-gw на staging 🧪
Причины:
- Протестировать стабильность
- Оценить производительность
- Выявить баги

### Phase 3 (Production): Миграция на ras-grpc-gw 🚀
Условия:
- Успешные тесты на staging
- Проект стабилизировался (Beta/RC)
- Нет критичных багов

**Преимущества миграции:**
- Чистый Go код (без exec)
- Лучшая производительность
- Структурированные данные
- Легче тестировать

---

## 📚 Полезные ссылки

### Проект ras-grpc-gw
- **GitHub:** https://github.com/v8platform/ras-grpc-gw
- **Releases:** https://github.com/v8platform/ras-grpc-gw/releases
- **Docker Hub:** https://hub.docker.com/r/v8platform/ras-grpc-gw

### Proto definitions
- **GitHub:** https://github.com/v8platform/protos
- Содержит все .proto файлы для gRPC

### v8platform организация
- **GitHub:** https://github.com/v8platform
- Много полезных Go библиотек для работы с 1С

---

## ✅ TODO: Следующие шаги

1. **Протестировать локально** (1 день)
   - Запустить ras-grpc-gw в Docker
   - Проверить работу GetShortInfobases
   - Оценить стабильность

2. **Создать Go модуль** (2-3 дня)
   - Реализовать GRPCClusterManager
   - Добавить обработку ошибок
   - Написать unit тесты

3. **Интегрировать с Installation Service** (1 неделя)
   - Добавить в docker-compose
   - Протестировать на dev окружении
   - Сравнить с rac.exe подходом

4. **Production decision** (после Phase 2)
   - Если стабильно → использовать ras-grpc-gw
   - Если нестабильно → остаться на rac.exe

---

**Версия:** 1.0
**Дата:** 2025-10-27
**Автор:** CommandCenter1C Team
**Статус:** Рекомендуется для тестирования
