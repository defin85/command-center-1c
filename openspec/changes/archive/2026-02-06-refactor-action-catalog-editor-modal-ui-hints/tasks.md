## 1. Backend: UI hints API
- [x] Добавить staff-only endpoint `GET /api/v2/ui/action-catalog/editor-hints/` (или эквивалентный) с версионированным ответом.
- [x] Описать контракт в `contracts/orchestrator/openapi.yaml` и перегенерить frontend client.
- [x] Реализовать registry capability → hints (минимум: `extensions.set_flags`).
- [x] Тесты:
  - staff-only доступ,
  - формат ответа + наличие hints для `extensions.set_flags`.

## 2. Frontend: Modal v2 layout
- [x] Разбить `ActionCatalogEditorModal` на вкладки (Basics / Executor / Params / Safety & Fixed / Preview).
- [x] Sticky footer: Save/Cancel + (Preview/Copy/Reset).
- [x] Params UX:
  - поиск по параметрам,
  - группировка required/optional/filled,
  - сворачиваемые группы,
  - perf‑гарантии (не рендерить тысячи `Form.Item` без необходимости).

## 3. Frontend: capability-driven fixed section
- [x] Добавить query `useActionCatalogEditorHints()` и кэширование.
- [x] Вынести capability‑специфичный рендер `executor.fixed` в отдельный компонент, который использует hints.
- [x] Интегрировать `@rjsf/antd` (или другой schema‑form слой) для рендера fixed‑секции по `schema+uiSchema`.
- [x] Удалить хардкод `extensions.set_flags` fixed.apply_mask UI из модалки (заменить на hints-driven).

## 4. Spec & Validation
- [x] Добавить delta-specs для `ui-action-catalog-editor`.
- [x] `openspec validate refactor-action-catalog-editor-modal-ui-hints --strict --no-interactive`.
