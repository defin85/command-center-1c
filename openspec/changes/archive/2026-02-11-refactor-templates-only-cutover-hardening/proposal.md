# Change: Закрыть хвосты templates-only cutover и риски эксплуатационной регрессии

## Why
Архивный change `refactor-templates-only-remove-action-catalog` закрыл большую часть миграции на templates-only, но аудит выявил незакрытые технические хвосты: неполная реализация pinned mapping в completion pipeline, legacy артефакты в OpenAPI/generated client, а также устаревшие тесты и операторские инструкции.

Без отдельного hardening-шага остаются риски недетерминированных snapshot’ов, ложных CI-падений и возврата к legacy паттернам через документацию/тестовые сценарии.

## What Changes
- Довести backend completion pipeline до полного pinned mapping/result-contract поведения без runtime fallback на текущее состояние mapping.
- Убрать legacy Action Catalog schemas из публичного OpenAPI-контракта и из сгенерированных frontend моделей.
- Переписать/удалить legacy тесты и фикстуры, которые всё ещё опираются на `surface=action_catalog` и `GET /api/v2/ui/action-catalog/` как рабочий путь.
- Обновить операторские гайды и runbooks, чтобы в них не оставалось инструкций с `/templates?surface=action_catalog` как актуального сценария.
- Добавить регрессионные проверки на templates-only модель для `/templates`, `/extensions`, `/databases`.

## Impact
- Affected specs:
  - `command-result-snapshots`
  - `extensions-action-catalog`
  - `ui-action-catalog-editor`
- Affected code:
  - Backend: `orchestrator/apps/operations/event_subscriber/handlers_worker.py`
  - Backend: `orchestrator/apps/mappings/**`, `orchestrator/apps/api_v2/tests/**`
  - Contracts: `contracts/orchestrator/openapi.yaml`
  - Frontend generated API: `frontend/src/api/generated/**`
  - Frontend/browser tests: `frontend/tests/browser/**`
  - Docs: `docs/**`

## Non-Goals
- Новый dual-path rollout для Action Catalog.
- Возврат или частичная реанимация capability `action_catalog`.
- Изменение business scope manual operations за пределами закрытия выявленных хвостов и рисков.
