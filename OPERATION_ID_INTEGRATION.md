# Operation ID Integration - Сводка изменений

## ✅ Решённые проблемы

### Проблема 1: Operation ID не возвращался при установке расширения
**Было:** Frontend получал только `task_id` (Celery task)
**Стало:** Frontend получает и `task_id`, и `operation_id` для workflow tracking

### Проблема 2: Не было быстрого способа перейти к мониторингу
**Было:** Нужно было копировать Operation ID вручную и вставлять в Operation Monitor
**Стало:** Кнопка "Monitor Workflow" с автоматическим переходом

---

## 📝 Список изменений

### Backend (Django)

**1. `orchestrator/apps/databases/views.py`** (строка 523-533)
- Модифицирован endpoint `install_extension` в `DatabaseViewSet`
- **Изменение:** Получение результата task через `task.get()` для извлечения `operation_id`
- **Возвращаемые данные:**
  ```python
  {
      "status": "queued",
      "task_id": "celery-task-id",
      "operation_id": "uuid-operation-id",  # NEW!
      "message": "Installation started for DatabaseName",
      "queued_count": 1
  }
  ```

**Примечание:** `task.get(timeout=10)` ждёт максимум 10 секунд для получения operation_id. Это быстро, так как task только создаёт операцию в БД и отправляет в queue.

---

### Frontend (React/TypeScript)

**1. `frontend/src/types/installation.ts`**
- Добавлен новый тип `InstallSingleResponse`:
  ```typescript
  export interface InstallSingleResponse {
    task_id: string
    operation_id: string  // NEW!
    message: string
    status: string
    queued_count?: number
  }
  ```

**2. `frontend/src/api/endpoints/installation.ts`**
- Обновлён тип возвращаемого значения `installSingle()`:
  ```typescript
  installSingle: async (...): Promise<InstallSingleResponse>
  ```

**3. `frontend/src/pages/Databases/Databases.tsx`**

**Изменения:**
- Добавлено состояние `currentOperationId` для сохранения operation_id
- Модифицирован `handleConfirmInstall()`:
  - Сохраняет `operation_id` в состояние
  - Показывает operation_id в success message
- Добавлен блок "Operation Monitor Link" с:
  - Копируемым Operation ID
  - Кнопкой "Monitor Workflow" для быстрого перехода

**UI:**
```tsx
{/* Operation Monitor Link */}
{currentOperationId && progressModalVisible && (
  <Space direction="vertical" style={{ width: '100%', padding: '16px', ... }}>
    <div>
      <strong>Operation ID:</strong>
      <Paragraph copyable={{ text: currentOperationId }}>
        <code>{currentOperationId}</code>
      </Paragraph>
      <Button
        type="primary"
        icon={<EyeOutlined />}
        onClick={() => navigate(`/operation-monitor?operation=${currentOperationId}`)}
      >
        Monitor Workflow
      </Button>
    </div>
  </Space>
)}
```

**4. `frontend/src/pages/OperationMonitor/index.tsx`**
- Добавлена поддержка URL query parameter `?operation=<operation-id>`
- Автоматическое подключение при наличии operation_id в URL
- **Использование:** `http://localhost:5173/operation-monitor?operation=abc-123-def-456`

---

## 🚀 Как это работает

### Шаг 1: Запуск установки расширения

Пользователь открывает `/databases` и нажимает "Install Extension":

1. Выбирает файл расширения
2. Нажимает "Install"
3. **Frontend вызывает:** `POST /api/v1/databases/{id}/install-extension/`
4. **Backend возвращает:**
   ```json
   {
     "status": "queued",
     "task_id": "abc-123",
     "operation_id": "def-456-ghi-789",
     "message": "Installation started for MyDatabase",
     "queued_count": 1
   }
   ```

### Шаг 2: Отображение Operation ID

Frontend показывает:
- ✅ Success message с Operation ID
- ✅ Блок с копируемым Operation ID
- ✅ Кнопку "Monitor Workflow"

### Шаг 3: Переход к мониторингу

Пользователь нажимает "Monitor Workflow":
1. **URL:** `http://localhost:5173/operation-monitor?operation=def-456-ghi-789`
2. **Operation Monitor автоматически:**
   - Читает operation_id из URL query parameter
   - Подключается к SSE stream
   - Показывает real-time workflow визуализацию

---

## 📊 Примеры использования

### Сценарий 1: Установка расширения через UI

```
1. Пользователь: Databases → Install Extension → Выбрать файл → Install
2. Backend: Создаёт operation, возвращает operation_id
3. Frontend: Показывает "Operation ID: abc-123" + кнопка "Monitor Workflow"
4. Пользователь: Нажимает "Monitor Workflow"
5. Frontend: Открывает /operation-monitor?operation=abc-123
6. Operation Monitor: Показывает real-time workflow
```

