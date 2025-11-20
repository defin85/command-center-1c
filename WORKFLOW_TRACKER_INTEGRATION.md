# Real-time Workflow Tracker - Интеграция

## 📦 Что реализовано

### ✅ Backend (Django)
1. **`orchestrator/apps/operations/events.py`** - EventPublisher для Redis PubSub
2. **`orchestrator/apps/operations/tasks.py`** - публикация события QUEUED
3. **`orchestrator/apps/operations/views.py`** - SSE endpoint `/api/v1/operations/{id}/stream`
4. **`orchestrator/apps/operations/urls.py`** - routing настроен

### ✅ Worker (Go)
1. **`go-services/worker/internal/events/publisher.go`** - EventPublisher с методами
2. **`go-services/worker/internal/processor/processor.go`** - интеграция EventPublisher (PROCESSING, SUCCESS, FAILED)
3. **`go-services/worker/internal/processor/extension_handler.go`** - события для установки расширений (UPLOADING, INSTALLING, VERIFYING)
4. **`go-services/worker/cmd/main.go`** - создание shared redis.Client
5. **`go-services/worker/internal/queue/consumer.go`** - использование shared redis.Client

### ✅ Frontend (React)
1. **`frontend/src/hooks/useOperationStream.ts`** - SSE hook
2. **`frontend/src/components/WorkflowTracker/index.tsx`** - React component
3. **`frontend/src/components/WorkflowTracker/styles.css`** - стили
4. **`frontend/src/pages/OperationMonitor/index.tsx`** - отдельная страница мониторинга
5. **`frontend/src/App.tsx`** - добавлен route `/operation-monitor`
6. **`frontend/src/components/layout/MainLayout.tsx`** - добавлен пункт меню
7. **ReactFlow** установлен (`npm install reactflow`)

---

## 🔧 Как использовать в Frontend

### Вариант 1: В существующей странице

```typescript
import { WorkflowTracker } from '@/components/WorkflowTracker'
import { useOperationStream } from '@/hooks/useOperationStream'
import { Card } from 'antd'

export const YourPage = () => {
  const [operationId, setOperationId] = useState<string | null>(null)

  // Подключиться к SSE stream
  const { events, currentState, error, isConnected } = useOperationStream(operationId)

  return (
    <div>
      {/* Ваша форма для запуска операции */}
      <Button onClick={async () => {
        const response = await api.post('/operations', {...})
        setOperationId(response.data.id)  // Сохранить operation_id
      }}>
        Запустить операцию
      </Button>

      {/* WorkflowTracker */}
      {operationId && (
        <Card title="Прогресс операции" style={{ marginTop: 24 }}>
          <WorkflowTracker
            events={events}
            currentState={currentState}
            error={error}
            isConnected={isConnected}
          />
        </Card>
      )}
    </div>
  )
}
```

### Вариант 2: Отдельная страница мониторинга ✅ РЕАЛИЗОВАНО

**Страница уже создана и доступна по адресу:** http://localhost:5173/operation-monitor

**Возможности:**
- Input для ввода Operation ID
- Кнопка "Подключиться" / "Отключиться"
- Alert с информацией о подключении
- WorkflowTracker с визуализацией
- Справка по использованию

**Как использовать:**
1. Запустите Frontend: `cd frontend && npm run dev`
2. Откройте http://localhost:5173/operation-monitor
3. Введите Operation ID (UUID) операции
4. Нажмите "Подключиться"
5. Наблюдайте workflow в real-time!

**Навигация:**
Пункт меню "Operation Monitor" (иконка 👁️) добавлен в левое меню приложения

---

## 🧪 Тестирование

### 1. Тест SSE endpoint (Backend)

```bash
# Проверить что SSE endpoint работает
curl -N http://localhost:8000/api/v1/operations/{OPERATION_ID}/stream

# Ожидается:
# data: {"state":"QUEUED","microservice":"orchestrator",...}
```

### 2. Тест Redis PubSub (Manual)

```bash
# Подключиться к Redis
docker exec -it redis redis-cli

# Подписаться на события операции
SUBSCRIBE operation:{OPERATION_ID}:events

# В другом терминале опубликовать тестовое событие
docker exec -it redis redis-cli
PUBLISH operation:{OPERATION_ID}:events '{"state":"PROCESSING","message":"test"}'
```

### 3. Тест Frontend

1. Запустить Frontend: `cd frontend && npm run dev`
2. Открыть страницу с WorkflowTracker
3. Запустить операцию установки расширения
4. Проверить что:
   - SSE подключение установлено (isConnected = true)
   - События появляются в timeline
   - ReactFlow визуализация обновляется
   - Анимация переходов работает

---

## 🎯 State Machine Flow

