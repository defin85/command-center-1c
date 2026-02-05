# Change: refactor-action-catalog-editor-modal-ui-hints

## Why
Модалка Add/Edit action в редакторе `ui.action_catalog` сейчас выполняет слишком много задач в одном длинном скролле (Basics + Executor + params Guided/Raw + fixed/presets). На командах с большим количеством параметров Guided‑панель превращается в “простыню”, ухудшается читаемость, навигация и стабильность UX.

Дополнительно, capability‑специфичный UI (например `extensions.set_flags` → `fixed.apply_mask`) сейчас реализуется хардкодом на фронте, что плохо масштабируется: новые reserved capabilities будут увеличивать сложность и риск регрессий.

## What Changes
1) **Modal v2 (UI)**:
   - Перестроить модалку на вкладки (Basics / Executor / Params / Safety & Fixed / Preview).
   - Сделать “params” управляемыми: поиск, группировка (required/optional/filled), сворачивание групп, perf‑friendly рендер.
   - Sticky footer с Save/Cancel и быстрыми действиями (Preview, Copy JSON, Reset).

2) **Capability-driven UI hints (backend → UI)**:
   - Добавить staff-only endpoint, который возвращает “UI hints” для capability (JSON Schema + uiSchema) для capability‑специфичных секций модалки (в первую очередь `executor.fixed.*`).
   - На фронте рендерить capability‑специфичную часть **декларативно** (например через `@rjsf/antd`), а не через хардкод `if capability === ...`.

3) **Первый кейс hints**:
   - `extensions.set_flags`: hints описывают `fixed.apply_mask` (3 булевых флага) и текстовые подсказки.

## Impact
- Backend (orchestrator):
  - новый UI endpoint (staff-only) для получения capability hints,
  - OpenAPI контракт + generated client.
- Frontend:
  - переработка `ActionCatalogEditorModal` и связанных утилит,
  - добавление/интеграция `@rjsf/antd` (или эквивалентного schema‑form слоя) для capability‑секций.
- Specs:
  - `ui-action-catalog-editor` (новые/модифицированные требования).

## Non-goals (MVP)
- Полная замена всего Guided params UI на JSON Schema form (можно делать инкрементально).
- Перенос всех правил валидации на фронт (источник истины — backend).