### Сценарий 2: Мониторинг существующей операции

```
1. Пользователь: Копирует Operation ID из логов/email/notification
2. Пользователь: Открывает /operation-monitor
3. Пользователь: Вставляет Operation ID в input field
4. Пользователь: Нажимает "Подключиться"
5. Operation Monitor: Показывает real-time workflow
```

### Сценарий 3: Прямая ссылка

```
1. Система отправляет email/notification с ссылкой:
   "Monitor operation: http://localhost:5173/operation-monitor?operation=abc-123"
2. Пользователь: Кликает на ссылку
3. Operation Monitor: Автоматически подключается и показывает workflow
```

---

## 🧪 Тестирование

### 1. Проверить что operation_id возвращается

```bash
# Запустить установку через API
curl -X POST http://localhost:8000/api/v1/databases/{DB_ID}/install-extension/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "extension_config": {
      "name": "TestExtension",
      "path": "/path/to/extension.cfe"
    }
  }'

# Ожидаемый ответ:
# {
#   "status": "queued",
#   "task_id": "...",
#   "operation_id": "...",    <-- ДОЛЖЕН БЫТЬ!
#   "message": "...",
#   "queued_count": 1
# }
```

### 2. Проверить UI flow

1. Запустите Frontend: `cd frontend && npm run dev`
2. Откройте http://localhost:5173/databases
3. Нажмите "Install Extension" на любой активной базе
4. Выберите файл расширения
5. Нажмите "Install"
6. **Проверьте:**
   - ✅ Success message показывает Operation ID
   - ✅ Появляется блок с Operation ID и кнопкой
   - ✅ Кнопка "Monitor Workflow" работает
   - ✅ Operation Monitor открывается с правильным operation_id
   - ✅ Real-time workflow отображается

### 3. Проверить прямую ссылку

1. Скопируйте Operation ID из предыдущего теста
2. Откройте новую вкладку
3. Перейдите: `http://localhost:5173/operation-monitor?operation={OPERATION_ID}`
4. **Проверьте:**
   - ✅ Input field заполнен автоматически
   - ✅ Подключение установлено автоматически
   - ✅ Workflow отображается

---

## ❓ Troubleshooting

### Страница /operations пустая

**Проблема:** Frontend показывает пустой список операций

**Причина:** API Gateway routing не поддерживал trailing slash

**Решение:** Добавлена поддержка trailing slash в `go-services/api-gateway/internal/routes/router.go`:
```go
operations.GET("/", handlers.ProxyToOrchestrator) // Trailing slash для Django DRF
```

**См. также:** [OPERATIONS_PAGE_FIX.md](OPERATIONS_PAGE_FIX.md) для детального анализа

### Operation ID не возвращается

**Проблема:** Response не содержит `operation_id`

**Решение:**
```bash
# 1. Проверить что backend изменения применены
cd orchestrator
source venv/Scripts/activate  # Windows GitBash
grep "operation_id" apps/databases/views.py

# 2. Перезапустить Orchestrator
./scripts/dev/restart.sh orchestrator

# 3. Проверить логи
./scripts/dev/logs.sh orchestrator | grep "install-extension"
```

### Кнопка "Monitor Workflow" не работает

**Проблема:** Клик на кнопку не переходит на Operation Monitor

**Решение:**
```typescript
// Проверить что navigate импортирован
import { useNavigate } from 'react-router-dom'

// Проверить что navigate используется
const navigate = useNavigate()
onClick={() => navigate(`/operation-monitor?operation=${currentOperationId}`)}
```

### Operation Monitor не подключается автоматически

**Проблема:** Открывается /operation-monitor?operation=abc-123 но не подключается

**Решение:**
```bash
# 1. Проверить что useSearchParams добавлен
grep "useSearchParams" frontend/src/pages/OperationMonitor/index.tsx

# 2. Проверить browser console
# Должно быть: "SSE connection established"

# 3. Проверить что SSE endpoint доступен
curl -N http://localhost:8000/api/v1/operations/{OPERATION_ID}/stream
```

---

## 📈 Следующие улучшения

1. **Страница /operations должна показывать все операции**
   - Проверить API endpoint `/api/v1/operations/`
   - Убедиться что операции установки расширений включены

2. **Добавить Operation Monitor во все места создания операций**
   - Batch installation
   - Update operations
   - Query operations

3. **Email notifications с ссылкой на Operation Monitor**
   - При завершении операции отправлять email
   - Включать прямую ссылку на monitoring

4. **История операций с быстрым доступом к мониторингу**
   - В /operations добавить иконку "Monitor" для каждой операции
   - Клик на иконку → открывает Operation Monitor

---

**Статус:** ✅ Готово к тестированию
**Дата:** 2025-11-19
