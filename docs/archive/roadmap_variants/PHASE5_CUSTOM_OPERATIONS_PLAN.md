# Phase 5: Custom Operations & Templates - План реализации

> Расширяемая система операций с динамическими формами на основе JSON Schema

**Дата создания:** 2025-12-09
**Статус:** ✅ COMPLETED (2025-12-10)
**Оценка:** 10-14 дней (фактически: 1 день)
**Зависимости:** Phase 4 (Context Menu Actions) ✅

---

## Содержание

1. [Обзор и цели](#обзор-и-цели)
2. [Структура input_schema](#структура-input_schema)
3. [API Endpoints](#api-endpoints)
4. [DynamicForm компонент](#dynamicform-компонент)
5. [Интеграция с Operations Wizard](#интеграция-с-operations-wizard)
6. [File Upload Flow](#file-upload-flow)
7. [Порядок реализации](#порядок-реализации)
8. [Риски и митигация](#риски-и-митигация)
9. [Acceptance Criteria](#acceptance-criteria)

---

## Обзор и цели

### Проблема

Сейчас типы операций жёстко закодированы в frontend (`OPERATION_TYPES` в types.ts), а формы конфигурации — отдельные компоненты для каждого типа. Это затрудняет добавление новых операций без изменения кода.

### Решение

Сделать систему **data-driven**:
1. Администратор создаёт WorkflowTemplate с `input_schema` (JSON Schema)
2. Frontend автоматически генерирует форму на основе схемы
3. Пользователь заполняет форму, данные валидируются и передаются в workflow

### Ключевые преимущества

- Новые операции без изменения frontend кода
- Стандартизированная валидация через JSON Schema
- Переиспользуемые шаблоны операций
- Поддержка загрузки файлов (CSV, Excel) для bulk-операций

---

## Структура input_schema

### Формат

Используется **JSON Schema draft-07** с расширениями через `x-*` атрибуты для UI hints.

### Поддерживаемые типы полей (x-field-type)

| x-field-type | JSON Schema type | UI Компонент | Описание |
|--------------|------------------|--------------|----------|
| `text` | string | Input | Однострочный текст (default) |
| `textarea` | string | TextArea | Многострочный текст |
| `password` | string | Input.Password | Скрытый ввод |
| `number` | integer/number | InputNumber | Числовой ввод |
| `boolean` | boolean | Switch | Переключатель |
| `date` | string (format: date) | DatePicker | Выбор даты |
| `datetime` | string (format: date-time) | DatePicker (showTime) | Дата + время |
| `select` | string (enum) | Select | Выпадающий список |
| `multi-select` | array (items: enum) | Select (mode: multiple) | Множественный выбор |
| `file` | string | Upload | Загрузка файла |
| `entity` | string | AutoComplete | OData entity picker |
| `database-select` | array | DatabaseSelector | Выбор баз данных |

### Расширенные атрибуты (x-*)

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `x-field-type` | string | Тип UI компонента |
| `x-order` | number | Порядок отображения поля |
| `x-placeholder` | string | Placeholder для input |
| `x-help-text` | string | Дополнительная подсказка |
| `x-conditional` | object | Условное отображение (field, value, operator) |
| `x-file-accept` | string | Допустимые расширения файлов |
| `x-file-max-size` | number | Максимальный размер файла в bytes |
| `x-depends-on` | string | Зависимость от другого поля |

---

## API Endpoints

### Изменения модели WorkflowTemplate

Добавить поля:
- `input_schema` (JSONField) — JSON Schema для динамических форм
- `is_template` (BooleanField) — флаг шаблона для Operations Center
- `icon` (CharField) — имя иконки Ant Design
- `category` (CharField) — категория: ras, odata, system, custom

### Новые endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v2/workflows/list-templates/` | Список шаблонов (is_template=true) |
| GET | `/api/v2/workflows/get-template-schema/` | Схема конкретного шаблона |
| POST | `/api/v2/files/upload/` | Универсальная загрузка файлов |
| GET | `/api/v2/files/download/{file_id}/` | Скачивание файла |
| DELETE | `/api/v2/files/{file_id}/` | Удаление файла |

### Новая модель UploadedFile

Django app `files` с моделью для временного хранения файлов:
- `id` (UUID) — primary key
- `filename`, `original_filename` — имена файлов
- `file_path` — относительный путь в storage
- `size`, `mime_type` — метаданные
- `purpose` — назначение (operation_input, extension, export)
- `uploaded_by` — FK на User
- `expires_at` — время автоудаления (default: 24 часа)
- `checksum` — SHA-256 для верификации

---

## DynamicForm компонент

### Структура

```
frontend/src/components/DynamicForm/
├── index.ts                    # Public exports
├── DynamicForm.tsx             # Main component
├── types.ts                    # Type definitions
├── hooks/
│   ├── useSchemaValidation.ts  # JSON Schema validation (Ajv)
│   ├── useConditionalFields.ts # Conditional visibility
│   └── useFieldOrder.ts        # Sort by x-order
├── renderers/
│   ├── index.ts                # Field renderer registry
│   ├── TextFieldRenderer.tsx
│   ├── NumberFieldRenderer.tsx
│   ├── BooleanFieldRenderer.tsx
│   ├── DateFieldRenderer.tsx
│   ├── SelectFieldRenderer.tsx
│   ├── FileFieldRenderer.tsx
│   ├── EntityFieldRenderer.tsx
│   └── DatabaseSelectRenderer.tsx
└── utils/
    ├── schemaParser.ts         # Parse schema to configs
    ├── validator.ts            # Ajv setup
    └── defaults.ts             # Extract defaults
```

### Ключевые интерфейсы

**DynamicFormProps:**
- `schema` — JSON Schema для генерации формы
- `values` — текущие значения полей
- `onChange` — callback при изменении
- `onValidationError` — callback при ошибках валидации
- `uploadedFiles` — маппинг field_name -> file_id
- `onFileUpload` — callback при загрузке файла
- `disabled` — отключить все поля
- `layout` — horizontal/vertical

### Логика работы

1. Парсинг схемы → список полей с конфигурацией
2. Сортировка по `x-order`
3. Фильтрация по `x-conditional` (условное отображение)
4. Рендеринг через registry (getFieldRenderer по x-field-type)
5. Валидация через Ajv при изменении значений

---

## Интеграция с Operations Wizard

### SelectTypeStep

Изменения:
- Загрузка custom templates через `useWorkflowTemplates({ is_template: true })`
- Объединение built-in операций с custom templates
- Группировка по категориям (ras, odata, system, custom)
- Badge "Custom" для пользовательских шаблонов

### ConfigureStep

Изменения:
- Определение типа операции: legacy (hardcoded) vs custom (template)
- Для custom templates: загрузка схемы через `useTemplateSchema(templateId)`
- Рендеринг DynamicForm для custom templates
- Сохранение legacy форм для backward compatibility

### Новые хуки

- `useWorkflowTemplates(options)` — загрузка списка шаблонов
- `useTemplateSchema(templateId)` — загрузка input_schema конкретного шаблона

---

## File Upload Flow

### Последовательность

1. Пользователь выбирает файл в DynamicForm (FileFieldRenderer)
2. Frontend вызывает `POST /api/v2/files/upload/`
3. Django сохраняет файл, создаёт UploadedFile record, возвращает file_id
4. Frontend сохраняет file_id в form values
5. При submit операции file_id передаётся в input_context
6. Go Worker получает файл через API или прямой путь
7. Cleanup job удаляет expired files (cron, каждый час)

### Безопасность

- Валидация MIME type и расширения файла
- Ограничение размера (default: 100MB, configurable per field)
- Sandboxed storage (вне webroot)
- SHA-256 checksum для верификации
- Автоудаление через 24 часа

### Storage структура

```
/var/lib/1c/uploads/
├── 2025/
│   └── 12/
│       └── {uuid}/
│           └── filename.csv
```

---

## Порядок реализации

### Phase 5.1: Backend Foundation (3-4 дня)

| # | Task | Файлы |
|---|------|-------|
| 1 | Миграция WorkflowTemplate | `apps/templates/workflow/models.py`, migrations |
| 2 | Django app `files` | `apps/files/` (models, services, views) |
| 3 | API endpoints для files | `apps/api_v2/views/files.py` |
| 4 | API endpoints для templates | `apps/api_v2/views/workflows.py` |
| 5 | Cleanup job | `apps/files/tasks.py` |
| 6 | Tests | `apps/files/tests/` |

### Phase 5.2: Frontend DynamicForm (4-5 дней)

| # | Task | Файлы |
|---|------|-------|
| 1 | Types & interfaces | `components/DynamicForm/types.ts` |
| 2 | Schema validation hook | `hooks/useSchemaValidation.ts` |
| 3 | Basic renderers | Text, Number, Boolean, Select |
| 4 | File renderer | `FileFieldRenderer.tsx` |
| 5 | Conditional fields hook | `hooks/useConditionalFields.ts` |
| 6 | Main DynamicForm | `DynamicForm.tsx` |
| 7 | Files API client | `api/files.ts` |
| 8 | Tests | `__tests__/` |

### Phase 5.3: Integration (2-3 дня)

| # | Task | Файлы |
|---|------|-------|
| 1 | Update SelectTypeStep | `NewOperationWizard/SelectTypeStep.tsx` |
| 2 | Update ConfigureStep | `NewOperationWizard/ConfigureStep.tsx` |
| 3 | useWorkflowTemplates hook | `hooks/useWorkflowTemplates.ts` |
| 4 | useTemplateSchema hook | `hooks/useTemplateSchema.ts` |
| 5 | E2E testing | Manual + Cypress |

### Phase 5.4: Template Library (1-2 дня)

| # | Task | Файлы |
|---|------|-------|
| 1 | Fixtures для стандартных операций | WorkflowTemplate с input_schema |
| 2 | Admin UI для управления шаблонами | `pages/Admin/Templates/` |
| 3 | Документация | `docs/CUSTOM_OPERATIONS_GUIDE.md` |

---

## Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| JSON Schema validation complexity | Medium | Medium | Использовать Ajv библиотеку |
| File upload security | High | High | Валидация типов, размеров, sandboxed storage |
| Backward compatibility | Medium | High | Сохранить legacy forms, постепенная миграция |
| Performance (large files) | Medium | Medium | Chunked upload, streaming, progress |
| Go Worker file access | Low | High | Shared storage или API для download |

---

## Acceptance Criteria

### Backend

- [ ] WorkflowTemplate.input_schema работает и валидируется
- [ ] File upload API работает (upload, download, delete)
- [ ] Templates API возвращает custom templates с is_template=true
- [ ] Cleanup job удаляет expired files
- [ ] Tests: >80% coverage для files app

### Frontend

- [ ] DynamicForm генерирует формы из JSON Schema
- [ ] Все field types работают (text, number, boolean, select, file)
- [ ] Conditional fields показываются/скрываются корректно
- [ ] File upload работает с progress и error handling
- [ ] Unit tests для DynamicForm и renderers

### Integration

- [ ] SelectTypeStep показывает custom templates
- [ ] ConfigureStep использует DynamicForm для custom templates
- [ ] Full flow работает: select template → configure → execute
- [ ] E2E: Happy path для custom operation

---

## Оценка Effort

| Phase | Effort | Calendar Days |
|-------|--------|---------------|
| 5.1 Backend Foundation | 16h | 3-4 days |
| 5.2 Frontend DynamicForm | 24h | 4-5 days |
| 5.3 Integration | 15h | 2-3 days |
| 5.4 Template Library | 10h | 1-2 days |
| **Total** | **65h** | **10-14 days** |

---

## Ссылки

- [Frontend Unification Roadmap](./FRONTEND_UNIFICATION_ROADMAP.md)
- [API V2 Unification Roadmap](./API_V2_UNIFICATION_ROADMAP.md)
- [JSON Schema Specification](https://json-schema.org/draft-07/json-schema-release-notes.html)

---

**Версия:** 1.0
**Автор:** AI Assistant
**Последнее обновление:** 2025-12-09
