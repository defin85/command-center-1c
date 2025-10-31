# Инструкция: Применение исправления ras-grpc-gw

**Цель:** Исправить метод `AuthenticateCluster` в ras-grpc-gw для поддержки endpoint session management.

---

## Предварительные требования

1. **Доступ к репозиторию ras-grpc-gw:**
   - Fork от https://github.com/khorevaa/ras-client (или другой upstream)
   - Или локальная копия

2. **Go toolchain:** Go 1.21+ установлен

---

## Шаг 1: Найти репозиторий ras-grpc-gw

### Вариант A: Используется через go.mod

```bash
# Проверить где находится ras-grpc-gw в dependencies
cd C:\1CProject\command-center-1c\go-services\cluster-service
go mod graph | grep ras-grpc-gw

# Найти путь к модулю в GOPATH/pkg/mod
go list -m all | grep ras

# Пример вывода:
# github.com/khorevaa/ras-client v0.x.x
```

**Путь к source code:**
```
%GOPATH%\pkg\mod\github.com\khorevaa\ras-client@v0.x.x
```

### Вариант B: Локальный fork

Если вы уже создали fork:

```bash
git clone https://github.com/YOUR_USERNAME/ras-client
cd ras-client
```

---

## Шаг 2: Применить изменение

### Файл для изменения

```
ras-client/
  └── internal/
      └── server/
          └── server.go
```

### Найти метод AuthenticateCluster

```bash
# Поиск в файле server.go
grep -n "AuthenticateCluster" internal/server/server.go

# Пример вывода:
# 137:func (s *rasClientServiceServer) AuthenticateCluster(ctx context.Context, request *messagesv1.ClusterAuthenticateRequest) (*emptypb.Empty, error) {
```

### Исходный код (ДО изменения)

```go
// Примерно строки 137-146
func (s *rasClientServiceServer) AuthenticateCluster(ctx context.Context, request *messagesv1.ClusterAuthenticateRequest) (*emptypb.Empty, error) {
    endpoint, err := s.client.GetEndpoint(ctx)
    if err != nil {
        return nil, err
    }
    return endpoint.AuthenticateCluster(ctx, request)
}
```

### Новый код (ПОСЛЕ изменения)

```go
func (s *rasClientServiceServer) AuthenticateCluster(ctx context.Context, request *messagesv1.ClusterAuthenticateRequest) (*emptypb.Empty, error) {
    return withEndpoint(ctx, s.client, func(ctx context.Context, endpoint clientv1.EndpointServiceImpl) (*emptypb.Empty, error) {
        return endpoint.AuthenticateCluster(ctx, request)
    })
}
```

### Применить изменение вручную

**Откройте файл:**
```bash
# В вашем любимом редакторе
code internal/server/server.go
# или
vim internal/server/server.go
```

**Замените тело метода согласно примеру выше.**

---

## Шаг 3: Проверить компиляцию

```bash
# В корне ras-client репозитория
go build ./...

# Ожидаемый вывод:
# (без ошибок)
```

Если есть ошибки компиляции:
- Убедитесь что `withEndpoint` доступна в том же файле
- Проверьте imports

---

## Шаг 4: Запустить тесты (если есть)

```bash
go test ./...
```

Если тесты падают - анализируйте вывод. Большинство тестов должны продолжить работать, так как изменение backward compatible.

---

## Шаг 5: Интеграция с cluster-service

### Вариант A: Использовать локальный replace (для разработки)

**В `go-services/cluster-service/go.mod`:**

```go
module github.com/your-org/command-center-1c/cluster-service

go 1.21

require (
    github.com/khorevaa/ras-client v0.x.x
    // ... другие dependencies
)

// ВРЕМЕННО для тестирования локального исправления
replace github.com/khorevaa/ras-client => C:/path/to/local/ras-client
```

**Затем:**

```bash
cd C:\1CProject\command-center-1c\go-services\cluster-service
go mod tidy
go build ./...
```

### Вариант B: Опубликовать fork и использовать его

**1. Создать fork на GitHub:**

```bash
# Если еще не создали
cd C:\path\to\ras-client
git remote add origin https://github.com/YOUR_USERNAME/ras-client.git
git add internal/server/server.go
git commit -m "feat: Return endpoint_id from AuthenticateCluster"
git push origin main
```

**2. Создать tag/release:**

```bash
git tag v0.x.x-patched
git push origin v0.x.x-patched
```

**3. Обновить go.mod в cluster-service:**

```go
require (
    github.com/YOUR_USERNAME/ras-client v0.x.x-patched
)
```

```bash
go mod tidy
```

---

## Шаг 6: Тестирование интеграции

### Test Case 1: Проверка endpoint_id в логах

**Запустить cluster-service:**

```bash
cd C:\1CProject\command-center-1c\go-services\cluster-service
go run cmd/main.go
```

