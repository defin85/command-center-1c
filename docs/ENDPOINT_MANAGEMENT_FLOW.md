# Endpoint Management Flow: Диаграммы и визуализация

**Связанные документы:**
- `ENDPOINT_MANAGEMENT_ARCHITECTURE.md` - Полное архитектурное решение
- `RAS_GRPC_GW_FIX.md` - Минимальное исправление
- `APPLY_RAS_GRPC_GW_FIX.md` - Инструкция по применению

---

## 1. Проблема: ДО исправления

### Диаграмма: Несоответствие ключей кэша

```
┌─────────────────────────────────────────────────────────────┐
│ cluster-service (gRPC Client)                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  EndpointInterceptor {                                      │
│    endpointID: "d263f94f-7b65-450d-8c6d-e8af948737ee"      │
│  }                                                          │
│                                                             │
│  Request 1: AuthenticateCluster                            │
│    metadata["endpoint_id"] = "d263f94f-..."                │
│                                                             │
│  Request 2: GetShortInfobases                              │
│    metadata["endpoint_id"] = "d263f94f-..."                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ gRPC
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ ras-grpc-gw (gRPC Server)                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Endpoint Cache {                                           │
│    "1": endpoint_1,                                         │
│    "2": endpoint_2,                                         │
│    "3": endpoint_3,                                         │
│  }                                                          │
│                                                             │
│  Request 1: GetEndpoint()                                   │
│    Search: cache["d263f94f-..."]  ❌ NOT FOUND             │
│    Action: create NEW endpoint                              │
│    RAS assigns: ID = "3"                                    │
│    Save: cache["3"] = new_endpoint                          │
│    ⚠️ AuthenticateCluster НЕ возвращает header endpoint_id │
│                                                             │
│  Request 2: GetEndpoint()                                   │
│    Search: cache["d263f94f-..."]  ❌ NOT FOUND             │
│    Action: create NEW endpoint                              │
│    RAS assigns: ID = "4"                                    │
│    Save: cache["4"] = new_endpoint (БЕЗ AUTH!)             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ Binary Protocol
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ RAS Server (1C)                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Endpoint "3": AUTHENTICATED ✅                             │
│  Endpoint "4": NOT AUTHENTICATED ❌                         │
│                                                             │
│  GetShortInfobases on endpoint "4":                         │
│    ❌ ERROR: Недостаточно прав пользователя                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Последовательность событий (ПРОБЛЕМА)

```
Time →

cluster-service          ras-grpc-gw               RAS Server
     │                        │                         │
     │ AuthenticateCluster    │                         │
     │ metadata{              │                         │
     │   endpoint_id:         │                         │
     │   "d263f94f-..."       │                         │
     │ }                      │                         │
     ├───────────────────────>│                         │
     │                        │ Search cache            │
     │                        │ ["d263f94f-..."]        │
     │                        │ ❌ NOT FOUND            │
     │                        │                         │
     │                        │ Create endpoint         │
     │                        ├────────────────────────>│
     │                        │                         │
     │                        │<────────────────────────┤
     │                        │ endpoint ID = "3"       │
     │                        │                         │
     │                        │ cache["3"] = endpoint   │
     │                        │                         │
     │                        │ Authenticate on "3"     │
     │                        ├────────────────────────>│
     │                        │                         │
     │                        │<────────────────────────┤
     │                        │ ✅ AUTH SUCCESS         │
     │                        │                         │
     │                        │ ⚠️ NO header returned   │
     │<───────────────────────┤                         │
     │ ✅ Response: {}        │                         │
     │                        │                         │
     │ GetShortInfobases      │                         │
     │ metadata{              │                         │
     │   endpoint_id:         │                         │
     │   "d263f94f-..."       │                         │
     │ }                      │                         │
     ├───────────────────────>│                         │
     │                        │ Search cache            │
     │                        │ ["d263f94f-..."]        │
     │                        │ ❌ NOT FOUND            │
     │                        │                         │
     │                        │ Create NEW endpoint     │
     │                        ├────────────────────────>│
     │                        │                         │
     │                        │<────────────────────────┤
     │                        │ endpoint ID = "4"       │
     │                        │                         │
     │                        │ cache["4"] = endpoint   │
     │                        │                         │
     │                        │ GetInfobases on "4"     │
     │                        ├────────────────────────>│
     │                        │                         │
     │                        │<────────────────────────┤
     │                        │ ❌ NOT AUTHENTICATED    │
     │                        │                         │
     │<───────────────────────┤                         │
     │ ❌ Error: Недостаточно │                         │
     │    прав пользователя   │                         │
     │                        │                         │
