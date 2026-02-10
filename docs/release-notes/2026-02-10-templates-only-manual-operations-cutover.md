# Release Notes — 2026-02-10

## refactor-templates-only-remove-action-catalog

### Что изменилось
- Платформенный Action Catalog полностью decommissioned:
  - runtime endpoint `GET /api/v2/ui/action-catalog/` возвращает `404` (`error.code=NOT_FOUND`);
  - legacy runtime settings key `ui.action_catalog` больше не поддерживается в write/read path.
- Execution model переведена на templates-only + manual operations:
  - `extensions.plan/apply` используют `manual_operation` + template-based resolve;
  - `action_id` и legacy action-catalog payload удалены.
- Добавлен tenant-scoped API preferred bindings:
  - `GET /api/v2/extensions/manual-operation-bindings/`;
  - `PUT|DELETE /api/v2/extensions/manual-operation-bindings/{manual_operation}/`.
- Для extensions flow введён детерминированный resolve порядок:
  - `template_id` override;
  - иначе preferred binding;
  - иначе fail-closed `MISSING_TEMPLATE_BINDING`.
- В plan metadata фиксируются `result_contract` и `mapping_spec_ref`; apply использует pinned metadata без runtime fallback.

### Breaking changes
- Удалена поддержка `surface=action_catalog` в operation catalog API.
- Legacy планы `extensions.apply` старого формата отклоняются (`PLAN_INVALID_LEGACY`).
- UI `/templates`, `/extensions`, `/databases` работают без action-catalog controls.
