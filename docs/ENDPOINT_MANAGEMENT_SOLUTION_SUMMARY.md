# Endpoint Management Solution: Executive Summary

**Дата:** 2025-10-31
**Статус:** ✅ cluster-service готов | ⏳ ras-grpc-gw требует изменений
**Приоритет:** HIGH (блокирует интеграцию с RAS)

---

## TL;DR

**Проблема:** Каждый gRPC запрос от cluster-service к ras-grpc-gw создает новый endpoint в RAS, из-за чего `GetShortInfobases` работает на endpoint без аутентификации после `AuthenticateCluster`.

**Решение:** Исправить **1 метод** в ras-grpc-gw (`AuthenticateCluster` → использовать `withEndpoint()` wrapper) и улучшить `EndpointInterceptor` в cluster-service (не отправлять UUID, ждать RAS ID).

**Изменения:**
- ✅ **cluster-service:** 3 файла модифицированы (DONE)
- ⏳ **ras-grpc-gw:** 1 файл, 1 метод, 3 строки кода (TODO)

**Результат:** Все запросы после `AuthenticateCluster` переиспользуют один endpoint с сохраненной аутентификацией.

---

## Проблема в деталях

### Симптом

```
ERROR: Недостаточно прав пользователя на управление кластером
```

### Причина

1. **cluster-service** генерирует UUID `"d263f94f-..."` и отправляет в каждом запросе
2. **ras-grpc-gw** кэширует endpoints по RAS-assigned numeric IDs: `"1"`, `"2"`, `"3"`
3. **Поиск проваливается:** `cache["d263f94f-..."]` ❌ NOT FOUND
4. **Каждый запрос создает новый endpoint:**
   - `AuthenticateCluster` → endpoint "3" (с auth)
   - `GetShortInfobases` → endpoint "4" (БЕЗ auth)
5. **`AuthenticateCluster` не возвращает `endpoint_id`** в response headers

### Корневая проблема

**ras-grpc-gw: `AuthenticateCluster` не использует `withEndpoint()` wrapper**, в отличие от всех других методов.

---

## Решение

### Архитектурный подход

**НЕ отправлять endpoint_id от cluster-service → позволить ras-grpc-gw создать → получить RAS-assigned ID → переиспользовать**

### Изменения

#### 1. ras-grpc-gw (КРИТИЧНО)

**Файл:** `internal/server/server.go`

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

**Эффект:** Метод теперь возвращает `endpoint_id` в response headers (через `withEndpoint()` wrapper).

#### 2. cluster-service (✅ DONE)

**Файл:** `go-services/cluster-service/internal/grpc/interceptors/endpoint.go`

**Изменения:**
- ❌ Убрали генерацию UUID при создании interceptor
- ✅ Начинаем с `endpointID = ""`
- ✅ НЕ отправляем `endpoint_id` если он пустой
- ✅ Получаем RAS-assigned ID из response headers и сохраняем
- ✅ Последующие запросы отправляют сохраненный RAS ID

---

## Flow (ПОСЛЕ исправления)

```
1. cluster-service: AuthenticateCluster
   metadata: {} (БЕЗ endpoint_id)
   ↓
2. ras-grpc-gw: создает новый endpoint
   RAS назначает ID "1"
   ↓
3. ras-grpc-gw: возвращает header "endpoint_id: 1"
   ↓
4. cluster-service: EndpointInterceptor сохраняет endpointID = "1"
   ↓
5. cluster-service: GetShortInfobases
   metadata: {endpoint_id: "1"}
   ↓
6. ras-grpc-gw: находит endpoint "1" в кэше
   Переиспользует (с auth)
   ↓
7. ✅ SUCCESS: Infobases data получены
```

---

## Документация

### Основные документы

1. **ENDPOINT_MANAGEMENT_ARCHITECTURE.md** - Полное архитектурное решение
   - Анализ проблемы
   - Рассмотренные варианты
   - Выбранное решение с обоснованием
   - План реализации
   - Риски и митигация

2. **RAS_GRPC_GW_FIX.md** - Минимальное исправление ras-grpc-gw
   - Точное изменение (1 метод)
   - Обоснование
   - Тестирование
   - Upstream PR template

3. **APPLY_RAS_GRPC_GW_FIX.md** - Инструкция по применению
   - Пошаговое руководство
   - Интеграция с cluster-service
   - Тестирование
   - Troubleshooting

4. **ENDPOINT_MANAGEMENT_FLOW.md** - Диаграммы и визуализация
   - Последовательность событий
   - Сравнение ДО/ПОСЛЕ
   - Ожидаемые логи

### Измененные файлы (cluster-service)

```
go-services/cluster-service/internal/grpc/interceptors/endpoint.go
```

---

## Статус изменений

### ✅ Выполнено

- [x] Архитектурное решение разработано
- [x] Документация создана (4 документа)
- [x] cluster-service: EndpointInterceptor обновлен
- [x] Удален неиспользуемый import (uuid)

### ⏳ Ожидает выполнения

- [ ] Fork ras-grpc-gw
- [ ] Применить исправление AuthenticateCluster
- [ ] Интеграционное тестирование
- [ ] Создать PR в upstream ras-grpc-gw

