# Change: Перепроектировать /extensions под policy-флаги и actions (active/safe_mode/unsafe_action_protection)

## Why
Текущий `/extensions` показывает агрегированные счетчики `active/inactive` (и частично выводит некоторые канонические поля), но:
- Для оператора важнее видеть **желаемое** состояние (policy) и дрейф по базам, чем распределение `active/inactive`.
- Нужна единая модель **трёх флагов** (`active`, `safe_mode`, `unsafe_action_protection`) с одинаковой семантикой агрегации и отображения.
- Управление этими флагами должно выполняться **через actions** (action catalog), с preflight/preview и безопасной массовой применимостью.

## What Changes
- UI `/extensions`:
  - вместо столбцов `Active`/`Inactive` отображает один булевый столбец `Active (policy)` (и аналогичные `Safe mode (policy)`, `Unsafe action protection (policy)`).
  - добавляет унифицированный индикатор дрейфа/смешанного состояния по каждому флагу (например `mixed`/`unknown`/`drift_count`).
  - действия управления флагами доступны через `Actions…` (с учётом tenant/staff ограничений).
- API `/api/v2/extensions/overview/`:
  - добавляет унифицированную структуру агрегации флагов по расширению (policy + observed + drift) для `active/safe_mode/unsafe_action_protection`.
  - сохраняет текущую семантику `database_id`: ограничивает *набор имён* по snapshot выбранной базы, но агрегаты считаются по всем доступным базам.
- New capability: `extensions-flags-policy`
  - хранение tenant-scoped policy для флагов по `extension_name`.
  - API для чтения/изменения policy (mutating операции требуют явного tenant context для staff).
- Action catalog:
  - вводится зарезервированный capability для применения policy к списку баз (bulk), с drift check и подробным результатом per-db.

## Impact
- Affected specs:
  - `extensions-overview` (UI+API: policy-колонки и унифицированная агрегация флагов)
  - `extensions-action-catalog` (новый reserved capability для применения флагов)
  - `extensions-plan-apply` (plan/apply для действия применения флагов, drift check, snapshot update)
  - **NEW**: `extensions-flags-policy` (tenant-scoped policy API/хранилище)
- Affected code (ожидаемо):
  - Orchestrator: `apps/api_v2/views/extensions.py`, новый storage/API для policy, планировщик bulk-операций
  - Frontend: `frontend/src/pages/Extensions/Extensions.tsx` + UI для запуска action (preview/apply)
  - Contracts/OpenAPI: `contracts/orchestrator/openapi.yaml` + регенерация клиентов/типов

## Risks / Mitigations (ключевые)
- Staff cross-tenant режим делает policy неоднозначным (какой tenant менять/применять).
  - Митигация: mutating операции (edit policy / apply flags) требуют явного tenant context (`X-CC1C-Tenant-ID`) для staff; без него actions в UI disabled и API отвечает fail-closed.
- Snapshot freshness: после apply UI может показывать “старое”.
  - Митигация: apply обязано обновлять snapshot по маркеру snapshot-producing (как в `extensions-plan-apply`) и/или триггерить refresh.
- Partial failures на больших пулах баз.
  - Митигация: bulk создаёт N tasks, возвращает per-db результаты и допускает retry для failed subset.
- Разные версии 1С/драйверов могут не поддерживать установку флагов.
  - Митигация: fail-closed validation action catalog по driver catalog; если команда/параметры недоступны — action скрывается/запуск блокируется.

## Non-Goals
- Миграция/удаление существующих полей ответа `extensions/overview` в рамках этого change (возможна отдельная deprecation-работа позже).
- Изменение формата сырых worker payload beyond текущего snapshot shape.
- Попытка “синхронизировать” policy автоматически без явных действий оператора (только через Adopt/Apply flows).

