# Change: Добавить explicit eligibility controls для `cluster_all` в pool master-data sync

## Why
Текущий manual sync launch трактует `cluster_all` как все `Database` с тем же `cluster_id`. На живом tenant это небезопасно: в одном кластере могут оказаться ИБ другой конфигурации, пилотные или служебные базы, а также базы, которые не должны участвовать в данном master-data контуре. Оператор сегодня не может выразить это в продукте и вынужден помнить исключения вручную или уходить в `database_set`.

Для fail-closed поведения системе недостаточно знать, что база технически отвечает по OData. Ей нужен явный ответ на другой вопрос: входит ли эта база в operator-approved cluster-wide scope для pool master-data sync. Этот допуск должен задаваться явно через UI и блокировать `cluster_all`, пока по каждой базе кластера не принято операторское решение.

## What Changes
- Ввести per-database explicit eligibility state для участия в `cluster_all` pool master-data sync:
  - `eligible` — база участвует в `cluster_all`;
  - `excluded` — база явно исключена из `cluster_all`;
  - `unconfigured` — решение не принято; `cluster_all` блокируется fail-closed.
- Расширить `/databases` operator-facing surface управлением этим state, включая explainers и текущий readiness summary как отдельный слой диагностики.
- Изменить server-side target resolution для `cluster_all`:
  - в immutable target snapshot попадают только `eligible` базы;
  - `excluded` базы не попадают в snapshot и публикуются как явные resolution diagnostics;
  - наличие хотя бы одной `unconfigured` базы в выбранном кластере отклоняет create request без создания parent launch.
- Расширить `Sync` zone на `/pools/master-data` diagnostics/handoff:
  - launcher показывает summary по `eligible/excluded/unconfigured` для выбранного кластера;
  - submit блокируется, если в кластере остались `unconfigured` базы;
  - UI даёт явный handoff в `/databases` для исправления eligibility.
- Сохранить separation of concerns:
  - eligibility определяет business participation в `cluster_all`;
  - runtime readiness, OData health, service mapping и policy gates остаются отдельными проверками и не auto-flip eligibility state.

## Impact
- Affected specs:
  - `pool-master-data-sync`
  - `pool-master-data-hub-ui`
  - `database-metadata-management-ui`
- Affected code:
  - `orchestrator/apps/intercompany_pools/master_data_sync_launch_service.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data_sync.py`
  - `orchestrator/apps/api_v2/views/databases.py`
  - `orchestrator/apps/databases/**`
  - `frontend/src/pages/Pools/masterData/SyncLaunchDrawer.tsx`
  - `frontend/src/pages/Databases/**`
  - `frontend/src/api/**`
  - `contracts/**`
- Affected runtime boundaries:
  - `frontend -> api-gateway -> orchestrator`
  - change не должен вводить второй cluster-targeting runtime вне существующего manual sync launch path

## Non-Goals
- Автоопределение eligibility по `odata_url`, `config_name`, `driver`, `username`, health probe или иным эвристикам.
- Изменение semantics `database_set`; explicit database selection остаётся отдельным operator override path.
- Автоматическое включение/исключение базы из `cluster_all` по временным runtime ошибкам.
- Generic cross-domain eligibility framework для всех cluster-scoped features проекта.
- Автоматическое массовое исправление `cluster_all` membership без operator decision в `/databases`.

## Assumptions
- Решение о participation в `cluster_all` принимается оператором или staff в tenant scope и должно храниться как machine-readable per-database state.
- `excluded` означает intentional non-membership в cluster-wide master-data sync и не должен блокировать `cluster_all`.
- Existing clusters могут содержать смешанные базы; после rollout `cluster_all` может временно блокироваться до тех пор, пока оператор явно не разрешит `unconfigured` состояния.