**Ожидаемые логи:**

```
[EndpointInterceptor] Created without initial endpoint_id (will be assigned by ras-grpc-gw)
[EndpointInterceptor] No endpoint_id yet, letting ras-grpc-gw create new endpoint (method: /v1.RasClientService/AuthenticateCluster)
[EndpointInterceptor] Received new endpoint_id from server: 1 (replacing )
[EndpointInterceptor] Adding endpoint_id to request: 1 (method: /v1.RasClientService/GetShortInfobases)
✅ GetShortInfobases SUCCESS
```

### Test Case 2: Проверка grpcurl

**Вызвать AuthenticateCluster напрямую:**

```bash
grpcurl -plaintext \
  -d '{
    "cluster": "localhost:1541",
    "credentials": {
      "username": "admin",
      "password": ""
    }
  }' \
  -v \
  localhost:1540 \
  v1.RasClientService/AuthenticateCluster
```

**Ожидаемый вывод:**

```
Response headers received:
content-type: application/grpc
endpoint_id: 1         ← ✅ КРИТИЧНО: должен присутствовать

Response contents:
{}
```

---

## Шаг 7: Создание PR в upstream (опционально)

**Если вы хотите внести вклад в upstream ras-grpc-gw:**

### 1. Создать feature branch

```bash
cd C:\path\to\ras-client
git checkout -b feat/auth-endpoint-id
```

### 2. Применить изменение (уже сделано в Шаге 2)

### 3. Написать commit message

```bash
git add internal/server/server.go
git commit -m "feat: Return endpoint_id from AuthenticateCluster for session management

## Problem

AuthenticateCluster does not return endpoint_id in response headers,
unlike other methods (GetInfobases, GetClusters, etc.).

This prevents clients from reusing the authenticated endpoint in
subsequent requests.

## Solution

Use withEndpoint() wrapper for AuthenticateCluster to return
endpoint_id in response headers, aligning it with other methods.

## Changes

- Modified AuthenticateCluster to use withEndpoint() wrapper

## Backward Compatibility

Fully backward compatible:
- Clients not reading headers: work as before
- Clients reading headers: gain session management capability
"
```

### 4. Push и создать PR

```bash
git push origin feat/auth-endpoint-id
```

Затем на GitHub:
1. Go to https://github.com/khorevaa/ras-client (или ваш upstream)
2. Click "Compare & pull request"
3. Fill in title: **"feat: Return endpoint_id from AuthenticateCluster"**
4. Paste описание из commit message
5. Submit PR

---

## Откат изменений (если нужно)

### Вариант A: Локальный replace

**Удалить `replace` директиву из go.mod:**

```bash
cd C:\1CProject\command-center-1c\go-services\cluster-service
# Удалить строку: replace github.com/khorevaa/ras-client => ...
go mod tidy
```

### Вариант B: Fork

**Вернуться на upstream:**

```go
// go.mod
require (
    github.com/khorevaa/ras-client v0.x.x  // upstream version
)
```

```bash
go mod tidy
```

---

## Troubleshooting

### Проблема 1: Не компилируется после изменения

**Симптом:**
```
undefined: withEndpoint
```

**Решение:**
- Убедитесь что `withEndpoint` определена в том же файле `server.go`
- Проверьте что она экспортируется (если в другом файле)

**Поиск withEndpoint:**
```bash
grep -rn "withEndpoint" internal/server/
```

### Проблема 2: endpoint_id не появляется в response headers

**Проверка:**
1. Убедитесь что вы применили изменение ТОЧНО как указано
2. Перекомпилируйте и перезапустите ras-grpc-gw
3. Проверьте что используете исправленную версию (не кэш)

**Debug:**
```bash
# Логи ras-grpc-gw должны показывать endpoint ID
# Добавьте log.Printf в withEndpoint если нужно
```

### Проблема 3: Тесты cluster-service падают

**Возможная причина:**
- Mock ras-grpc-gw не возвращает endpoint_id

**Решение:**
- Обновите mocks чтобы возвращать header `endpoint_id`

---

## Статус изменений

### ✅ Готово
- [x] Архитектурное решение разработано
- [x] Изменения в cluster-service применены
- [x] Документация создана

### ⏳ В процессе
- [ ] Применить изменение в ras-grpc-gw (этот гайд)
- [ ] Интеграционное тестирование
- [ ] Создать PR в upstream (опционально)

---

## Дополнительные ресурсы

- **Полное архитектурное решение:** `ENDPOINT_MANAGEMENT_ARCHITECTURE.md`
- **Минимальное изменение (summary):** `RAS_GRPC_GW_FIX.md`
- **Исходный код cluster-service:** `go-services/cluster-service/internal/grpc/interceptors/endpoint.go`

---

**Версия:** 1.0
**Последнее обновление:** 2025-10-31
**Автор:** Architecture Team
