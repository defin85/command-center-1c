# React Query + Real-time Updates Roadmap

> Интеграция React Query для кэширования с WebSocket для real-time обновлений

**Дата создания:** 2025-12-10
**Статус:** Planned
**Приоритет:** Medium
**Оценка:** 1-2 недели
**Зависимости:** useServiceMesh (уже реализован)

---

## Содержание

1. [Проблемы текущего состояния](#проблемы-текущего-состояния)
2. [Целевая архитектура](#целевая-архитектура)
3. [Phase 1: React Query Setup](#phase-1-react-query-setup-2-3-часа)
4. [Phase 2: Dashboard Migration](#phase-2-dashboard-migration-4-6-часов)
5. [Phase 3: WebSocket Invalidation](#phase-3-websocket-invalidation-4-6-часов)
6. [Phase 4: Other Pages Migration](#phase-4-other-pages-migration-2-3-дня)
7. [Phase 5: Optimistic Updates](#phase-5-optimistic-updates-опционально)

---

## Проблемы текущего состояния

### 1. Нет кэширования между навигациями

```
User открывает /dashboard → 3 API запроса
User переходит на /databases → ...
User возвращается на /dashboard → ещё 3 API запроса (те же данные!)
```

**Результат:** Лишний трафик, задержка при навигации.

### 2. CanceledError при быстрой навигации

```typescript
// Текущий код в useDashboardStats.ts
} catch (error) {
  if (error.name === 'CanceledError') return  // ← Workaround, не решение
}
```

**Проблема:** Запросы отправляются, потом отменяются → wasted bandwidth.

### 3. Нет stale-while-revalidate

При обновлении данных пользователь видит loading spinner вместо старых данных.

### 4. Manual polling vs Push

```typescript
// Текущее: polling каждые 30-60 сек
useEffect(() => {
  const interval = setInterval(fetchData, 60000)
  return () => clearInterval(interval)
}, [])

// Проблема: данные могут измениться через 1 сек после fetch
// Пользователь увидит обновление только через 59 сек
```

### 5. Дублирование логики

Каждая страница реализует свой fetch + error handling + loading state.

---

## Целевая архитектура

### Гибридный подход: React Query + WebSocket

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐              │
│  │   React Query    │ ←────── │  WebSocket       │              │
│  │   (Cache Layer)  │  invalidate  │  (useServiceMesh)│         │
│  └────────┬─────────┘         └──────────────────┘              │
│           │                            ↑                         │
│           │ fetch                      │ events                  │
│           ↓                            │                         │
├─────────────────────────────────────────────────────────────────┤
│                         BACKEND                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐              │
│  │   REST API v2    │         │  WebSocket       │              │
│  │   (Source of     │         │  Consumer        │              │
│  │    Truth)        │         │  (Notifications) │              │
│  └──────────────────┘         └──────────────────┘              │
│                                        ↑                         │
│                                        │ signals                 │
│                                        │                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Django Signals: post_save(BatchOperation), etc.         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Принципы

1. **REST API = Source of Truth** — данные всегда берутся через API
2. **React Query = Cache Layer** — кэширует, дедуплицирует, retry
3. **WebSocket = Notification Channel** — только сигналы "данные изменились"
4. **Separation of Concerns** — каждый компонент делает одно дело

### Преимущества

| До | После |
|----|-------|
| 3 запроса при каждом открытии Dashboard | 0 запросов если данные свежие |
| Spinner при навигации | Instant показ из кэша |
| Polling каждые 60 сек | Push при изменении |
| Manual error handling | Automatic retry |
| CanceledError workarounds | Automatic request deduplication |

---

## Phase 1: React Query Setup (2-3 часа)

### 1.1 Установка зависимостей

```bash
cd frontend
npm install @tanstack/react-query @tanstack/react-query-devtools
```

### 1.2 Настройка QueryClient

**Файл:** `frontend/src/main.tsx`

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,        // 30 сек — данные считаются свежими
      gcTime: 5 * 60 * 1000,       // 5 мин — хранить в кэше
      retry: 2,                     // 2 retry при ошибке
      refetchOnWindowFocus: true,   // Обновить при возврате в таб
      refetchOnReconnect: true,     // Обновить при восстановлении сети
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
```

### 1.3 Создание базовых хуков

**Файл:** `frontend/src/api/queries/index.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../client'

// Query keys factory
export const queryKeys = {
  operations: {
    all: ['operations'] as const,
    list: (filters?: OperationFilters) => [...queryKeys.operations.all, 'list', filters] as const,
    detail: (id: string) => [...queryKeys.operations.all, 'detail', id] as const,
  },
  databases: {
    all: ['databases'] as const,
    list: (filters?: DatabaseFilters) => [...queryKeys.databases.all, 'list', filters] as const,
    detail: (id: string) => [...queryKeys.databases.all, 'detail', id] as const,
  },
  clusters: {
    all: ['clusters'] as const,
    list: () => [...queryKeys.clusters.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.clusters.all, 'detail', id] as const,
  },
  dashboard: {
    stats: ['dashboard', 'stats'] as const,
  },
}
```

### Критерии завершения Phase 1

- [ ] React Query установлен
- [ ] QueryClientProvider настроен в main.tsx
- [ ] DevTools доступны в development
- [ ] Query keys factory создан
- [ ] Базовые типы определены

---

## Phase 2: Dashboard Migration (4-6 часов)

### 2.1 Создание query hooks для Dashboard

**Файл:** `frontend/src/api/queries/dashboard.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from './index'
import type { BatchOperation, Database, Cluster } from '../generated/model'

interface DashboardStatsResponse {
  operations: BatchOperation[]
  databases: Database[]
  clusters: Cluster[]
}

async function fetchDashboardStats(): Promise<DashboardStatsResponse> {
  const [operationsRes, databasesRes, clustersRes] = await Promise.all([
    apiClient.get('/api/v2/operations/list-operations/', { params: { limit: 100 } }),
    apiClient.get('/api/v2/databases/list-databases/'),
    apiClient.get('/api/v2/clusters/list-clusters/'),
  ])

  return {
    operations: operationsRes.data.operations,
    databases: databasesRes.data.databases,
    clusters: clustersRes.data.clusters,
  }
}

export function useDashboardStats() {
  return useQuery({
    queryKey: queryKeys.dashboard.stats,
    queryFn: fetchDashboardStats,
    staleTime: 60 * 1000,  // 1 минута для Dashboard
  })
}
```

### 2.2 Рефакторинг useDashboardStats.ts

**До:** ~320 строк с useState, useEffect, AbortController, error handling
**После:** ~50 строк

```typescript
// frontend/src/pages/Dashboard/hooks/useDashboardStats.ts
import { useMemo } from 'react'
import { useDashboardStats as useDashboardQuery } from '../../../api/queries/dashboard'
import { calculateOperationsStats, calculateDatabasesStats, calculateClusterStats } from './calculations'
import type { DashboardStats } from '../types'

export function useDashboardStats(): DashboardStats & { refresh: () => void } {
  const { data, isLoading, error, refetch } = useDashboardQuery()

  const stats = useMemo(() => {
    if (!data) return null

    return {
      operations: calculateOperationsStats(data.operations),
      databases: calculateDatabasesStats(data.databases),
      clusters: calculateClusterStats(data.clusters, data.databases),
      recentOperations: data.operations.slice(0, 5),
      failedOperations: data.operations.filter(op => op.status === 'failed'),
    }
  }, [data])

  return {
    ...stats,
    loading: isLoading,
    error: error?.message ?? null,
    lastUpdated: data ? new Date() : null,
    refresh: refetch,
  }
}
```

### 2.3 Удаление boilerplate

Удалить из useDashboardStats.ts:
- useState для loading/error
- useEffect для fetch
- AbortController логику
- Manual retry логику
- CanceledError handling

### Критерии завершения Phase 2

- [ ] useDashboardQuery создан
- [ ] useDashboardStats рефакторен на React Query
- [ ] Dashboard работает без регрессий
- [ ] Навигация туда-обратно использует кэш (проверить Network tab)
- [ ] DevTools показывают кэшированные данные

---

## Phase 3: WebSocket Invalidation (4-6 часов)

### 3.1 Расширение WebSocket consumer (Backend)

**Файл:** `orchestrator/apps/core/consumers.py`

```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class ServiceMeshConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await super().connect()
        # Подписка на dashboard группу
        await self.channel_layer.group_add("dashboard_updates", self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dashboard_updates", self.channel_name)
        await super().disconnect(close_code)

    # Новый handler для dashboard updates
    async def dashboard_invalidate(self, event):
        """Отправить сигнал клиенту о необходимости обновления."""
        await self.send(text_data=json.dumps({
            "type": "dashboard_invalidate",
            "scope": event.get("scope", "all"),  # "operations", "databases", "clusters", "all"
            "timestamp": event.get("timestamp"),
        }))
```

### 3.2 Django signals для broadcast

**Файл:** `orchestrator/apps/operations/signals.py`

```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import BatchOperation

channel_layer = get_channel_layer()

@receiver(post_save, sender=BatchOperation)
def on_operation_changed(sender, instance, created, **kwargs):
    """Broadcast при создании/изменении операции."""
    async_to_sync(channel_layer.group_send)(
        "dashboard_updates",
        {
            "type": "dashboard.invalidate",
            "scope": "operations",
            "timestamp": instance.updated_at.isoformat(),
        }
    )

@receiver(post_delete, sender=BatchOperation)
def on_operation_deleted(sender, instance, **kwargs):
    """Broadcast при удалении операции."""
    async_to_sync(channel_layer.group_send)(
        "dashboard_updates",
        {
            "type": "dashboard.invalidate",
            "scope": "operations",
            "timestamp": datetime.now().isoformat(),
        }
    )
```

### 3.3 Frontend: invalidation hook

**Файл:** `frontend/src/hooks/useRealtimeInvalidation.ts`

```typescript
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useServiceMesh } from './useServiceMesh'
import { queryKeys } from '../api/queries'

/**
 * Подписка на WebSocket события для invalidation React Query кэша.
 * Используется на уровне App для глобального эффекта.
 */
export function useRealtimeInvalidation() {
  const queryClient = useQueryClient()
  const { /* существующие поля */ } = useServiceMesh()

  useEffect(() => {
    // Расширить useServiceMesh для обработки dashboard_invalidate
    // или создать отдельный listener

    const handleInvalidate = (scope: string) => {
      switch (scope) {
        case 'operations':
          queryClient.invalidateQueries({ queryKey: queryKeys.operations.all })
          queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.stats })
          break
        case 'databases':
          queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
          queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.stats })
          break
        case 'clusters':
          queryClient.invalidateQueries({ queryKey: queryKeys.clusters.all })
          queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.stats })
          break
        case 'all':
        default:
          queryClient.invalidateQueries()
          break
      }
    }

    // TODO: Интегрировать с useServiceMesh
    // ws.on('dashboard_invalidate', (msg) => handleInvalidate(msg.scope))

  }, [queryClient])
}
```

### 3.4 Интеграция в App

**Файл:** `frontend/src/App.tsx`

```typescript
function App() {
  // Глобальная подписка на invalidation
  useRealtimeInvalidation()

  return (
    // ...existing code
  )
}
```

### Критерии завершения Phase 3

- [ ] WebSocket consumer расширен для dashboard_invalidate
- [ ] Django signals отправляют broadcast при изменениях
- [ ] useRealtimeInvalidation создан
- [ ] При изменении операции Dashboard обновляется автоматически
- [ ] Тест: создать операцию → Dashboard обновился без refresh

---

## Phase 4: Other Pages Migration (2-3 дня)

### 4.1 Databases Page

```typescript
// frontend/src/api/queries/databases.ts
export function useDatabases(filters?: DatabaseFilters) {
  return useQuery({
    queryKey: queryKeys.databases.list(filters),
    queryFn: () => fetchDatabases(filters),
  })
}

export function useDatabase(id: string) {
  return useQuery({
    queryKey: queryKeys.databases.detail(id),
    queryFn: () => fetchDatabase(id),
    enabled: !!id,
  })
}
```

### 4.2 Operations Page

```typescript
// frontend/src/api/queries/operations.ts
export function useOperations(filters?: OperationFilters) {
  return useQuery({
    queryKey: queryKeys.operations.list(filters),
    queryFn: () => fetchOperations(filters),
    refetchInterval: 10000,  // Операции обновляются чаще
  })
}

export function useOperation(id: string) {
  return useQuery({
    queryKey: queryKeys.operations.detail(id),
    queryFn: () => fetchOperation(id),
    enabled: !!id,
    refetchInterval: (data) =>
      data?.status === 'running' ? 2000 : false,  // Poll только running
  })
}
```

### 4.3 Clusters Page

```typescript
// frontend/src/api/queries/clusters.ts
export function useClusters() {
  return useQuery({
    queryKey: queryKeys.clusters.list(),
    queryFn: fetchClusters,
  })
}
```

### Критерии завершения Phase 4

- [ ] Databases page использует React Query
- [ ] Operations page использует React Query
- [ ] Clusters page использует React Query
- [ ] Все страницы работают с кэшированием
- [ ] WebSocket invalidation работает для всех страниц

---

## Phase 5: Optimistic Updates (опционально)

### Концепция

При мутации (создание/удаление) обновлять UI сразу, не дожидаясь ответа сервера.

```typescript
// Пример: удаление операции
export function useDeleteOperation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteOperation,

    onMutate: async (operationId) => {
      // Отменить текущие запросы
      await queryClient.cancelQueries({ queryKey: queryKeys.operations.all })

      // Сохранить предыдущее состояние
      const previousOperations = queryClient.getQueryData(queryKeys.operations.list())

      // Оптимистично удалить
      queryClient.setQueryData(
        queryKeys.operations.list(),
        (old) => old?.filter(op => op.id !== operationId)
      )

      return { previousOperations }
    },

    onError: (err, operationId, context) => {
      // Откатить при ошибке
      queryClient.setQueryData(
        queryKeys.operations.list(),
        context?.previousOperations
      )
    },

    onSettled: () => {
      // Всегда обновить после завершения
      queryClient.invalidateQueries({ queryKey: queryKeys.operations.all })
    },
  })
}
```

### Критерии завершения Phase 5

- [ ] Optimistic updates для delete операций
- [ ] Optimistic updates для create операций
- [ ] Rollback при ошибках работает корректно

---

## Метрики успеха

| Метрика | До | После |
|---------|-----|-------|
| API запросов при навигации Dashboard | 3 | 0 (из кэша) |
| Время до отображения данных | ~500ms | ~0ms (кэш) |
| Задержка обновления при изменении | 30-60 сек | ~100ms |
| Строк кода в useDashboardStats | ~320 | ~50 |
| CanceledError в консоли | Часто | Никогда |

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| WebSocket disconnect | Средняя | Fallback на polling при disconnect |
| Stale data в кэше | Низкая | staleTime + WebSocket invalidation |
| Race conditions | Низкая | React Query handles automatically |
| Bundle size increase | Низкая | @tanstack/react-query ~13KB gzipped |

---

## Ссылки

- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [React Query + WebSocket Example](https://tanstack.com/query/latest/docs/react/guides/mutations#invalidating-queries)
- [useServiceMesh.ts](../frontend/src/hooks/useServiceMesh.ts) — существующий WebSocket хук
