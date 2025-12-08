# Roadmap: V2 Migration и Синхронизация кластеров

> **Дата создания:** 2025-12-08
> **Статус:** Draft
> **Приоритет:** High

---

## Executive Summary

| Задача | Сложность | Время | Риск |
|--------|-----------|-------|------|
| Удаление v1 endpoints | **Medium** | 2-3 дня | Low |
| Синхронизация кластеров | **High** | 5-7 дней | Medium |

---

## ЗАДАЧА 1: Удаление v1 endpoints

### Текущее состояние

| Компонент | Статус v1 |
|-----------|-----------|
| API Gateway (Go) | ✅ **Удалены** (2025-11-27) |
| RAS Adapter (Go) | ✅ **Удалены** |
| Django Orchestrator | ❌ **Активны** (37 endpoints) |
| Frontend | ❌ **Прямые вызовы v1** (5 мест) |

### Django v1 endpoints для удаления

**config/urls.py (строки 31-34):**
```python
path('api/v1/', include('apps.databases.urls')),           # ~15 endpoints
path('api/v1/operations/', include('apps.operations.urls')),  # ~8 endpoints
path('api/v1/templates/', include('apps.templates.urls')),    # ~12 endpoints
path('api/v1/system/', include('apps.monitoring.urls')),      # 2 endpoints
```

### Frontend v1 вызовы

| Файл | Строка | Endpoint | Действие |
|------|--------|----------|----------|
| `useOperationStream.ts` | 44 | `/api/v1/operations/{id}/stream` | SSE - оставить или proxy |
| `extensionStorage.ts` | 23 | `/api/v1/extensions/storage/` | Создать v2 |
| `extensionStorage.ts` | 41 | `/api/v1/extensions/upload/` | Создать v2 |
| `extensionStorage.ts` | 52 | `/api/v1/extensions/storage/{filename}/` | Создать v2 |

### План выполнения

#### Phase 1: Добавить недостающие v2 endpoints (1 день)

**Создать `orchestrator/apps/api_v2/views/extensions.py`:**
```python
@api_view(['GET'])
def list_extension_storage(request):
    """GET /api/v2/extensions/list-storage/"""
    ...

@api_view(['POST'])
def upload_extension(request):
    """POST /api/v2/extensions/upload-extension/"""
    ...

@api_view(['DELETE'])
def delete_extension(request):
    """DELETE /api/v2/extensions/delete-extension/?filename=X"""
    ...
```

#### Phase 2: Мигрировать Frontend (1 день)

1. Обновить `extensionStorage.ts` на v2 endpoints
2. Решить вопрос с SSE stream (proxy через API Gateway или исключение)
3. Регенерировать `frontend/src/api/generated/`

#### Phase 3: Удалить v1 routes (0.5 дня)

```python
# orchestrator/config/urls.py - УДАЛИТЬ ВСЕ v1 пути
```

### Файлы для изменения

| Файл | Действие |
|------|----------|
| `orchestrator/apps/api_v2/views/extensions.py` | CREATE |
| `orchestrator/apps/api_v2/urls.py` | MODIFY |
| `frontend/src/api/extensionStorage.ts` | MODIFY |
| `orchestrator/config/urls.py` | MODIFY (удалить v1) |

---

## ЗАДАЧА 2: Синхронизация кластеров (Discover Clusters)

### Концепция

**Текущее ограничение:** Кластеры создаются вручную. Пользователь должен знать RAS адрес и имя кластера.

**Цель:** Автоматическое обнаружение ВСЕХ кластеров на RAS сервере и их синхронизация в Django БД.

### Новый flow

```
Frontend [Discover Clusters]
  │ POST /api/v2/clusters/discover-clusters/
  │ Body: { "ras_server": "localhost:1545" }
  ▼
API Gateway → Orchestrator
  │ 1. Создает BatchOperation (type=discover_clusters)
  │ 2. Публикует в Redis Queue
  ▼
Go Worker
  │ processDiscoverClusters():
  │ 1. rasClient.ListClusters(ctx, ras_server)
  │ 2. Публикует в Redis Stream "events:worker:clusters-discovered"
  ▼
Event Subscriber (Django)
  │ handle_clusters_discovered():
  │ 1. Для каждого cluster → create или update Cluster
  ▼
PostgreSQL
```

### Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────────────┐
│                       FRONTEND (React)                          │
│  Clusters.tsx                                                   │
│  ├── [Discover Clusters] → DiscoverClustersModal (NEW)          │
│  ├── [Add Cluster] (manual)                                     │
│  └── [Sync] per cluster                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ POST /api/v2/clusters/discover-clusters/
┌─────────────────────────────────────────────────────────────────┐
│                   API GATEWAY (Go:8180)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ORCHESTRATOR (Django:8200)                      │
│  views/clusters.py                                              │
│  └── discover_clusters() → BatchOperation + Redis enqueue       │
│                                                                 │
│  event_subscriber.py                                            │
│  └── handle_clusters_discovered() → Cluster.objects.create()    │
└─────────────────────────────────────────────────────────────────┘
        │                                          ▲
        │ XADD tasks:operations                    │ XREAD
        ▼                                          │
┌─────────────────────────────────────────────────────────────────┐
│                       REDIS (6379)                              │
│  ├── Stream: tasks:operations                                   │
│  └── Stream: events:worker:clusters-discovered (NEW)            │
└─────────────────────────────────────────────────────────────────┘
        │                                          ▲
        ▼                                          │ XADD
