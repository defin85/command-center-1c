# Track 2: Orchestrator ↔ Worker Integration

> **Git Worktree для параллельной разработки Track 2A + 2B**

**Дата создания:** 2025-11-09
**Ветка:** `feature/track2-orchestrator-worker-integration`
**Worktree:** `C:\1CProject\command-center-1c-track2`

---

## 📋 Обзор

Этот worktree объединяет **Track 2A** и **Track 2B**, так как они тесно связаны и требуют координации для согласования **Message Protocol**.

### Track 2A: Celery Producer (Django → Redis)
**Цель:** Реализовать producer side интеграции - Django/Celery отправляет задачи в Redis queue для Go Workers

**Компоненты:**
- Django Celery tasks
- Redis queue producer
- Message serialization
- Callback endpoint для приема результатов от Worker

### Track 2B: Go Worker Consumer (Redis → Worker)
**Цель:** Реализовать consumer side интеграции - Go Worker читает задачи из Redis queue и обрабатывает их

**Компоненты:**
- Redis queue consumer
- Message deserialization
- Worker pool integration
- Heartbeat mechanism

---

## 🎯 Цели Track 2

### Основные задачи

**Track 2A (Python Backend):**
- [ ] Реализовать `process_operation()` в Celery tasks
- [ ] Message Protocol Design (JSON schema)
- [ ] Callback endpoint `POST /api/v1/operations/{id}/callback`
- [ ] Progress tracking (update operation status)

**Track 2B (Go Backend):**
- [ ] Message Protocol Design (Go structs)
- [ ] Redis queue consumer (`queue/consumer.go`)
- [ ] Worker pool integration
- [ ] Heartbeat mechanism

**Общие задачи:**
- [ ] Согласовать Message Protocol (JSON schema + Go structs)
- [ ] Integration tests (Django → Redis → Worker → Callback)
- [ ] Documentation

---

## 📡 Message Protocol (КРИТИЧНО - требует sync!)

### JSON Schema (версия 1.0)

\`\`\`json
{
  "version": "1.0",
  "operation_id": "uuid",
  "template_id": "uuid",
  "operation_type": "create|update|delete",
  "target_databases": ["db_uuid1", "db_uuid2"],
  "payload": {
    "entity": "Catalog_Users",
    "data": {"Name": "Test User", ...}
  },
  "options": {
    "batch_size": 100,
    "retry_count": 3
  }
}
\`\`\`

### Go Structs (версия 1.0)

\`\`\`go
type OperationMessage struct {
    Version         string                 \`json:"version"\`
    OperationID     string                 \`json:"operation_id"\`
    TemplateID      string                 \`json:"template_id"\`
    OperationType   string                 \`json:"operation_type"\` // create|update|delete
    TargetDatabases []string               \`json:"target_databases"\`
    Payload         map[string]interface{} \`json:"payload"\`
    Options         OperationOptions       \`json:"options"\`
}

type OperationOptions struct {
    BatchSize  int \`json:"batch_size"\`
    RetryCount int \`json:"retry_count"\`
}
\`\`\`

**⚠️ ВАЖНО:** Этот протокол должен быть согласован между Python и Go разработчиками!

**Статус:** 🔴 НЕ СОГЛАСОВАН (требуется sync meeting)

---

## 📅 План работы

### Неделя 1

**День 1 (сегодня):**
- ✅ Создан worktree
- [ ] Kickoff sync meeting (Python + Go разработчики)
- [ ] Согласовать Message Protocol
- [ ] Документировать protocol в \`docs/MESSAGE_PROTOCOL.md\`

**День 2-5:** См. PARALLEL_WORK_PLAN.md

---

## 🚀 Быстрый старт

\`\`\`bash
# 1. Перейти в worktree
cd /c/1CProject/command-center-1c-track2

# 2. Проверить git status
git status

# 3. Запустить dev окружение
./scripts/dev/start-all.sh

# 4. Проверить Redis
docker exec -it redis redis-cli ping
\`\`\`

---

**Версия:** 1.0
**Дата:** 2025-11-09
**Следующий шаг:** Sync Meeting - Message Protocol Design
