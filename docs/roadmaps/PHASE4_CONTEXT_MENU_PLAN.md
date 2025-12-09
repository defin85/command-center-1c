# Phase 4: Context Menu Actions — План реализации

> RAS операции через очередь с единым API endpoint

**Дата создания:** 2025-12-09
**Статус:** ✅ COMPLETED
**Оценка:** 4-5 дней
**Фактически:** 1 день
**Зависимости:** Phase 1-3 (завершены)

---

## Содержание

1. [Архитектурные решения](#архитектурные-решения)
2. [Поток данных](#поток-данных)
3. [API Contract](#api-contract)
4. [Файлы для реализации](#файлы-для-реализации)
5. [Детали реализации](#детали-реализации)
6. [Оценка и риски](#оценка-и-риски)

---

## Архитектурные решения

| Вопрос | Решение | Обоснование |
|--------|---------|-------------|
| **Worker → RAS Adapter** | HTTP вызовы (не Event Bus) | Простые атомарные операции, State Machine избыточна |
| **Batch обработка** | Параллельно через goroutines | Go Worker обрабатывает все БД параллельно |
| **State Machine** | Не нужна для RAS операций | Только для сложных цепочек (install_extension) |
| **Partial success** | Поддерживается | 5/10 успешно = completed с детальной статистикой |
| **Retry policy** | 3 попытки с exponential backoff | Configurable через config |

### Почему HTTP вместо Event Bus

Для `install_extension` используется Event Bus + State Machine потому что операция многошаговая:
```
lock → terminate sessions → install → unlock
```

Для простых RAS операций (lock/unlock/block) это избыточно:
- Одна атомарная операция
- Нет промежуточных состояний
- Проще отладка и мониторинг

---

## Поток данных

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Databases Page                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ ☑ Select All  │ Bulk Actions ▼ │ Clear Selection            │    │
│  ├───┬───────────┬────────┬────────────────────────────────────┤    │
│  │ ☑ │ Database  │ Status │ Actions                            │    │
│  ├───┼───────────┼────────┼────────────────────────────────────┤    │
│  │ ☑ │ УТ_Prod   │ Active │ [⋮] ← Context Menu                 │    │
│  │ ☑ │ БП_Test   │ Active │      ┌────────────────────────┐    │    │
│  │ □ │ ЗУП_Dev   │ Maint. │      │ 🔒 Lock Jobs           │    │    │
│  └───┴───────────┴────────┴──────│ 🔓 Unlock Jobs         │────┘    │
│                                  │ ─────────────────────  │         │
│                                  │ ⛔ Block Sessions      │         │
│                                  │ ✅ Unblock Sessions    │         │
│                                  │ ❌ Terminate Sessions  │         │
│                                  │ ─────────────────────  │         │
│                                  │ 💓 Health Check        │         │
│                                  │ ⚙️ More Operations...  │         │
│                                  └────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     API GATEWAY (8180)                               │
├─────────────────────────────────────────────────────────────────────┤
│  POST /api/v2/operations/execute/                                    │
│  {                                                                   │
│    "operation_type": "lock_scheduled_jobs",                          │
│    "database_ids": ["uuid1", "uuid2", "uuid3"],                      │
│    "config": {}                                                      │
│  }                                                                   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (8200)                               │
├─────────────────────────────────────────────────────────────────────┤
│  ExecuteOperationView:                                               │
│  1. Validate request                                                 │
│  2. Create BatchOperation (status: pending)                          │
│  3. Create Task for each database_id                                 │
│  4. Call OperationsService.enqueue_ras_operation()                   │
│  5. Return operation_id                                              │
│                                                                      │
│  Response: { "operation_id": "abc123", "status": "queued" }          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      REDIS QUEUE                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Queue: cc1c:operations:v1                                           │
│  Message (OperationMessageV2):                                       │
│  {                                                                   │
│    "operation_id": "abc123",                                         │
│    "operation_type": "lock_scheduled_jobs",                          │
│    "target_databases": [                                             │
│      {"id": "uuid1", "cluster_id": "c1", "name": "УТ_Prod"},         │
│      {"id": "uuid2", "cluster_id": "c1", "name": "БП_Test"},         │
│      {"id": "uuid3", "cluster_id": "c2", "name": "ЗУП_Prod"}         │
│    ],                                                                │
│    "config": {},                                                     │
│    "execution_config": { "timeout_seconds": 60, "max_retries": 3 }   │
│  }                                                                   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      GO WORKER                                       │
├─────────────────────────────────────────────────────────────────────┤
│  RASHandler.Process():                                               │
│                                                                      │
│  1. Parse OperationMessageV2                                         │
│  2. Group databases by cluster_id                                    │
│  3. For each database (parallel goroutines):                         │
│     ┌─────────────────────────────────────────────────────────┐     │
│     │  rasClient.LockInfobase(cluster_id, infobase_id)        │     │
│     │       │                                                  │     │
│     │       ▼                                                  │     │
│     │  HTTP POST to RAS Adapter:                               │     │
│     │  http://ras-adapter:8188/api/v2/lock-infobase            │     │
│     │  ?cluster_id=c1&infobase_id=uuid1                        │     │
│     └─────────────────────────────────────────────────────────┘     │
│  4. Collect results (success/failure per database)                   │
│  5. Publish OperationResultV2 to Redis                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RAS ADAPTER (8188)                                │
├─────────────────────────────────────────────────────────────────────┤
│  POST /api/v2/lock-infobase?cluster_id=c1&infobase_id=uuid1          │
│                                                                      │
│  1. Connect to RAS Server (1545)                                     │
│  2. Execute LockInfobase via RAS Protocol                            │
│  3. Return { "success": true, "message": "Infobase locked" }         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   RESULT PROPAGATION                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Worker publishes to Redis:                                          │
│  Channel: events:worker:operation-completed                          │
│  {                                                                   │
│    "operation_id": "abc123",                                         │
│    "status": "completed",                                            │
│    "results": [                                                      │
│      {"database_id": "uuid1", "success": true},                      │
│      {"database_id": "uuid2", "success": true},                      │
│      {"database_id": "uuid3", "success": false, "error": "timeout"}  │
│    ],                                                                │
│    "summary": { "total": 3, "succeeded": 2, "failed": 1 }            │
│  }                                                                   │
│                                                                      │
│  Orchestrator webhook updates BatchOperation:                        │
│  - status: completed                                                 │
│  - completed_tasks: 2                                                │
│  - failed_tasks: 1                                                   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FRONTEND                                        │
├─────────────────────────────────────────────────────────────────────┤
│  SSE Stream / Polling:                                               │
│  GET /api/v2/operations/{operation_id}/progress/                     │
│                                                                      │
│  Progress UI:                                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Lock Scheduled Jobs                              [67%] ████░░│    │
│  │ ✅ УТ_Prod - Locked successfully                            │    │
│  │ ✅ БП_Test - Locked successfully                            │    │
│  │ ❌ ЗУП_Prod - Connection timeout                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## API Contract

### Execute Operation

```typescript
// Request
POST /api/v2/operations/execute/

interface ExecuteOperationRequest {
  operation_type:
    | 'lock_scheduled_jobs'
    | 'unlock_scheduled_jobs'
    | 'block_sessions'
    | 'unblock_sessions'
    | 'terminate_sessions'
    | 'health_check';
  database_ids: string[];  // UUIDs
  config?: {
    // Для block_sessions:
    message?: string;           // "Maintenance in progress"
    permission_code?: string;   // Код для разрешения входа
    denied_from?: string;       // ISO datetime
    denied_to?: string;         // ISO datetime
  };
}

// Response (Success)
interface ExecuteOperationResponse {
  operation_id: string;
  status: 'queued';
  total_tasks: number;
  message: string;
}

// Response (Error)
interface ErrorResponse {
  error: string;
  code: string;
  details?: Record<string, string[]>;
}
```

### Get Operation Progress

```typescript
// Request
GET /api/v2/operations/{operation_id}/

// Response
interface OperationProgressResponse {
  id: string;
  operation_type: string;
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  tasks: TaskProgress[];
}

interface TaskProgress {
  id: string;
  database_id: string;
  database_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  error_message?: string;
  started_at?: string;
  completed_at?: string;
}
```

---

## Файлы для реализации

### Backend — Orchestrator (Django)

| # | Файл | Действие | Описание | Статус |
|---|------|----------|----------|--------|
| 1 | `orchestrator/apps/api_v2/views/operations.py` | **MODIFY** | execute_operation view + сериализаторы | ✅ |
| 2 | `orchestrator/apps/api_v2/urls.py` | **MODIFY** | Добавить route `/operations/execute/` | ✅ |
| 3 | `orchestrator/apps/operations/services/operations_service.py` | **MODIFY** | Добавить `enqueue_ras_operation()` | ✅ |
| 4 | `orchestrator/apps/databases/models.py` | **MODIFY** | RBAC: PermissionLevel, ClusterPermission, DatabasePermission | ✅ |
| 5 | `orchestrator/apps/databases/services.py` | **MODIFY** | PermissionService | ✅ |
| 6 | `orchestrator/apps/databases/permissions.py` | **CREATE** | CanExecuteOperation, HasDatabasePermission | ✅ |
| 7 | `orchestrator/apps/databases/admin.py` | **MODIFY** | ClusterPermissionAdmin, DatabasePermissionAdmin | ✅ |
| 8 | `orchestrator/apps/databases/migrations/0014_add_rbac_permissions.py` | **CREATE** | RBAC migration | ✅ |

### Backend — Go Worker

| # | Файл | Действие | Описание | Статус |
|---|------|----------|----------|--------|
| 9 | `go-services/worker/internal/processor/ras_handler.go` | **CREATE** | RAS операций handler + semaphore | ✅ |
| 10 | `go-services/worker/internal/processor/processor.go` | **MODIFY** | Routing для RAS операций | ✅ |
| 11 | `go-services/worker/internal/rasadapter/client.go` | **MODIFY** | Методы для RAS операций | ✅ |

### Frontend

| # | Файл | Действие | Описание | Статус |
|---|------|----------|----------|--------|
| 12 | `frontend/src/components/actions/DatabaseActionsMenu.tsx` | **CREATE** | Context menu для одной БД | ✅ |
| 13 | `frontend/src/components/actions/BulkActionsToolbar.tsx` | **CREATE** | Toolbar для bulk операций | ✅ |
| 14 | `frontend/src/components/actions/OperationConfirmModal.tsx` | **CREATE** | Confirm dialog | ✅ |
| 15 | `frontend/src/components/actions/constants.ts` | **CREATE** | RAS_OPERATIONS константы | ✅ |
| 16 | `frontend/src/components/actions/index.ts` | **CREATE** | Re-exports | ✅ |
| 17 | `frontend/src/hooks/useDatabaseActions.ts` | **CREATE** | Hook для выполнения операций | ✅ |
| 18 | `frontend/src/pages/Databases/Databases.tsx` | **MODIFY** | Row selection + menu интеграция | ✅ |
| 19 | `frontend/src/api/operations.ts` | **CREATE** | API функции для операций | ✅ |

---

## Детали реализации

### 1. Orchestrator — ExecuteOperationView

```python
# orchestrator/apps/api_v2/views/operations.py

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.operations.services import OperationsService
from .serializers.operations import ExecuteOperationSerializer

class ExecuteOperationView(APIView):
    """
    POST /api/v2/operations/execute/

    Создаёт BatchOperation и ставит в очередь для выполнения.
    """

    def post(self, request):
        serializer = ExecuteOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        operation_type = serializer.validated_data['operation_type']
        database_ids = serializer.validated_data['database_ids']
        config = serializer.validated_data.get('config', {})

        # Создание и постановка в очередь
        batch_operation = OperationsService.enqueue_ras_operation(
            operation_type=operation_type,
            database_ids=database_ids,
            config=config,
            user=request.user,
        )

        return Response({
            'operation_id': str(batch_operation.id),
            'status': batch_operation.status,
            'total_tasks': batch_operation.total_tasks,
            'message': f'{operation_type} queued for {len(database_ids)} database(s)',
        }, status=status.HTTP_202_ACCEPTED)
```

### 2. Orchestrator — OperationsService

```python
# orchestrator/apps/operations/services/operations_service.py

@classmethod
def enqueue_ras_operation(
    cls,
    operation_type: str,
    database_ids: list[str],
    config: dict,
    user,
) -> BatchOperation:
    """
    Создаёт BatchOperation для RAS операции и ставит в очередь.
    """
    # Получить databases с cluster_id
    databases = Database.objects.filter(id__in=database_ids).select_related('cluster')

    # Создать BatchOperation
    batch_operation = BatchOperation.objects.create(
        operation_type=operation_type,
        status=BatchOperation.STATUS_PENDING,
        payload=config,
        total_tasks=len(database_ids),
        created_by=user,
    )
    batch_operation.target_databases.set(databases)

    # Создать Tasks
    tasks = [
        Task(
            batch_operation=batch_operation,
            database=db,
            status=Task.STATUS_PENDING,
        )
        for db in databases
    ]
    Task.objects.bulk_create(tasks)

    # Сформировать сообщение для очереди
    message = {
        'operation_id': str(batch_operation.id),
        'operation_type': operation_type,
        'target_databases': [
            {
                'id': str(db.id),
                'cluster_id': str(db.cluster_id),
                'infobase_id': str(db.infobase_id),  # UUID в RAS
                'name': db.name,
            }
            for db in databases
        ],
        'config': config,
        'execution_config': {
            'timeout_seconds': 60,
            'max_retries': 3,
        },
    }

    # Enqueue
    redis_client.lpush('cc1c:operations:v1', json.dumps(message))

    # Обновить статус
    batch_operation.status = BatchOperation.STATUS_QUEUED
    batch_operation.save(update_fields=['status'])

    return batch_operation
```

### 3. Go Worker — RAS Handler

```go
// go-services/worker/internal/processor/ras_handler.go

package processor

import (
    "context"
    "sync"

    "go-services/shared/models"
    "go-services/worker/internal/rasadapter"
)

type RASHandler struct {
    client *rasadapter.Client
}

func NewRASHandler(rasAdapterURL string) *RASHandler {
    return &RASHandler{
        client: rasadapter.NewClient(rasAdapterURL),
    }
}

func (h *RASHandler) Process(ctx context.Context, msg *models.OperationMessageV2) (*models.OperationResultV2, error) {
    results := make([]models.DatabaseResult, len(msg.TargetDatabases))
    var wg sync.WaitGroup
    var mu sync.Mutex

    for i, db := range msg.TargetDatabases {
        wg.Add(1)
        go func(idx int, database models.TargetDatabase) {
            defer wg.Done()

            var err error
            switch msg.OperationType {
            case "lock_scheduled_jobs":
                err = h.client.LockInfobase(ctx, database.ClusterID, database.InfobaseID)
            case "unlock_scheduled_jobs":
                err = h.client.UnlockInfobase(ctx, database.ClusterID, database.InfobaseID)
            case "block_sessions":
                err = h.client.BlockSessions(ctx, database.ClusterID, database.InfobaseID, msg.Config)
            case "unblock_sessions":
                err = h.client.UnblockSessions(ctx, database.ClusterID, database.InfobaseID)
            case "terminate_sessions":
                err = h.client.TerminateSessions(ctx, database.ClusterID, database.InfobaseID)
            }

            mu.Lock()
            results[idx] = models.DatabaseResult{
                DatabaseID: database.ID,
                Success:    err == nil,
                Error:      errorString(err),
            }
            mu.Unlock()
        }(i, db)
    }

    wg.Wait()

    // Подсчёт статистики
    succeeded := 0
    for _, r := range results {
        if r.Success {
            succeeded++
        }
    }

    return &models.OperationResultV2{
        OperationID: msg.OperationID,
        Status:      "completed",
        Results:     results,
        Summary: models.ResultSummary{
            Total:     len(results),
            Succeeded: succeeded,
            Failed:    len(results) - succeeded,
        },
    }, nil
}
```

### 4. Go Worker — RAS Adapter Client

```go
// go-services/worker/internal/rasadapter/client.go

package rasadapter

import (
    "context"
    "fmt"
    "net/http"
    "time"
)

type Client struct {
    baseURL    string
    httpClient *http.Client
}

func NewClient(baseURL string) *Client {
    return &Client{
        baseURL: baseURL,
        httpClient: &http.Client{
            Timeout: 30 * time.Second,
        },
    }
}

func (c *Client) LockInfobase(ctx context.Context, clusterID, infobaseID string) error {
    url := fmt.Sprintf("%s/api/v2/lock-infobase?cluster_id=%s&infobase_id=%s",
        c.baseURL, clusterID, infobaseID)
    return c.doPost(ctx, url, nil)
}

func (c *Client) UnlockInfobase(ctx context.Context, clusterID, infobaseID string) error {
    url := fmt.Sprintf("%s/api/v2/unlock-infobase?cluster_id=%s&infobase_id=%s",
        c.baseURL, clusterID, infobaseID)
    return c.doPost(ctx, url, nil)
}

func (c *Client) BlockSessions(ctx context.Context, clusterID, infobaseID string, config map[string]interface{}) error {
    url := fmt.Sprintf("%s/api/v2/block-sessions?cluster_id=%s&infobase_id=%s",
        c.baseURL, clusterID, infobaseID)
    return c.doPost(ctx, url, config)
}

func (c *Client) UnblockSessions(ctx context.Context, clusterID, infobaseID string) error {
    url := fmt.Sprintf("%s/api/v2/unblock-sessions?cluster_id=%s&infobase_id=%s",
        c.baseURL, clusterID, infobaseID)
    return c.doPost(ctx, url, nil)
}

func (c *Client) TerminateSessions(ctx context.Context, clusterID, infobaseID string) error {
    url := fmt.Sprintf("%s/api/v2/terminate-sessions?cluster_id=%s&infobase_id=%s",
        c.baseURL, clusterID, infobaseID)
    return c.doPost(ctx, url, nil)
}

func (c *Client) doPost(ctx context.Context, url string, body interface{}) error {
    // Implementation: create request, send, check response
    // ...
}
```

### 5. Frontend — DatabaseActionsMenu

```typescript
// frontend/src/components/actions/DatabaseActionsMenu.tsx

import React from 'react';
import { Dropdown, Button } from 'antd';
import type { MenuProps } from 'antd';
import {
  LockOutlined,
  UnlockOutlined,
  StopOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  HeartOutlined,
  MoreOutlined,
  EllipsisOutlined,
} from '@ant-design/icons';
import type { Database } from '@/api/generated/model';

export type DatabaseActionKey =
  | 'lock_scheduled_jobs'
  | 'unlock_scheduled_jobs'
  | 'block_sessions'
  | 'unblock_sessions'
  | 'terminate_sessions'
  | 'health_check'
  | 'more';

export interface DatabaseActionsMenuProps {
  database: Database;
  onAction: (action: DatabaseActionKey, database: Database) => void;
  disabled?: boolean;
}

const menuItems: MenuProps['items'] = [
  { key: 'lock_scheduled_jobs', icon: <LockOutlined />, label: 'Lock Scheduled Jobs' },
  { key: 'unlock_scheduled_jobs', icon: <UnlockOutlined />, label: 'Unlock Scheduled Jobs' },
  { type: 'divider' },
  { key: 'block_sessions', icon: <StopOutlined />, label: 'Block Sessions' },
  { key: 'unblock_sessions', icon: <CheckCircleOutlined />, label: 'Unblock Sessions' },
  {
    key: 'terminate_sessions',
    icon: <CloseCircleOutlined />,
    label: 'Terminate Sessions',
    danger: true,
  },
  { type: 'divider' },
  { key: 'health_check', icon: <HeartOutlined />, label: 'Health Check' },
  { type: 'divider' },
  { key: 'more', icon: <MoreOutlined />, label: 'More Operations...' },
];

export const DatabaseActionsMenu: React.FC<DatabaseActionsMenuProps> = ({
  database,
  onAction,
  disabled = false,
}) => {
  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    onAction(key as DatabaseActionKey, database);
  };

  return (
    <Dropdown
      menu={{ items: menuItems, onClick: handleMenuClick }}
      trigger={['click']}
      disabled={disabled || database.status !== 'active'}
    >
      <Button icon={<EllipsisOutlined />} size="small" />
    </Dropdown>
  );
};
```

### 6. Frontend — useDatabaseActions Hook

```typescript
// frontend/src/hooks/useDatabaseActions.ts

import { useState, useCallback } from 'react';
import { message } from 'antd';
import { executeOperation } from '@/api/operations';
import type { Database } from '@/api/generated/model';

export interface UseDatabaseActionsResult {
  execute: (
    operationType: string,
    databases: Database[],
    config?: Record<string, unknown>
  ) => Promise<string | null>;  // Returns operation_id
  loading: boolean;
  error: string | null;
}

export const useDatabaseActions = (): UseDatabaseActionsResult => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(
    async (
      operationType: string,
      databases: Database[],
      config?: Record<string, unknown>
    ): Promise<string | null> => {
      setLoading(true);
      setError(null);

      try {
        const response = await executeOperation({
          operation_type: operationType,
          database_ids: databases.map((db) => db.id!),
          config,
        });

        message.success(
          `${operationType} queued for ${databases.length} database(s)`
        );

        return response.operation_id;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Operation failed';
        setError(errorMsg);
        message.error(errorMsg);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { execute, loading, error };
};
```

---

## Оценка и риски

### Оценка времени

| Компонент | Время | Приоритет |
|-----------|-------|-----------|
| Backend: Orchestrator endpoint + service | 4-6 часов | 1 |
| Backend: Go Worker handler + RAS client | 4-6 часов | 2 |
| Frontend: Action компоненты | 4-6 часов | 3 |
| Frontend: Databases.tsx интеграция | 2-4 часа | 4 |
| Тестирование и отладка | 4-6 часов | 5 |
| **Итого** | **4-5 дней** | |

### Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| RAS Adapter недоступен | Low | High | Circuit breaker + retry с exponential backoff |
| Большое кол-во БД (>100) | Medium | Medium | Configurable parallelism (default: 10) |
| Длительные операции | Low | Medium | Timeout 60s + SSE для real-time updates |
| Partial failure handling | Medium | Low | Детальная статистика в UI |

### Зависимости

- ✅ Phase 1-3 завершены
- ✅ RAS Adapter REST API работает
- ✅ Redis Queue инфраструктура есть
- ✅ BatchOperation модель определена
- ⚠️ Нужно добавить `infobase_id` в Database модель (если ещё нет)

---

## Критерии готовности

### Phase 4.1 — Backend
- [ ] `POST /api/v2/operations/execute/` endpoint работает
- [ ] BatchOperation создаётся с правильным типом
- [ ] Tasks создаются для каждой БД
- [ ] Сообщение попадает в Redis Queue
- [ ] Worker обрабатывает RAS операции
- [ ] Результат публикуется в Redis
- [ ] BatchOperation обновляется после завершения

### Phase 4.2 — Frontend
- [ ] DatabaseActionsMenu показывает все операции
- [ ] BulkActionsToolbar появляется при выборе БД
- [ ] OperationConfirmModal показывает список БД
- [ ] Операция создаётся через API
- [ ] Прогресс отображается в Operations Center

### Phase 4.3 — Integration
- [ ] E2E: выбор БД → context menu → confirm → operation → progress
- [ ] Bulk: выбор 10 БД → bulk action → параллельное выполнение
- [ ] Error handling: partial failure отображается корректно

---

## Ссылки

- [FRONTEND_UNIFICATION_ROADMAP.md](./FRONTEND_UNIFICATION_ROADMAP.md) — родительский roadmap
- [EVENT_DRIVEN_ARCHITECTURE.md](../architecture/EVENT_DRIVEN_ARCHITECTURE.md) — архитектура событий
- [1C_ADMINISTRATION_GUIDE.md](../1C_ADMINISTRATION_GUIDE.md) — RAS операции

---

**Версия:** 1.0
**Автор:** AI Assistant
**Дата:** 2025-12-09