```

---

## 2. Решение: ПОСЛЕ исправления

### Диаграмма: Корректный endpoint lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ cluster-service (gRPC Client)                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  EndpointInterceptor {                                      │
│    endpointID: ""  (ПУСТОЙ при создании)                   │
│  }                                                          │
│                                                             │
│  Request 1: AuthenticateCluster                            │
│    metadata: {} (БЕЗ endpoint_id)                          │
│    Response headers: endpoint_id = "1"                     │
│    Save: endpointID = "1"  ✅                              │
│                                                             │
│  Request 2: GetShortInfobases                              │
│    metadata["endpoint_id"] = "1"                           │
│    ✅ ПЕРЕИСПОЛЬЗУЕТ тот же endpoint                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ gRPC
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ ras-grpc-gw (gRPC Server)                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Endpoint Cache {                                           │
│    "1": endpoint_1 (AUTHENTICATED),                         │
│  }                                                          │
│                                                             │
│  Request 1: GetEndpoint()                                   │
│    metadata: {} (no endpoint_id)                            │
│    Action: create NEW endpoint                              │
│    RAS assigns: ID = "1"                                    │
│    Save: cache["1"] = new_endpoint                          │
│    ✅ withEndpoint() возвращает header: endpoint_id = "1"  │
│                                                             │
│  Request 2: GetEndpoint()                                   │
│    metadata["endpoint_id"] = "1"                            │
│    Search: cache["1"]  ✅ FOUND                            │
│    Action: ПЕРЕИСПОЛЬЗОВАТЬ endpoint "1"                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ Binary Protocol
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ RAS Server (1C)                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Endpoint "1": AUTHENTICATED ✅                             │
│                                                             │
│  GetShortInfobases on endpoint "1":                         │
│    ✅ SUCCESS: Infobases data returned                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Последовательность событий (РЕШЕНИЕ)

```
Time →

cluster-service          ras-grpc-gw               RAS Server
     │                        │                         │
     │ AuthenticateCluster    │                         │
     │ metadata: {}           │                         │
     │ (no endpoint_id)       │                         │
     ├───────────────────────>│                         │
     │                        │ No endpoint_id in       │
     │                        │ metadata                │
     │                        │                         │
     │                        │ Create NEW endpoint     │
     │                        ├────────────────────────>│
     │                        │                         │
     │                        │<────────────────────────┤
     │                        │ endpoint ID = "1"       │
     │                        │                         │
     │                        │ cache["1"] = endpoint   │
     │                        │                         │
     │                        │ Authenticate on "1"     │
     │                        ├────────────────────────>│
     │                        │                         │
     │                        │<────────────────────────┤
     │                        │ ✅ AUTH SUCCESS         │
     │                        │                         │
     │                        │ withEndpoint() wrapper  │
     │                        │ returns header:         │
     │                        │   endpoint_id = "1"     │
     │<───────────────────────┤                         │
     │ ✅ Response: {}        │                         │
     │    Headers:            │                         │
     │      endpoint_id: "1"  │                         │
     │                        │                         │
     │ [Interceptor saves     │                         │
     │  endpointID = "1"]     │                         │
     │                        │                         │
     │ GetShortInfobases      │                         │
     │ metadata{              │                         │
     │   endpoint_id: "1"     │                         │
     │ }                      │                         │
     ├───────────────────────>│                         │
     │                        │ Search cache["1"]       │
     │                        │ ✅ FOUND                │
     │                        │                         │
     │                        │ REUSE endpoint "1"      │
     │                        │                         │
     │                        │ GetInfobases on "1"     │
     │                        ├────────────────────────>│
     │                        │                         │
     │                        │<────────────────────────┤
     │                        │ ✅ AUTHENTICATED        │
     │                        │    Infobases data       │
     │                        │                         │
     │<───────────────────────┤                         │
     │ ✅ Success: [...data]  │                         │
     │                        │                         │