┌─────────────────────────────────────────────────────────────────┐
│                      GO WORKER                                  │
│  processor/discover_clusters.go (NEW)                           │
│  └── processDiscoverClusters()                                  │
│      ├── rasClient.ListClusters()                               │
│      └── publishDiscoverClustersResult()                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP /api/v2/list-clusters
┌─────────────────────────────────────────────────────────────────┐
│                  RAS ADAPTER (Go:8188)                          │
│  └── ListClusters() → RAS Protocol → 1C                         │
└─────────────────────────────────────────────────────────────────┘
```

### Файлы для создания/изменения

| Файл | Действие | Описание |
|------|----------|----------|
| `go-services/worker/internal/processor/discover_clusters.go` | **CREATE** | Новый handler |
| `go-services/worker/internal/processor/processor.go` | MODIFY | Добавить case |
| `orchestrator/apps/api_v2/views/clusters.py` | MODIFY | Добавить endpoint |
| `orchestrator/apps/api_v2/urls.py` | MODIFY | Добавить path |
| `orchestrator/apps/operations/event_subscriber.py` | MODIFY | Добавить handler |
| `orchestrator/apps/operations/models/batch_operation.py` | MODIFY | Добавить TYPE |
| `frontend/src/pages/Clusters/DiscoverClustersModal.tsx` | **CREATE** | UI компонент |
| `frontend/src/pages/Clusters/Clusters.tsx` | MODIFY | Добавить кнопку |

### Go Worker Handler

```go
// go-services/worker/internal/processor/discover_clusters.go

type DiscoverClustersPayload struct {
    RASServer   string `json:"ras_server"`
    ClusterUser string `json:"cluster_user,omitempty"`
    ClusterPwd  string `json:"cluster_pwd,omitempty"`
}

type DiscoverClustersResult struct {
    OperationID string                   `json:"operation_id"`
    RASServer   string                   `json:"ras_server"`
    Clusters    []map[string]interface{} `json:"clusters"`
    Success     bool                     `json:"success"`
    Error       string                   `json:"error,omitempty"`
}

func (p *TaskProcessor) processDiscoverClusters(ctx context.Context, msg *models.OperationMessage) *models.OperationResultV2 {
    // 1. Parse payload
    // 2. Call RAS Adapter: GET /api/v2/list-clusters?server=X
    // 3. Publish to Redis Stream: "events:worker:clusters-discovered"
    // 4. Return success result
}
```

### Django Event Handler

```python
# orchestrator/apps/operations/event_subscriber.py

STREAM_HANDLERS = {
    ...
    'events:worker:clusters-discovered': 'handle_clusters_discovered',
}

def handle_clusters_discovered(self, payload: dict, correlation_id: str):
    from apps.databases.models import Cluster

    ras_server = payload.get('ras_server')
    clusters_data = payload.get('clusters', [])

    created = updated = 0
    for cluster_data in clusters_data:
        cluster_uuid = cluster_data.get('uuid')

        cluster, is_new = Cluster.objects.update_or_create(
            ras_cluster_uuid=cluster_uuid,
            defaults={
                'name': cluster_data.get('name'),
                'ras_server': ras_server,
                'metadata': cluster_data,
                'status': Cluster.STATUS_ACTIVE,
            }
        )
        if is_new:
            created += 1
        else:
            updated += 1

    logger.info(f"Clusters discovered: created={created}, updated={updated}")
```

### Frontend Component

```tsx
// frontend/src/pages/Clusters/DiscoverClustersModal.tsx

export const DiscoverClustersModal = ({ visible, onClose, onSuccess }) => {
    const [form] = Form.useForm();

    const handleDiscover = async () => {
        const values = await form.validateFields();
        const result = await api.postClustersDiscoverClusters(values);
        message.success(`Discovery started: ${result.operation_id}`);
        onSuccess();
    };

    return (
        <Modal title="Discover Clusters" open={visible} onOk={handleDiscover}>
            <Form form={form} layout="vertical">
                <Form.Item label="RAS Server" name="ras_server" rules={[{ required: true }]}>
                    <Input placeholder="localhost:1545" />
                </Form.Item>
            </Form>
        </Modal>
    );
};
```

---

## Timeline

```
Week 1:
├── Day 1-2: Задача 1 (v2 extension endpoints + frontend)
├── Day 3:   Задача 1 (удаление v1 routes)
├── Day 4-5: Задача 2 (Go Worker + Django handlers)

Week 2:
├── Day 1-2: Задача 2 (Frontend UI)
├── Day 3:   Code Review + Bug fixes
├── Day 4-5: E2E тестирование
```

---

## Риски

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Сломается Frontend при удалении v1 | Medium | Полное тестирование перед удалением |
| Дубликаты кластеров при discover | Medium | Unique constraint на ras_cluster_uuid |
| RAS Adapter недоступен | Low | Fallback к ручному созданию |

---

## Checklist

### Задача 1: Удаление v1

- [x] Создать v2 endpoints для extensions
- [x] Мигрировать Frontend на v2
- [x] Удалить v1 routes из Django
- [ ] Тестирование всех страниц

### Задача 2: Discover Clusters

- [x] Go Worker: discover_clusters.go
- [x] Django: endpoint + event handler
- [x] Event Subscriber: новый stream handler
- [x] Frontend: DiscoverClustersModal
- [ ] Интеграционные тесты
- [ ] E2E тесты
