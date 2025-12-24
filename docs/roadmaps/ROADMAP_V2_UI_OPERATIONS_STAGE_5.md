# Roadmap: Этап 5 — Единый экран операций + трассировка

**Дата:** 2025-12-23  
**Статус:** ✅ выполнено  
**Приоритет:** Высокий  

---

## Контекст

Сейчас уже есть визуализация таймлайна одной операции (waterfall).  
Нужно сделать `/operations` единым экраном с live + history и связать атомарные операции с workflow-run (DAG).

---

## Цели

- Единый UI для операций (live + history), без отдельного Operation Details.
- Нормальная корреляция атомарных операций внутри workflow-run.
- Возможность перехода из service-mesh в детали операции.
- Подготовка к распределённому трейсингу (trace_id во всех событиях).

---

## Сделано

- В событиях операций и operation-flow добавлены поля `trace_id`, `workflow_execution_id`, `node_id`.
- Корреляция прокинута до worker‑timeline и worker‑streams.
- `/operations` = основной экран с drawer + waterfall, поддерживает deep‑link.
- `/service-mesh` использует те же компоненты для деталей/таймлайна.
- Добавлены фильтры по `workflow_execution_id` и `node_id`.
- Live Monitor удалён (переход через `/operations?operation=...`).
- Уже есть визуализация таймлайна операции:
  - UI: `frontend/src/components/service-mesh/OperationTimelineDrawer.tsx`
  - Визуализация: `frontend/src/components/service-mesh/WaterfallTimeline.tsx`
  - Endpoint: `POST /api/v2/internal/operations/{operation_id}/timeline`

---

## Скоуп

### UI
- `/operations` = основной экран с timeline/waterfall и деталями.
- `/service-mesh` использует те же компоненты для деталей/таймлайна.
- В `/operations` добавлены фильтры по `workflow_execution_id`.

### API/Streams
- В каждом event для операции: `workflow_execution_id`, `node_id`, `trace_id`.
- История и live‑поток должны иметь одинаковую схему события.

### Data model (минимум)
- `WorkflowExecution.id` уже есть (используем как `workflow_execution_id`).
- `WorkflowStepResult.node_id` уже есть (используем как `node_id`).
- Для атомарной операции добавляем `operation_id` ↔ `node_id` связь в событиях.

---

## План работ (факт)

### 5.1 — Контракты и схема событий (✅)
- Определить единый формат событий операции (history + live).
- Добавить поля `workflow_execution_id`, `node_id`, `trace_id`.
- Обновить OpenAPI там, где события/ответы сериализуются из БД.

### 5.2 — Корреляция операций с workflow-run (✅)
- При запуске workflow: пробрасывать `workflow_execution_id` и `node_id` в операции.
- В Streams событиях фиксировать корреляцию.

### 5.3 — Единый UI `/operations` (✅)
- Список операций + панель деталей справа (drawer).
- Waterfall таймлайн в деталях (использовать существующую визуализацию).
- Ссылка на workflow-run (если есть).

### 5.4 — Интеграция `/service-mesh` (✅)
- Из service‑mesh клик открывает те же детали операции.
- Единые компоненты для таймлайна/деталей.

### 5.5 — Депрекейт Live Monitor (✅)
- Редирект/удаление старого экрана.
- Сохранить deep‑link в `/operations?operation=...`.

### 5.6 — Тесты и критерии качества (⚠️ частично)
- API tests: корректные поля в событиях — добавлены.
- UI tests: открытие/закрытие деталей, загрузка таймлайна — не реализованы.

---

## Критерии готовности

- Любая атомарная операция показывает связь с workflow-run (если была вызвана из него).
- В `/operations` и `/service-mesh` отображаются одинаковые детали операции.
- Нет отдельного экрана Operation Details.
- Все события содержат `trace_id` (может быть пустым, но поле есть).

---

## Вне скоупа

- Полноценная интеграция Jaeger UI (только подготовка полей).
- Новые типы операций/драйверы.

---

## Риски

- Несогласованность форматов live/history → UI показывает разное.
- Потеря `workflow_execution_id` в событиях → нет связи с workflow.
- Увеличение объёма событий → нужна виртуализация и лимиты.