```
PENDING (создано в Orchestrator)
  ↓ enqueue_operation()
QUEUED (отправлено в Redis queue)  ← ✅ Реализовано в tasks.py
  ↓ Worker.Poll()
PROCESSING (Worker взял в работу)  ← ✅ Реализовано в processor.go
  ↓
  ├─→ UPLOADING (загрузка .cfe)  ← ✅ Реализовано в extension_handler.go
  ├─→ INSTALLING (установка)     ← ✅ Реализовано в extension_handler.go
  ├─→ VERIFYING (проверка)       ← ✅ Реализовано в extension_handler.go
  ↓
SUCCESS / FAILED / TIMEOUT        ← ✅ Реализовано в processor.go
```

---

## 📊 Event Schema

```json
{
  "version": "1.0",
  "operation_id": "uuid",
  "timestamp": "2025-11-19T10:30:00Z",
  "state": "PROCESSING",
  "microservice": "worker",
  "message": "Обработка базы 'УправлениеПроизводством'",
  "metadata": {
    "database_id": "uuid",
    "worker_id": "worker-001",
    "progress_percentage": 45
  }
}
```

---

## 🚀 Тестирование End-to-End

### Шаг 1: Запустить все сервисы

```bash
# Перезапустить Worker с новым кодом
./scripts/dev/restart.sh worker

# Проверить что все сервисы работают
./scripts/dev/health-check.sh

# Запустить Frontend (если не запущен)
cd frontend && npm run dev
```

### Шаг 2: Открыть страницу мониторинга

1. Откройте http://localhost:5173/operation-monitor
2. Вы увидите страницу с input полем для Operation ID

### Шаг 3: Запустить тестовую операцию

**Вариант A: Через Frontend (если есть страница установки расширений)**
1. Откройте страницу установки расширений
2. Запустите установку
3. Скопируйте Operation ID из ответа

**Вариант B: Через API напрямую**
```bash
# Пример запроса для создания операции
curl -X POST http://localhost:8000/api/v1/operations/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "operation_type": "install_extension",
    "target_databases": ["database-id-1"],
    "payload": {
      "data": {
        "extension_name": "TestExtension",
        "extension_path": "/path/to/extension.cfe"
      }
    }
  }'

# Скопируйте operation_id из ответа
```

### Шаг 4: Подключиться к мониторингу

1. Вставьте скопированный Operation ID в input поле
2. Нажмите "Подключиться"
3. Вы увидите:
   - ✅ Alert "Подключено к операции"
   - ✅ Real-time обновления активны
   - ✅ ReactFlow диаграмма с состояниями
   - ✅ Timeline с событиями

### Шаг 5: Наблюдать workflow

Вы должны увидеть последовательность состояний:
1. **QUEUED** - операция поставлена в очередь (Orchestrator)
2. **PROCESSING** - Worker начал обработку (Worker)
3. **UPLOADING** - подготовка к установке (Worker)
4. **INSTALLING** - фактическая установка (Worker)
5. **VERIFYING** - проверка результата (Worker)
6. **SUCCESS** - успешное завершение (Worker)

### Шаг 6: Проверить детали (опционально)

**Проверить SSE stream напрямую:**
```bash
curl -N http://localhost:8000/api/v1/operations/{OPERATION_ID}/stream
```

**Проверить Redis PubSub:**
```bash
docker exec -it redis redis-cli
SUBSCRIBE operation:{OPERATION_ID}:events
```

**Проверить логи Worker:**
```bash
./scripts/dev/logs.sh worker | grep "PublishProcessing\|PublishUploading\|PublishInstalling"
```

---

## 🎯 Следующие улучшения (опционально)

1. **Интеграция в существующие страницы** - добавить WorkflowTracker в InstallExtension, Operations List
2. **Progress percentage** - показывать процент выполнения каждого шага
3. **Estimated time remaining** - прогноз времени завершения
4. **Retry/Cancel кнопки** - возможность повторить или отменить операцию
5. **Export timeline** - экспорт хронологии в JSON/CSV
6. **Звуковые уведомления** - при завершении операции
7. **Desktop notifications** - браузерные уведомления

---

## ❓ Troubleshooting

### SSE не подключается

```bash
# Проверить что Orchestrator работает
curl http://localhost:8000/health

# Проверить что Redis работает
docker exec -it redis redis-cli ping
```

### События не приходят

```bash
# Проверить логи Orchestrator
./scripts/dev/logs.sh orchestrator | grep "SSE"

# Проверить что events.py работает
# В Django shell:
python manage.py shell
>>> from apps.operations.events import event_publisher
>>> event_publisher.publish("test-id", "QUEUED", "test")
```

### Frontend ошибки

```bash
# Проверить что ReactFlow установлен
cd frontend
npm list reactflow

# Если нет:
npm install reactflow
```

---

**✅ Реализация завершена на 100%!**

Все компоненты интегрированы:
- ✅ Backend (Django) - SSE endpoint + EventPublisher
- ✅ Worker (Go) - EventPublisher интегрирован в processor.go и extension_handler.go
- ✅ Frontend (React) - WorkflowTracker component + useOperationStream hook

Готово к end-to-end тестированию!
