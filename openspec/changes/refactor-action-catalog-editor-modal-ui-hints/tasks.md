## 1. Backend: UI hints API
- [ ] Добавить staff-only endpoint `GET /api/v2/ui/action-catalog/editor-hints/` (или эквивалентный) с версионированным ответом.
- [ ] Описать контракт в `contracts/orchestrator/openapi.yaml` и перегенерить frontend client.
- [ ] Реализовать registry capability → hints (минимум: `extensions.set_flags`).
- [ ] Тесты:
  - staff-only доступ,
  - формат ответа + наличие hints для `extensions.set_flags`.

## 2. Frontend: Modal v2 layout
- [ ] Разбить `ActionCatalogEditorModal` на вкладки (Basics / Executor / Params / Safety & Fixed / Preview).
- [ ] Sticky footer: Save/Cancel + (Preview/Copy/Reset).
- [ ] Params UX:
  - поиск по параметрам,
  - группировка required/optional/filled,
  - сворачиваемые группы,
  - perf‑гарантии (не рендерить тысячи `Form.Item` без необходимости).

## 3. Frontend: capability-driven fixed section
- [ ] Добавить query `useActionCatalogEditorHints()` и кэширование.
- [ ] Вынести capability‑специфичный рендер `executor.fixed` в отдельный компонент, который использует hints.
- [ ] Интегрировать `@rjsf/antd` (или другой schema‑form слой) для рендера fixed‑секции по `schema+uiSchema`.
- [ ] Удалить хардкод `extensions.set_flags` fixed.apply_mask UI из модалки (заменить на hints-driven).

## 4. Spec & Validation
- [ ] Добавить delta-specs для `ui-action-catalog-editor`.
- [ ] `openspec validate refactor-action-catalog-editor-modal-ui-hints --strict --no-interactive`.