---

## Следующие шаги

### Шаг 1: Применить исправление ras-grpc-gw

**Опции:**

**A. Локальная разработка (рекомендуется для тестирования):**

```bash
# 1. Найти или клонировать ras-grpc-gw
git clone https://github.com/khorevaa/ras-client
cd ras-client

# 2. Применить изменение согласно APPLY_RAS_GRPC_GW_FIX.md
# Изменить internal/server/server.go (метод AuthenticateCluster)

# 3. Использовать replace в go.mod cluster-service
# go.mod:
replace github.com/khorevaa/ras-client => C:/path/to/local/ras-client
```

**B. Fork + PR (для production):**

```bash
# 1. Fork на GitHub
# 2. Применить изменение
# 3. Push to fork
# 4. Создать PR в upstream (template в RAS_GRPC_GW_FIX.md)
```

### Шаг 2: Тестирование

```bash
# 1. Запустить cluster-service с исправленным ras-grpc-gw
cd go-services/cluster-service
go run cmd/main.go

# 2. Проверить логи
# ОЖИДАЕТСЯ:
# [EndpointInterceptor] No endpoint_id yet, letting ras-grpc-gw create new endpoint
# [EndpointInterceptor] Received new endpoint_id from server: 1
# [EndpointInterceptor] Adding endpoint_id to request: 1
# ✅ GetShortInfobases SUCCESS
```

### Шаг 3: Commit изменений cluster-service

```bash
cd /c/1CProject/command-center-1c

# Добавить файлы
git add docs/ENDPOINT_MANAGEMENT_*.md
git add docs/RAS_GRPC_GW_FIX.md
git add docs/APPLY_RAS_GRPC_GW_FIX.md
git add go-services/cluster-service/internal/grpc/interceptors/endpoint.go

# Commit
git commit -m "[cluster-service] Fix endpoint management for ras-grpc-gw integration

- Remove UUID generation from EndpointInterceptor
- Start with empty endpoint_id, wait for RAS-assigned ID
- Only send endpoint_id in metadata if already received from server
- Extract endpoint_id from response headers and cache for reuse

This fixes the issue where each gRPC request created a new endpoint,
preventing GetShortInfobases from reusing authenticated endpoint
from AuthenticateCluster.

Requires corresponding fix in ras-grpc-gw (see docs/RAS_GRPC_GW_FIX.md)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"
```

---

## Критерии успеха

### 1. Один endpoint для всей сессии

```bash
# Логи ras-grpc-gw показывают только один ID
grep -E "^[0-9]+$" ras-grpc-gw.log | sort -u
# OUTPUT: 1
```

### 2. endpoint_id в AuthenticateCluster response

```bash
grpcurl -v ... v1.RasClientService/AuthenticateCluster | grep endpoint_id
# OUTPUT: endpoint_id: 1
```

### 3. GetShortInfobases SUCCESS

```bash
# Логи cluster-service
grep "GetShortInfobases" cluster-service.log
# OUTPUT: ✅ GetShortInfobases SUCCESS
```

---

## Риски

### Риск 1: Upstream ras-grpc-gw не принимает PR

**Вероятность:** Средняя
**Impact:** Средний

**Митигация:**
- Поддерживать собственный fork
- Зафиксировать версию в go.mod
- Периодически синхронизировать с upstream

### Риск 2: Breaking changes в ras-grpc-gw

**Вероятность:** Низкая
**Impact:** Высокий

**Митигация:**
- Зафиксировать версию в go.mod
- Интеграционные тесты на совместимость
- Тестировать обновления перед применением

---

## Альтернативные решения (НЕ выбраны)

### A1: Client-Side Endpoint Mapping

**Проблема:** Не решает отсутствие endpoint_id от AuthenticateCluster

### A2: Stateful Connection with Re-auth

**Проблема:** Overcomplicated, performance overhead

### A3: Long-Lived gRPC Streams

**Проблема:** Overkill для request-response паттерна

### A4: Service Mesh Session Affinity

**Проблема:** Не решает проблему endpoint_id, добавляет complexity

---

## Заключение

**Выбранное решение:**
- ✅ Минимальное изменение (1 метод в ras-grpc-gw, улучшение interceptor в cluster-service)
- ✅ Логичное и простое
- ✅ Backward compatible
- ✅ cluster-service уже готов

**Блокер:**
- ⏳ Требуется исправление AuthenticateCluster в ras-grpc-gw

**Время реализации:**
- ras-grpc-gw исправление: 1-2 часа
- Тестирование: 1-2 часа
- PR review: зависит от upstream

**Приоритет:** HIGH (блокирует функциональность cluster-service)

---

## Контакты

**Документация:**
- `docs/ENDPOINT_MANAGEMENT_ARCHITECTURE.md`
- `docs/RAS_GRPC_GW_FIX.md`
- `docs/APPLY_RAS_GRPC_GW_FIX.md`
- `docs/ENDPOINT_MANAGEMENT_FLOW.md`

**Код:**
- `go-services/cluster-service/internal/grpc/interceptors/endpoint.go`

---

**Версия:** 1.0
**Последнее обновление:** 2025-10-31
**Автор:** Architecture Team
