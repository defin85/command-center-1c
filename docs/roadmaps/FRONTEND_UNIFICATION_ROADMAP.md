# Frontend Unification Roadmap

> Унификация UI компонентов и единая система запуска операций CommandCenter1C

**Дата создания:** 2025-12-09
**Статус:** In Progress (Phase 3 Complete)
**Приоритет:** Medium
**Оценка:** 4-5 недель
**Прогресс:** Phase 1-3 завершены (2025-12-09)

---

## Содержание

1. [Проблемы текущего состояния](#проблемы-текущего-состояния)
2. [Архитектура единой системы операций](#архитектура-единой-системы-операций)
3. [Phase 1: Quick Fixes](#phase-1-quick-fixes-1-2-дня)
4. [Phase 2: Unified Operations Center](#phase-2-unified-operations-center-1-неделя)
5. [Phase 3: Удаление дублей](#phase-3-удаление-дублей-3-5-дней)
6. [Phase 4: Context Menu Actions](#phase-4-context-menu-actions-1-неделя)
7. [Phase 5: Custom Operations & Templates](#phase-5-custom-operations--templates-1-2-недели)
8. [Phase 6: Dashboard Improvements](#phase-6-dashboard-improvements-опционально)

---

## Проблемы текущего состояния

### 1. ~~Несогласованность форм~~ ✅ FIXED (Phase 1)

| Форма | RAS Server | Cluster Service URL |
|-------|------------|---------------------|
| Add New Cluster | ✅ | ✅ |
| Discover Clusters | ✅ | ✅ |

### 2. ~~Дублирование страниц операций~~ ✅ FIXED (Phase 2)

```
/operations           - Unified Operations Center (табы: List + Live Monitor)
/operation-monitor    - ✅ Редирект на /operations?tab=monitor
/installation-monitor - ✅ Редирект на /operations?tab=list
/service-mesh         - ✅ Использует unified navigation
```

### 3. ~~Выявленные баги~~ ✅ FIXED (Phase 1-2)

- ~~**URL parameter inconsistency:** `/service-mesh` использует `?id=` вместо `?operation=`~~ ✅ Fixed
- **Dashboard пустой:** нет real-time метрик и виджетов (Phase 6)
- ~~**Polling vs SSE:** `/installation-monitor` использует polling вместо SSE~~ ✅ Fixed (unified в /operations)

### 4. ~~Разрозненные точки запуска операций~~ ✅ FIXED (Phase 2)

| Место | Операция | Статус |
|-------|----------|--------|
| `/operations` | **New Operation Wizard** | ✅ Единая точка входа |
| `/databases` | Install Extension | Кнопка на каждой строке |
| `/clusters` | Sync Cluster | Кнопка на строке |
| `/clusters` | Discover Clusters | Отдельная модалка |
| `/workflows` | Execute Workflow | Отдельная страница |

**✅ Создан New Operation Wizard - единая точка запуска всех типов операций.**

---

## Архитектура единой системы операций

### Концепция: Operations Center

```
┌─────────────────────────────────────────────────────────────────┐
│                     OPERATIONS CENTER                            │
│  /operations                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ + New        │  │ Operations   │  │ Live Monitor │           │
│  │   Operation  │  │ List (Table) │  │ (SSE Stream) │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              NEW OPERATION WIZARD                         │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Step 1: Select Operation Type                             │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │   │
│  │  │  RAS    │ │  OData  │ │ Backup  │ │ Health  │         │   │
│  │  │Operations│ │Operations│ │ Restore │ │  Check  │         │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │   │
│  │  ┌─────────┐ ┌─────────┐                                  │   │
│  │  │Workflow │ │ Custom  │                                  │   │
│  │  │(Template)│ │(Advanced)│                                  │   │
│  │  └─────────┘ └─────────┘                                  │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Step 2: Select Target (DBs / Clusters)                    │   │
│  │  □ Select manually  ○ By filter  ○ All in cluster         │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Step 3: Configure Parameters                              │   │
│  │  [Dynamic form based on operation type]                   │   │
│  │  - File upload (extensions, data files)                   │   │
│  │  - Key-value inputs                                       │   │
│  │  - JSON editor (advanced)                                 │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Step 4: Review & Execute                                  │   │
│  │  [Summary] [Execute] [Schedule for later]                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Поддерживаемые типы операций

#### RAS Operations (через ras-adapter)
| Операция | Описание | Параметры |
|----------|----------|-----------|
| `lock_scheduled_jobs` | Заблокировать регламентные задания | cluster_id, database_ids |
| `unlock_scheduled_jobs` | Разблокировать регламентные задания | cluster_id, database_ids |
| `terminate_sessions` | Завершить сеансы | database_ids, session_filter |
| `block_sessions` | Запретить новые сеансы | database_ids, message |
| `unblock_sessions` | Разрешить новые сеансы | database_ids |

#### OData Operations
| Операция | Описание | Параметры |
|----------|----------|-----------|
| `install_extension` | Установить расширение | database_ids, extension_file |
| `query` | Выполнить OData запрос | database_ids, entity, filter |
| `create` | Создать записи | database_ids, entity, data |
| `update` | Обновить записи | database_ids, entity, filter, data |
| `delete` | Удалить записи | database_ids, entity, filter |

#### System Operations
| Операция | Описание | Параметры |
|----------|----------|-----------|
| `sync_cluster` | Синхронизировать кластер с RAS | cluster_id |
| `discover_clusters` | Обнаружить кластеры | ras_server, cluster_service_url |
| `health_check` | Проверить доступность | database_ids |

#### Backup/Restore (future)
| Операция | Описание | Параметры |
|----------|----------|-----------|
| `backup` | Создать резервную копию | database_id, path |
| `restore` | Восстановить из копии | database_id, backup_file |

### Context Menu Actions

```
┌─────────────────────────────────────────────────────────────┐
│ Databases Table                                              │
├─────┬──────────────┬────────┬────────────────────────────────┤
│  □  │ Database     │ Status │ Actions                        │
├─────┼──────────────┼────────┼────────────────────────────────┤
│  ☑  │ УТ_Prod      │ Active │ [⋮] ← Context Menu             │
│  ☑  │ БП_Test      │ Active │                                │
│  □  │ ЗУП_Dev      │ Sync.. │     ┌────────────────────────┐ │
└─────┴──────────────┴────────┴─────│ 🔒 Lock Jobs           │─┤
                                    │ 🔓 Unlock Jobs         │ │
  [Bulk Actions ▼]                  │ ⛔ Block Sessions      │ │
   └─ Same menu for selected        │ ✅ Unblock Sessions    │ │
                                    │ 🚀 Install Extension   │ │
                                    │ 🔍 Health Check        │ │
                                    │ 📦 Backup              │ │
                                    │ ─────────────────────  │ │
                                    │ ⚙️ More Operations...  │ │
                                    └────────────────────────┘ │
```

### Role-Based Access

| Роль | Может создавать Workflows | Может запускать операции | Может видеть все операции |
|------|---------------------------|-------------------------|---------------------------|
| Admin | ✅ | ✅ | ✅ |
| Operator | ❌ | ✅ (только одобренные) | ✅ (свои + shared) |
| Viewer | ❌ | ❌ | ✅ (только чтение) |

### User Input для Custom Operations

```
Workflow с пользовательским вводом:
┌─────────────────────────────────────────────────────────────┐
│ Execute Workflow: "Update Price List"                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 📁 Upload Data File (required)                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  [Drag & Drop CSV/Excel file here]                      │ │
│ │  or click to browse                                      │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ 📅 Effective Date                                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  [2025-12-09]                                           │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ 💬 Comment (optional)                                        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  Price update Q4 2025                                   │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│                    [Cancel]  [Execute Workflow]              │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Quick Fixes (1-2 дня)

### 1.1 Добавить Cluster Service URL в Discover Modal

**Файл:** `frontend/src/components/clusters/DiscoverClustersModal.tsx`

**Изменения:**
- Добавить поле `cluster_service_url` с дефолтом из `systemConfig.ras_adapter_url`
- Обновить тип `DiscoverClustersRequest`
- Передавать в API `/api/v2/clusters/discover-clusters/`

**Оценка:** 2 часа

### 1.2 Фикс URL parameter в RecentOperationsTable

**Файл:** `frontend/src/components/service-mesh/RecentOperationsTable.tsx:57`

**Изменения:**
```typescript
// Было:
navigate(`/operation-monitor?id=${record.id}`)

// Стало:
navigate(`/operation-monitor?operation=${record.id}`)
```

**Оценка:** 15 минут

---

## Phase 2: Unified Operations Center (1 неделя)

### 2.1 Объединить /operations и /operation-monitor

**Концепция:** Одна страница с вкладками + Wizard

```
/operations
├── Header: [+ New Operation]  [Filters]  [Search]
├── Tab: All Operations
│   └── Таблица всех операций с фильтрами
├── Tab: Live Monitor
│   └── SSE-based real-time monitoring для выбранной операции
└── Modal: New Operation Wizard (4 steps)
```

### 2.2 New Operation Wizard

**Компонент:** `frontend/src/components/operations/NewOperationWizard.tsx`

```typescript
interface OperationWizardProps {
  visible: boolean;
  onClose: () => void;
  onSubmit: (operation: NewOperationRequest) => void;
  preselectedDatabases?: string[];  // для вызова из context menu
  preselectedType?: OperationType;   // для quick actions
}

type OperationType =
  | 'lock_scheduled_jobs' | 'unlock_scheduled_jobs'
  | 'terminate_sessions' | 'block_sessions' | 'unblock_sessions'
  | 'install_extension' | 'query' | 'create' | 'update' | 'delete'
  | 'sync_cluster' | 'discover_clusters' | 'health_check'
  | 'backup' | 'restore'
  | 'workflow';
```

**Steps:**
1. **Select Type** - карточки с категориями операций
2. **Select Target** - выбор БД (manual/filter/all)
3. **Configure** - динамическая форма на основе типа
4. **Review** - сводка и кнопка Execute

### 2.3 Унифицировать API трансформации

**Текущее состояние:**
- `operationTransforms.ts` - snake_case → snake_case
- `serviceMeshTransforms.ts` - snake_case → camelCase

**Целевое состояние:** Единый `operationTransforms.ts` с camelCase выходом

### 2.4 Интегрировать Service Mesh Recent Operations

Переиспользовать общий `OperationsTable` с пропсом `limit={20}`.

---

## Phase 3: Удаление дублей (3-5 дней)

### 3.1 Удалить /installation-monitor

**Проблемы:**
- Дублирует `/operations`
- Использует polling вместо SSE
- Узкоспециализирован (только OData extensions)

**Миграция:**
- Функционал Batch Install → New Operation Wizard (type: `install_extension`)
- Просмотр прогресса → Operations List + Live Monitor tab

**Файлы для удаления:**
```
frontend/src/pages/InstallationMonitor/
frontend/src/components/installation/  (если есть)
frontend/src/api/transforms/installationTransforms.ts
```

### 3.2 Удалить отдельный /operation-monitor

**Миграция:** Встроен в `/operations` как Tab: Live Monitor

**Файлы для удаления:**
```
frontend/src/pages/OperationMonitor/
```

**Сохранить:** `useOperationStream.ts` → переместить в `/operations/hooks/`

### 3.3 Обновить маршрутизацию и меню

**App.tsx:**
```typescript
// Удалить:
<Route path="/installation-monitor" ... />
<Route path="/operation-monitor" ... />

// Оставить:
<Route path="/operations" element={<UnifiedOperations />} />
```

**MainLayout.tsx меню (7 пунктов):**
```
├── Dashboard
├── System Status
├── Clusters
├── Databases
├── Operations (unified)
├── Workflows
└── Service Mesh
```

---

## Phase 4: Context Menu Actions (1 неделя)

### 4.1 Database Context Menu

**Файл:** `frontend/src/pages/Databases/Databases.tsx`

**Компонент:** `DatabaseActionsMenu.tsx`

```typescript
const menuItems: MenuProps['items'] = [
  { key: 'lock_jobs', icon: <LockOutlined />, label: 'Lock Jobs' },
  { key: 'unlock_jobs', icon: <UnlockOutlined />, label: 'Unlock Jobs' },
  { type: 'divider' },
  { key: 'block_sessions', icon: <StopOutlined />, label: 'Block Sessions' },
  { key: 'unblock_sessions', icon: <CheckOutlined />, label: 'Unblock Sessions' },
  { key: 'terminate_sessions', icon: <CloseCircleOutlined />, label: 'Terminate Sessions' },
  { type: 'divider' },
  { key: 'install_extension', icon: <RocketOutlined />, label: 'Install Extension' },
  { key: 'health_check', icon: <HeartOutlined />, label: 'Health Check' },
  { type: 'divider' },
  { key: 'more', icon: <MoreOutlined />, label: 'More Operations...' },
];
```

### 4.2 Bulk Actions для выбранных БД

**Таблица с checkbox selection:**
```typescript
<Table
  rowSelection={{
    type: 'checkbox',
    selectedRowKeys,
    onChange: setSelectedRowKeys,
  }}
  ...
/>

{selectedRowKeys.length > 0 && (
  <Dropdown menu={{ items: bulkMenuItems }}>
    <Button>
      Bulk Actions ({selectedRowKeys.length}) <DownOutlined />
    </Button>
  </Dropdown>
)}
```

### 4.3 Cluster Context Menu

Аналогично для кластеров:
- Sync Cluster
- Discover Infobases
- Health Check All DBs

---

## Phase 5: Custom Operations & Templates (1-2 недели)

### 5.1 Workflow как шаблон операции

**Связь с существующим Workflow Designer:**
- Workflow сохраняется как "template"
- При запуске через Operations Center → показать форму ввода параметров

**Схема Workflow с input fields:**
```json
{
  "name": "Update Price List",
  "description": "Загрузить новый прайс-лист во все базы",
  "input_schema": {
    "type": "object",
    "properties": {
      "price_file": {
        "type": "file",
        "title": "Price List File",
        "accept": ".csv,.xlsx",
        "required": true
      },
      "effective_date": {
        "type": "date",
        "title": "Effective Date",
        "default": "today"
      },
      "comment": {
        "type": "string",
        "title": "Comment",
        "maxLength": 500
      }
    }
  },
  "nodes": [...]
}
```

### 5.2 Dynamic Form Generator

**Компонент:** `frontend/src/components/operations/DynamicForm.tsx`

```typescript
interface DynamicFormProps {
  schema: JSONSchema;        // input_schema from workflow
  onSubmit: (values: any) => void;
}

// Поддерживаемые типы полей:
// - string (Input)
// - number (InputNumber)
// - boolean (Switch)
// - date (DatePicker)
// - file (Upload)
// - select (Select с options)
// - array (Table для загрузки данных)
```

### 5.3 File Upload & Processing

**Для загрузки таблиц данных:**
```typescript
<Upload
  accept=".csv,.xlsx,.xls"
  beforeUpload={handleFileUpload}
  showUploadList={false}
>
  <Button icon={<UploadOutlined />}>Upload Data File</Button>
</Upload>
```

**Backend:** файл загружается в S3/MinIO, URL передается в workflow payload.

---

## Phase 6: Dashboard Improvements (опционально)

### 6.1 Добавить виджеты

```
Dashboard
├── System Health Card (текущий)
├── Recent Operations Widget (NEW)
│   └── Последние 5 операций с real-time статусом
├── Failed Operations Alert (NEW)
│   └── Операции с ошибками за последние 24 часа
└── Quick Actions (NEW)
    └── + New Operation, View All Operations, etc.
```

### 6.2 Real-time обновление

- Использовать SSE для автообновления виджетов
- Убрать polling где возможно

---

## Структура файлов после унификации

### ✅ Реализовано (Phase 2)

```
frontend/src/
├── pages/
│   ├── Operations/                          # ✅ Unified Operations Center
│   │   ├── index.tsx                        # Re-exports
│   │   ├── OperationsPage.tsx               # Tabs: List + Live Monitor
│   │   ├── types.ts                         # UIBatchOperation, UITask
│   │   ├── utils.ts                         # getStatusColor, getOperationTypeLabel
│   │   └── components/
│   │       ├── OperationsTable.tsx          # ✅ Переиспользуемая таблица
│   │       ├── OperationDetailsModal.tsx    # ✅ Модалка деталей
│   │       ├── LiveMonitorTab.tsx           # ✅ SSE real-time monitoring
│   │       └── NewOperationWizard/          # ✅ 4-step wizard
│   │           ├── index.tsx                # Wizard с Steps
│   │           ├── types.ts                 # OperationType, OperationConfig
│   │           ├── SelectTypeStep.tsx       # Step 1: выбор типа
│   │           ├── SelectTargetStep.tsx     # Step 2: выбор БД
│   │           ├── ConfigureStep.tsx        # Step 3: параметры
│   │           └── ReviewStep.tsx           # Step 4: подтверждение
│   ├── InstallationMonitor/                 # ✅ УДАЛЕНО (Phase 3)
│   └── OperationMonitor/                    # ✅ УДАЛЕНО (Phase 3)
│
├── hooks/
│   └── useOperationStream.ts                # ✅ SSE хук (улучшен: memory leak fix)
│
├── utils/
│   └── formatters.ts                        # ✅ NEW: formatFileSize
│
├── components/
│   ├── layout/
│   │   └── MainLayout.tsx                   # ✅ 7 menu items
│   └── service-mesh/
│       ├── RecentOperationsTable.tsx        # ✅ Использует shared utils
│       └── ServiceMeshTab.tsx               # ✅ Unified navigation
│
└── App.tsx                                  # ✅ Редиректы deprecated routes
```

### 🔲 Планируется (Phase 3-6)

```
frontend/src/
├── pages/
│   ├── Dashboard/              # Phase 6: + виджеты
│   ├── Databases/              # Phase 4: + Context Menu + Bulk Actions
│   │   └── components/
│   │       └── DatabaseActionsMenu.tsx
│   └── Workflows/              # Phase 5: + input_schema support
│
└── components/
    └── operations/
        └── DynamicForm.tsx     # Phase 5: JSON Schema based form
```

---

## Удалённые страницы/компоненты

| Компонент | Причина | Замена |
|-----------|---------|--------|
| `/installation-monitor` | Дублирует /operations | New Operation Wizard |
| `/operation-monitor` | Объединено с /operations | Tab: Live Monitor |
| `RecentOperationsTable` | Дублирование | Shared OperationsTable |
| `BatchInstallButton` | Узкоспециализирован | New Operation Wizard |

---

## Меню после унификации

```
Sidebar (7 пунктов вместо 9):
├── Dashboard
├── System Status
├── Clusters
├── Databases
├── Operations (unified)
├── Workflows
└── Service Mesh
```

---

## Timeline

| Phase | Название | Оценка | Зависимости | Статус |
|-------|----------|--------|-------------|--------|
| 1 | Quick Fixes | 1-2 дня | - | ✅ DONE |
| 2 | Unified Operations Center | 1 неделя | Phase 1 | ✅ DONE |
| 3 | Удаление дублей | 3-5 дней | Phase 2 | ✅ DONE |
| 4 | Context Menu Actions | 1 неделя | Phase 2 | ✅ DONE |
| 5 | Custom Operations & Templates | 1-2 недели | Phase 2, 4 | 🔲 TODO |
| 6 | Dashboard Improvements | 1 неделя | Phase 2 | 🔲 TODO |

**Total:** 4-6 недель (Phase 6 опционально)

---

## Критерии готовности

### Phase 1 ✅ DONE (2025-12-09)
- [x] Discover Clusters имеет поле Cluster Service URL
- [x] URL parameter fix в RecentOperationsTable (`?id` → `?operation`)

### Phase 2 ✅ DONE (2025-12-09)
- [x] Operations Center с табами List + Live Monitor
- [x] New Operation Wizard (4 steps)
- [x] Поддержка всех типов операций (RAS, OData, System)
- [x] Меню: 7 пунктов (убраны Installation Monitor, Operation Monitor)
- [x] Редиректы со старых URL на unified /operations

### Phase 3 ✅ DONE (2025-12-09)
- [x] `/pages/InstallationMonitor/` удалён
- [x] `/pages/OperationMonitor/` удалён
- [x] `/hooks/useInstallationProgress.ts` удалён
- [x] Обновлён редирект в InstallationProgressModal → /operations?tab=monitor
- Note: `installationTransforms.ts` и `/components/Installation/` оставлены (используются в Databases)

### Phase 4 ✅ DONE (2025-12-09)
- [x] Context menu на каждой БД (DatabaseActionsMenu)
- [x] Bulk actions для выбранных БД (BulkActionsToolbar)
- [x] Confirm modal перед операциями (OperationConfirmModal)
- [x] Backend: `POST /api/v2/operations/execute/` endpoint
- [x] Backend: Go Worker RAS handler с параллельной обработкой
- [ ] Context menu на кластерах (отложено на Phase 5)

### Phase 5
- [ ] Workflow input_schema поддержка
- [ ] DynamicForm компонент
- [ ] File upload для данных

### Phase 6
- [ ] Dashboard виджеты
- [ ] Real-time updates через SSE

---

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Потеря функционала при удалении | Low | High | Полный анализ перед удалением, regression tests |
| Breaking changes в API | Medium | Medium | Версионирование endpoints, deprecation warnings |
| Регрессии в UI | Medium | Medium | E2E тесты, manual QA |
| Сложность New Operation Wizard | Medium | Low | Итеративная разработка, MVP first |
| File upload limitations | Low | Medium | Проверить размеры, типы файлов |

---

## Backend изменения (требуются)

### Новые endpoints

```
POST /api/v2/operations/create/
  - Универсальный endpoint для создания любых операций
  - Принимает operation_type + target + payload

POST /api/v2/files/upload/
  - Загрузка файлов для операций
  - Возвращает file_url для передачи в payload

GET /api/v2/operations/types/
  - Список доступных типов операций
  - Включает схему параметров для каждого типа
```

### Изменения в Workflow model

```python
class Workflow(models.Model):
    # Existing fields...

    # NEW: Schema for user input
    input_schema = models.JSONField(
        null=True, blank=True,
        help_text="JSON Schema for user input parameters"
    )

    # NEW: Mark as template for Operations Center
    is_template = models.BooleanField(default=False)
```

---

## Ссылки

- [API V2 Unification Roadmap](./API_V2_UNIFICATION_ROADMAP.md)
- [Event-Driven Architecture](../architecture/EVENT_DRIVEN_ARCHITECTURE.md)
- [Frontend Source](../../frontend/src/)

---

**Версия:** 4.0
**Автор:** AI Assistant
**Последнее обновление:** 2025-12-09

### Changelog

**v4.0 (2025-12-09):**
- ✅ Phase 4 выполнена полностью:
  - **Frontend:**
    - DatabaseActionsMenu — context menu с операциями (lock/unlock/block/terminate)
    - BulkActionsToolbar — bulk actions для выбранных БД
    - OperationConfirmModal — confirm dialog с формой для block_sessions
    - useDatabaseActions hook — выполнение операций через API
    - Row selection (checkboxes) в таблице Databases
    - Вынесены константы в `constants.ts` (RAS_OPERATIONS)
  - **Backend Orchestrator:**
    - `POST /api/v2/operations/execute/` — универсальный endpoint
    - RBAC: модели ClusterPermission, DatabasePermission
    - PermissionService + CanExecuteOperation permission class
    - UUID validation, rate limiting (30/min), conflict check
  - **Backend Go Worker:**
    - RAS Handler с параллельной обработкой
    - Semaphore для ограничения (20 concurrent operations)
    - HTTP клиент для RAS Adapter
- Code Review fixes:
  - Critical #1: RBAC для проверки прав на БД
  - Critical #2: UUID validation в сериализаторе
  - High #3: Rate limiting (ExecuteOperationThrottle)
  - High #4: Проверка конфликтующих операций
  - High #5: Semaphore в Go Worker
  - Medium #8: health_check убран из RAS операций
  - Medium #9: Form reset при закрытии модалки
  - Low #10-13: Константы, типизация
- См. детальный план: [PHASE4_CONTEXT_MENU_PLAN.md](./PHASE4_CONTEXT_MENU_PLAN.md)

**v3.1 (2025-12-09):**
- ✅ Phase 3 выполнена:
  - Удалены deprecated страницы: InstallationMonitor, OperationMonitor
  - Удалён неиспользуемый хук useInstallationProgress.ts
  - Обновлён редирект в InstallationProgressModal
  - Сохранены активные компоненты Installation (используются в Databases)
- Commit: `a80f249 refactor(frontend): Phase 3 - Remove deprecated pages`

**v3.0 (2025-12-09):**
- ✅ Phase 2 выполнена полностью:
  - Создан OperationsPage с табами (All Operations + Live Monitor)
  - Создан NewOperationWizard с 4 шагами (SelectType, SelectTarget, Configure, Review)
  - Интегрирован SSE мониторинг через useOperationStream хук
  - Рефакторинг структуры: вынесены OperationsTable, OperationDetailsModal, utils
  - Меню сокращено с 9 до 7 пунктов
  - Добавлены редиректы /installation-monitor → /operations, /operation-monitor → /operations
  - Обновлён ServiceMeshTab для использования unified Operations
- Bug fixes после code review:
  - Fixed memory leak в useOperationStream (сброс state при смене operationId)
  - Добавлен MAX_EVENTS=1000 лимит для предотвращения переполнения памяти
  - Добавлен AbortController для предотвращения race conditions при polling
  - Fixed preselection race condition с useRef
  - Добавлен Alert UI для отображения ошибок загрузки
  - Вынесен formatFileSize в shared utils/formatters.ts
- Commit: `0b2e3cd feat(frontend): Unified Operations Center - Phase 2 complete`

**v2.1 (2025-12-09):**
- ✅ Phase 1 выполнена:
  - Добавлено поле Cluster Service URL в DiscoverClustersModal
  - Исправлен URL parameter в ServiceMeshTab (`?id` → `?operation`)
- Обновлён timeline с колонкой статуса

**v2.0 (2025-12-09):**
- Добавлена архитектура Unified Operations Center
- Добавлен New Operation Wizard (4 steps)
- Добавлены Context Menu Actions для БД и кластеров
- Добавлена Phase 5: Custom Operations & Templates
- Добавлен DynamicForm для JSON Schema based forms
- Расширен список поддерживаемых операций
- Добавлены требования к backend изменениям
- Обновлён timeline: 4-6 недель

**v1.0 (2025-12-09):**
- Initial draft
