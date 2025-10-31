# Руководство по администрированию 1С через RAS/RAC

**Статус:** Актуально для CommandCenter1C
**Версия:** 1.0
**Дата:** 2025-10-31

Практический гайд по работе с 1С:Enterprise через RAS (Remote Administration Server) и RAC (Remote Administration Console).

---

## 🎯 Выбранное решение: gRPC через ras-grpc-gw

CommandCenter1C использует **gRPC подход** через форк [ras-grpc-gw](https://github.com/defin85/ras-grpc-gw):

```
cluster-service (Go) → gRPC → ras-grpc-gw → RAS (1C Server) → Кластеры 1С
```

**Преимущества:**
- ✅ Типизированные protobuf контракты
- ✅ Автоматическая генерация Go/Python клиентов
- ✅ Streaming поддержка для real-time данных
- ✅ Надёжная сетевая коммуникация

**Альтернативы (НЕ используются):**
- ❌ RAC CLI (text parsing, нестабильный вывод)
- ❌ COM/ole automation (только Windows, проблемы в контейнерах)

---

## 🏗️ Архитектура RAS

### RAS (Remote Administration Server)

**Что это:** TCP сервер для удалённого управления кластерами 1С.

**Порт по умолчанию:** 1545

**Запуск:**
```bash
# Windows
"C:\Program Files\1cv8\8.3.27.1786\bin\ras.exe" cluster --port=1545

# Linux
/opt/1cv8/x86_64/8.3.27.1786/ras cluster --port=1545
```

**Протокол:** Бинарный протокол 1С (не документированный официально)

### RAC (Remote Administration Console)

**Что это:** CLI утилита для работы с RAS.

**Использование (reference only):**
```bash
# Список кластеров
rac cluster list localhost:1545

# Информация о кластере
rac cluster info --cluster=<cluster-id> localhost:1545

# Список информационных баз
rac infobase summary list --cluster=<cluster-id> localhost:1545
```

⚠️ **Важно:** В CommandCenter1C RAC CLI НЕ используется напрямую. Все операции идут через gRPC.

---

## 🔐 Аутентификация и безопасность

### Уровни аутентификации

1. **Кластер (cluster)** - доступ к управлению кластером
2. **Информационная база (infobase)** - доступ к конкретной базе данных
3. **Агент (agent)** - доступ к RAS серверу (опционально)

### Процесс аутентификации в cluster-service

```go
// 1. Аутентификация на кластере
req := &messagesv1.ClusterAuthenticateRequest{
    Cluster: &messagesv1.ClusterInfo{
        ClusterId: clusterId,
    },
    User:     "admin",
    Password: "password",
}
_, err := rasClient.AuthenticateCluster(ctx, req)

// 2. Получение данных (с сохранённым endpoint)
infobases, err := rasClient.GetShortInfobases(ctx, &messagesv1.GetInfobasesShortRequest{
    Cluster: &messagesv1.ClusterInfo{
        ClusterId: clusterId,
    },
})
```

**Критично:** Endpoint ID должен сохраняться между запросами (см. `EndpointInterceptor`).

### Ограничения безопасности RAC CLI

> **Reference:** docs/archive/research/ras_rac/1C_RAC_SECURITY.md

RAC CLI имеет серьёзные ограничения:
- ❌ Пароли передаются в plaintext в параметрах команды
- ❌ Видны в `ps aux` и логах shell
- ❌ Нет встроенного шифрования

**Решение в CommandCenter1C:** gRPC с TLS (Phase 3).

---

## 📡 ras-grpc-gw: Наш gRPC Gateway

### Форк проекта

**Upstream:** https://github.com/khorevaa/ras-client
**Наш форк:** https://github.com/defin85/ras-grpc-gw

**Зачем форк:**
- Исправление endpoint management (Sprint 1.4)
- Возврат endpoint_id в response headers
- Поддержка для cluster-service

### Запуск ras-grpc-gw

```bash
# Скачать релиз
wget https://github.com/defin85/ras-grpc-gw/releases/download/v0.1.0/ras-grpc-gw.exe

# Запустить
./ras-grpc-gw.exe --bind 0.0.0.0:9999 localhost:1545

# С health check endpoint
./ras-grpc-gw.exe --bind 0.0.0.0:9999 --health 0.0.0.0:8081 localhost:1545
```

**Health Check:**
```bash
curl http://localhost:8081/health
# {"status":"ok"}
```

### Конфигурация в cluster-service

```yaml
# configs/config.yaml
ras_grpc:
  address: "localhost:9999"
  timeout: 30s
  max_retry: 3
```

---

## 🔑 Основные операции

### Получение списка кластеров

```go
resp, err := rasClient.GetClusters(ctx, &messagesv1.GetClustersRequest{})
for _, cluster := range resp.Clusters {
    fmt.Printf("Cluster: %s\n", cluster.ClusterId)
}
```

### Получение информации о кластере

```go
resp, err := rasClient.GetClusterInfo(ctx, &messagesv1.GetClusterInfoRequest{
    Cluster: &messagesv1.ClusterInfo{
        ClusterId: clusterId,
    },
})
```

### Получение списка баз данных

```go
// После AuthenticateCluster
resp, err := rasClient.GetShortInfobases(ctx, &messagesv1.GetInfobasesShortRequest{
    Cluster: &messagesv1.ClusterInfo{
        ClusterId: clusterId,
    },
})
```

### Получение сессий базы данных

```go
resp, err := rasClient.GetInfobaseSessions(ctx, &messagesv1.GetInfobaseSessionsRequest{
    Cluster: &messagesv1.ClusterInfo{
        ClusterId: clusterId,
    },
    Infobase: &messagesv1.InfobaseInfo{
        InfobaseId: infobaseId,
    },
})
```

---

## ⚙️ Endpoint Management (Критично!)

### Проблема

RAS создаёт новый **endpoint** для каждого TCP соединения. Аутентификация привязана к endpoint.

**Без сохранения endpoint ID:**
```
AuthenticateCluster → endpoint "1" (authenticated ✅)
GetShortInfobases   → endpoint "2" (NOT authenticated ❌)
```

### Решение: EndpointInterceptor

```go
// internal/grpc/interceptors/endpoint.go
type EndpointInterceptor struct {
    mu         sync.RWMutex
    endpointID string
}

func (i *EndpointInterceptor) Intercept(
    ctx context.Context,
    method string,
    req, reply interface{},
    cc *grpc.ClientConn,
    invoker grpc.UnaryInvoker,
    opts ...grpc.CallOption,
) error {
    // Отправить endpoint_id если есть
    if i.endpointID != "" {
        ctx = metadata.AppendToOutgoingContext(ctx, "endpoint_id", i.endpointID)
    }

    // Вызвать метод
    err := invoker(ctx, method, req, reply, cc, opts...)

    // Получить endpoint_id из response headers
    if md, ok := metadata.FromIncomingContext(ctx); ok {
        if ids := md.Get("endpoint_id"); len(ids) > 0 {
            i.mu.Lock()
            i.endpointID = ids[0]
            i.mu.Unlock()
        }
    }

    return err
}
```

**См. подробнее:** `docs/ENDPOINT_MANAGEMENT_ARCHITECTURE.md`

---

## 📊 Производительность

**Текущие метрики (Sprint 1.4):**
- Первый вызов GetInfobases: **47.24ms**
- Последующие вызовы: **15.28ms** (3x speedup)
- Endpoint переиспользование: ✅ Работает

---

## 🔍 Troubleshooting

### "Недостаточно прав пользователя"

**Причина:** Endpoint не переиспользуется после аутентификации.

**Решение:**
1. Проверить что `EndpointInterceptor` настроен
2. Проверить логи: `endpoint_id` должен быть одинаковый
3. Убедиться что ras-grpc-gw возвращает `endpoint_id` в headers

### RAS не отвечает

```bash
# Проверить что RAS запущен
netstat -an | grep 1545

# Перезапустить RAS
killall ras && ras cluster --port=1545 &

# Проверить логи RAS
tail -f /var/log/1c/ras.log
```

### ras-grpc-gw недоступен

```bash
# Health check
curl http://localhost:8081/health

# Логи ras-grpc-gw
tail -f /tmp/ras-grpc-gw.log

# Перезапустить
./ras-grpc-gw.exe --bind 0.0.0.0:9999 localhost:1545 > /tmp/ras-grpc-gw.log 2>&1 &
```

---

## 📚 Справочная информация

### Детальная документация (архив)

Для глубокого погружения см. `docs/archive/research/ras_rac/`:
- `1C_RAS_vs_RAC.md` - сравнение подходов
- `1C_RAC_COMMANDS.md` - полный список команд RAC
- `1C_RAS_GRPC_SOLUTION.md` - детали gRPC решения
- `1C_RAC_SECURITY.md` - ограничения безопасности

### Полезные ссылки

- [ras-grpc-gw (наш форк)](https://github.com/defin85/ras-grpc-gw)
- [v8platform/protos](https://github.com/v8platform/protos) - protobuf определения
- [cluster-service README](../go-services/cluster-service/README.md) - наша реализация

---

## ✅ Checklist для новых разработчиков

- [ ] RAS запущен на порту 1545
- [ ] ras-grpc-gw запущен на порту 9999
- [ ] cluster-service подключается к ras-grpc-gw
- [ ] `EndpointInterceptor` настроен для переиспользования endpoint
- [ ] Логи показывают один endpoint ID для всех запросов после AuthenticateCluster
- [ ] GetShortInfobases возвращает список баз данных

---

**Версия:** 1.0
**Последнее обновление:** 2025-10-31
**Автор:** Architecture Team

**См. также:**
- `docs/ENDPOINT_MANAGEMENT_ARCHITECTURE.md` - подробности endpoint management
- `docs/SPRINT_1_PROGRESS.md` - Sprint 1.4 (RAS integration)
- `go-services/cluster-service/README.md` - cluster-service документация
