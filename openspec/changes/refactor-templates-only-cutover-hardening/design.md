## Context
После cutover на templates-only в кодовой базе остались смешанные артефакты двух моделей: часть runtime metadata уже перешла на `manual_operation` + `template_id`, но completion path и часть контрактного/тестового слоя всё ещё допускают поведение, не полностью соответствующее зафиксированной модели.

Проблемные зоны:
- completion snapshot path не закрепляет mapping детерминированно по pinned reference;
- public contract hygiene не доведён до конца (legacy schemas в OpenAPI/codegen);
- тесты и docs частично сохраняют legacy сценарии, создавая риск регрессии.

## Goals / Non-Goals
- Goals:
  - Гарантировать детерминированную completion нормализацию по pinned mapping metadata.
  - Зафиксировать чистый templates-only публичный контракт без legacy Action Catalog артефактов.
  - Устранить legacy ожидания из тестов и операторских инструкций.
- Non-Goals:
  - Расширение домена manual operations новыми operation keys.
  - Временные fallback-адаптеры `action_id -> manual_operation`.

## Decisions
### 1. Completion mapping резолвится только по pinned ref
- Источник mapping для completion: `mapping_spec_ref` из metadata плана/операции.
- Использование «текущего опубликованного mapping» как fallback не допускается.
- При недоступном pinned mapping completion сохраняет raw/normalized данные и явные diagnostics, без тихой подмены версии.

### 2. Result contract проверяется на completion
- `result_contract` из metadata обязателен для contract-aware completion path.
- Canonical payload проходит валидацию против contract schema.
- Ошибки валидации сохраняются в diagnostics (append-only), не уничтожая raw snapshot.

### 3. Decommission hygiene на уровне OpenAPI и codegen
- Публичный OpenAPI не содержит legacy Action Catalog response schemas.
- Generated frontend API не должен экспортировать legacy модели Action Catalog.
- Decommission endpoint `GET /api/v2/ui/action-catalog/` остаётся только как стабильный 404-контракт, без возврата рабочей семантики.

### 4. Templates-only testing/docs baseline
- Browser tests для ключевых экранов (`/templates`, `/extensions`, `/databases`) не используют `surface=action_catalog` и не ожидают controls legacy editor.
- Операторские гайды не должны направлять в legacy route как рабочий путь.

## Risks / Trade-offs
- Риск: жёсткий fail-closed при проблеме pinned mapping увеличит число явных ошибок в short-term.
  - Митигация: подробные diagnostics + точные error codes + тесты edge-case.
- Риск: удаление legacy OpenAPI schemas может затронуть потребителей неактуальных generated типов.
  - Митигация: release notes + синхронный codegen + проверка usage по репозиторию.
- Риск: массовая правка browser tests увеличит шум изменений.
  - Митигация: сегментация PR по подсистемам и сохранение только templates-only assertions.

## Migration Plan
1. Обновить OpenSpec delta-specs и зафиксировать hardening-контракт.
2. Внести backend изменения completion mapping/contract validation + тесты.
3. Очистить OpenAPI legacy components и перегенерировать frontend API.
4. Переписать legacy browser/backend тесты на templates-only flow.
5. Обновить docs/runbooks/release notes.
6. Прогнать релевантные проверки и подтвердить отсутствие ссылок на legacy рабочий path.

## Open Questions
- Отсутствуют.