```

---

## 3. Детальный flow: EndpointInterceptor

### Жизненный цикл endpoint_id

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Initialization                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  interceptor = NewEndpointInterceptor()                     │
│  {                                                          │
│    endpointID: ""  ← ПУСТОЙ                                │
│  }                                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: First Request (AuthenticateCluster)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  UnaryClientInterceptor() {                                 │
│                                                             │
│    1. Check endpointID                                      │
│       endpointID = "" (пустой)                              │
│                                                             │
│    2. Decision:                                             │
│       if endpointID != "" {                                 │
│         // add to metadata                                  │
│       } else {                                              │
│         ✅ DO NOTHING                                       │
│         // let ras-grpc-gw create new                       │
│       }                                                     │
│                                                             │
│    3. Invoke gRPC method                                    │
│       ├─> ras-grpc-gw                                       │
│       │                                                     │
│       │   withEndpoint() wrapper:                           │
│       │   - creates endpoint                                │
│       │   - RAS assigns ID "1"                              │
│       │   - returns header: endpoint_id = "1"               │
│       │                                                     │
│       └─< Response with headers                             │
│                                                             │
│    4. Extract endpoint_id from response headers             │
│       header.Get("endpoint_id") = ["1"]                     │
│                                                             │
│    5. Save to interceptor state                             │
│       endpointID = "1"  ✅                                  │
│  }                                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Subsequent Requests (GetShortInfobases, ...)      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  UnaryClientInterceptor() {                                 │
│                                                             │
│    1. Check endpointID                                      │
│       endpointID = "1" (НЕ пустой)                          │
│                                                             │
│    2. Decision:                                             │
│       if endpointID != "" {                                 │
│         ✅ ADD to metadata                                  │
│         metadata.Set("endpoint_id", "1")                    │
│       }                                                     │
│                                                             │
│    3. Invoke gRPC method                                    │
│       ├─> ras-grpc-gw                                       │
│       │                                                     │
│       │   GetEndpoint():                                    │
│       │   - receives metadata["endpoint_id"] = "1"          │
│       │   - searches cache["1"]                             │
│       │   - ✅ FOUND → returns existing endpoint            │
│       │                                                     │
│       └─< Response (with same or new endpoint_id)           │
│                                                             │
│    4. Extract endpoint_id (может обновиться)                │
│       header.Get("endpoint_id") = ["1"]                     │
│                                                             │
│    5. Update if changed                                     │
│       if endpointID != newEndpointID {                      │
│         endpointID = newEndpointID                          │
│       }                                                     │
│  }                                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Reset (опционально, для новой сессии)             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  interceptor.Reset()                                        │
│  {                                                          │
│    endpointID = ""  ← ОЧИСТИТЬ                             │
│  }                                                          │
│                                                             │
│  → Следующий запрос создаст НОВЫЙ endpoint                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Сравнение: ДО vs ПОСЛЕ

### Таблица сравнения

| Aspect | ДО исправления | ПОСЛЕ исправления |
|--------|----------------|-------------------|
| **endpoint_id в AuthenticateCluster response** | ❌ НЕТ | ✅ ЕСТЬ |
| **cluster-service initial endpoint_id** | UUID "d263f94f-..." | Пустой "" |
| **Первый запрос metadata** | endpoint_id: UUID | Нет endpoint_id |
| **ras-grpc-gw создает endpoint** | Каждый запрос | Только первый |
| **Кэш ras-grpc-gw** | cache["UUID"] ❌ NOT FOUND | cache["1"] ✅ FOUND |
| **Endpoint reuse** | ❌ НЕТ | ✅ ДА |
| **AuthenticateCluster endpoint ID** | "3" | "1" |
| **GetShortInfobases endpoint ID** | "4" (новый) | "1" (тот же) |
| **Authentication status** | Endpoint "4" НЕ auth | Endpoint "1" auth |
| **Результат** | ❌ ERROR | ✅ SUCCESS |

### Количество созданных endpoints

**ДО:**
```
Request 1 (AuthenticateCluster):  endpoint "3" created
Request 2 (GetShortInfobases):    endpoint "4" created
Request 3 (...):                  endpoint "5" created
...
```

**ПОСЛЕ:**
```
Request 1 (AuthenticateCluster):  endpoint "1" created
Request 2 (GetShortInfobases):    endpoint "1" reused ✅
Request 3 (...):                  endpoint "1" reused ✅
...
```

---

## 5. Код изменения (визуализация)

### ras-grpc-gw: AuthenticateCluster

```diff
 func (s *rasClientServiceServer) AuthenticateCluster(ctx context.Context, request *messagesv1.ClusterAuthenticateRequest) (*emptypb.Empty, error) {
-    endpoint, err := s.client.GetEndpoint(ctx)
-    if err != nil {
-        return nil, err
-    }
-    return endpoint.AuthenticateCluster(ctx, request)
+    return withEndpoint(ctx, s.client, func(ctx context.Context, endpoint clientv1.EndpointServiceImpl) (*emptypb.Empty, error) {
+        return endpoint.AuthenticateCluster(ctx, request)
+    })
 }
```

**Изменения:**
- ➖ Убрали прямой вызов `GetEndpoint()`
- ➕ Добавили `withEndpoint()` wrapper
- ✅ Результат: метод теперь возвращает `endpoint_id` в response headers

### cluster-service: EndpointInterceptor

```diff
 func NewEndpointInterceptor() *EndpointInterceptor {
-    endpointID := uuid.New().String()
-    log.Printf("[EndpointInterceptor] Created with new endpoint_id: %s", endpointID)
+    log.Printf("[EndpointInterceptor] Created without initial endpoint_id (will be assigned by ras-grpc-gw)")
     return &EndpointInterceptor{
-        endpointID: endpointID,
+        endpointID: "",
     }
 }
