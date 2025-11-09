# Message Protocol - Orchestrator ↔ Worker

**Версия:** 1.0 (DRAFT) - SUPERSEDED
**Дата:** 2025-11-09
**Статус:** 🔴 УСТАРЕЛ

⚠️ **ЭТОТ ДОКУМЕНТ УСТАРЕЛ**

Финализированная версия: **[MESSAGE_PROTOCOL_FINALIZED.md](MESSAGE_PROTOCOL_FINALIZED.md)**

---

## ⚠️ ВАЖНО

Используйте **MESSAGE_PROTOCOL_FINALIZED.md v2.0** для реализации!

Все open questions решены, все решения утверждены.

---

## Архивная информация (DRAFT v1.0)

---

## 📡 Message Format

### JSON Schema

```json
{
  "version": "1.0",
  "operation_id": "uuid",
  "template_id": "uuid",
  "operation_type": "create|update|delete",
  "target_databases": ["db_uuid1", "db_uuid2"],
  "payload": {
    "entity": "Catalog_Users",
    "data": {"Name": "Test User"}
  },
  "options": {
    "batch_size": 100,
    "retry_count": 3
  }
}
```

### Go Structs

```go
type OperationMessage struct {
    Version         string                 `json:"version"`
    OperationID     string                 `json:"operation_id"`
    TemplateID      string                 `json:"template_id"`
    OperationType   string                 `json:"operation_type"`
    TargetDatabases []string               `json:"target_databases"`
    Payload         OperationPayload       `json:"payload"`
    Options         OperationOptions       `json:"options"`
}
```

---

## 🐍 Python Producer

```python
@shared_task
def process_operation(operation_id: str):
    message = {
        "version": "1.0",
        "operation_id": str(operation.id),
        "template_id": str(operation.template.id),
        "operation_type": operation.operation_type,
        "target_databases": [str(db.id) for db in operation.target_databases.all()],
        "payload": {
            "entity": operation.template.entity_name,
            "data": operation.payload_data,
        },
        "options": {
            "batch_size": operation.batch_size or 100,
            "retry_count": operation.retry_count or 3,
        }
    }
    
    redis_client.rpush("operations:queue", json.dumps(message))
```

---

## 🔷 Go Consumer

```go
func (c *Consumer) Start(ctx context.Context) error {
    for {
        result, err := c.redisClient.BLPop(ctx, 5*time.Second, "operations:queue").Result()
        if err != nil {
            continue
        }
        
        var msg OperationMessage
        json.Unmarshal([]byte(result[1]), &msg)
        
        c.processMessage(ctx, &msg)
    }
}
```

---

## 🔄 Callback Protocol

### Go → Django Callback

```go
type CallbackPayload struct {
    Status  string           `json:"status"` // completed|failed
    Results []DatabaseResult `json:"results"`
}

// POST /api/v1/operations/{operation_id}/callback
```

### Django Handler

```python
@api_view(['POST'])
def operation_callback(request, operation_id):
    operation = Operation.objects.get(id=operation_id)
    operation.status = request.data.get('status')
    operation.results = request.data.get('results')
    operation.save()
    return Response({"status": "ok"})
```

---

## 🚧 Open Questions

- [ ] Queue naming: `operations:queue` или `cc1c:operations`?
- [ ] Redis data structure: List vs Stream?
- [ ] Credential management: Где хранить 1C credentials?
- [ ] Timeout handling: Что делать если Worker не отвечает?
- [ ] Dead Letter Queue format?

---

**Next Step:** Sync Meeting - согласовать protocol
