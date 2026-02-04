# Change: Расширить канонический инвентарь расширений и добавить фильтр по базе в /extensions

## Why
Сейчас “каноническая” (стабильная) структура extensions inventory содержит только минимальные поля (`name`, `version?`, `is_active?`). Из-за этого невозможно опираться на канонический слой для UI/аналитики, где нужно видеть дополнительные признаки расширения (например `purpose` и режимы безопасности), без обращения к “сырому” stdout и без привязки к формату драйвера.

Кроме того, экран `/extensions` (aggregated overview) не позволяет ограничить выборку “списком расширений, встречающихся в конкретной базе”, что затрудняет диагностику и сравнение.

## What Changes
- Канонический `extensions_inventory` расширяется полями:
  - `name` (обязательно)
  - `purpose` (опционально)
  - `is_active` (опционально)
  - `safe_mode` (опционально)
  - `unsafe_action_protection` (опционально)
  - (`version` остаётся опциональным, но не является обязательным для UI)
- `/api/v2/extensions/overview/` получает новый query-параметр `database_id` (опционально):
  - семантика: ограничивает *набор имён расширений в выдаче* теми, которые присутствуют в snapshot выбранной базы;
  - агрегированные счётчики по этим расширениям продолжают считаться по всем доступным пользователю базам (как и раньше).
- UI `/extensions`:
  - добавляет фильтр выбора базы (по доступным пользователю базам);
  - фильтр влияет только на верхнюю агрегированную таблицу;
  - в drill-down drawer используется отдельная (независимая) фильтрация по базе.

## Impact
- Affected specs:
  - `extensions-overview` (добавить фильтр по базе, уточнить минимальный набор полей snapshot/каноники)
  - `extensions-plan-apply` (уточнить, что канонический `extensions_inventory` включает дополнительные поля)
- Affected code (ожидаемо):
  - Orchestrator: `apps/mappings/extensions_inventory.py`, `apps/api_v2/views/extensions.py`
  - Frontend: `frontend/src/pages/Extensions/Extensions.tsx`, `frontend/src/api/queries/extensions.ts`
  - Contracts/OpenAPI: обновление контрактов для нового query param `database_id` на `/api/v2/extensions/overview/` и регенерация клиентов (если контракт-first применяется к этому endpoint)

## Non-Goals
- Переработка full snapshot (`snapshot.extensions`) или формата stdout/stderr.
- Новые доменные поля beyond перечисленных (например `hash_sum`), если не требуется явно.