```

```diff
 func (e *EndpointInterceptor) UnaryClientInterceptor() grpc.UnaryClientInterceptor {
     // ...
-    log.Printf("[EndpointInterceptor] Adding endpoint_id to request: %s", endpointID)
-    md = md.Copy()
-    md.Set("endpoint_id", endpointID)
-    ctx = metadata.NewOutgoingContext(ctx, md)
+    if endpointID != "" {
+        log.Printf("[EndpointInterceptor] Adding endpoint_id to request: %s", endpointID)
+        md = md.Copy()
+        md.Set("endpoint_id", endpointID)
+        ctx = metadata.NewOutgoingContext(ctx, md)
+    } else {
+        log.Printf("[EndpointInterceptor] No endpoint_id yet, letting ras-grpc-gw create new endpoint")
+    }
     // ...
 }
```

**Изменения:**
- ➖ Убрали генерацию UUID
- ➕ Начинаем с пустого `endpointID = ""`
- ✅ Отправляем `endpoint_id` ТОЛЬКО если он уже получен от сервера

---

## 6. Ожидаемые логи

### Успешный сценарий (ПОСЛЕ исправления)

```
[cluster-service]
  [EndpointInterceptor] Created without initial endpoint_id (will be assigned by ras-grpc-gw)

[cluster-service]
  [EndpointInterceptor] No endpoint_id yet, letting ras-grpc-gw create new endpoint (method: /v1.RasClientService/AuthenticateCluster)

[ras-grpc-gw]
  1   ← endpoint created with ID "1"

[cluster-service]
  [EndpointInterceptor] Received new endpoint_id from server: 1 (replacing )

[cluster-service]
  [EndpointInterceptor] Adding endpoint_id to request: 1 (method: /v1.RasClientService/GetShortInfobases)

[ras-grpc-gw]
  ← GetShortInfobases reusing endpoint "1" (no log, endpoint found in cache)

[cluster-service]
  ✅ GetShortInfobases SUCCESS: [... infobases data ...]
```

### Проблемный сценарий (ДО исправления)

```
[cluster-service]
  [EndpointInterceptor] Created with new endpoint_id: d263f94f-7b65-450d-8c6d-e8af948737ee

[cluster-service]
  [EndpointInterceptor] Adding endpoint_id to request: d263f94f-... (method: /v1.RasClientService/AuthenticateCluster)

[ras-grpc-gw]
  3   ← endpoint created with ID "3" (not found UUID in cache)

[cluster-service]
  [EndpointInterceptor] Adding endpoint_id to request: d263f94f-... (method: /v1.RasClientService/GetShortInfobases)

[ras-grpc-gw]
  4   ← endpoint created with ID "4" (not found UUID in cache, created NEW)

[cluster-service]
  ❌ ERROR: Недостаточно прав пользователя на управление кластером
```

---

## 7. Граф зависимостей

```
┌─────────────────────┐
│ AuthenticateCluster │
│ успешно завершен    │
│ endpoint_id = "1"   │
└──────────┬──────────┘
           │
           │ endpoint_id передан в metadata
           │
           ▼
┌─────────────────────┐
│ GetShortInfobases   │
│ использует endpoint │
│ "1" (с auth)        │
└──────────┬──────────┘
           │
           │ endpoint_id передан в metadata
           │
           ▼
┌─────────────────────┐
│ GetClusters         │
│ использует endpoint │
│ "1" (с auth)        │
└──────────┬──────────┘
           │
           ...
```

**Ключевое свойство:** Все запросы после `AuthenticateCluster` переиспользуют тот же endpoint "1" с сохраненной аутентификацией.

---

## 8. Метрики успеха

### Критерий 1: Один endpoint для всей сессии

```bash
# Проверка логов ras-grpc-gw
grep -E "^[0-9]+$" ras-grpc-gw.log | sort -u

# ОЖИДАЕТСЯ (ПОСЛЕ):
1

# БЫЛО (ДО):
3
4
5
6
...
```

### Критерий 2: endpoint_id в response headers

```bash
# grpcurl test
grpcurl -plaintext -v ... v1.RasClientService/AuthenticateCluster

# ОЖИДАЕТСЯ:
Response headers received:
endpoint_id: 1       ← ✅ КРИТИЧНО
```

### Критерий 3: GetShortInfobases SUCCESS

```bash
# Логи cluster-service
grep "GetShortInfobases" cluster-service.log

# ОЖИДАЕТСЯ:
✅ GetShortInfobases SUCCESS
```

---

**Версия:** 1.0
**Последнее обновление:** 2025-10-31
**Автор:** Architecture Team
