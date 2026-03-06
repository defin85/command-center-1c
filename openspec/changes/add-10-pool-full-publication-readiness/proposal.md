# Change: Прозрачный full-cycle top-down run для Pools (минимум документов, полное заполнение, UI + OData verify)

## Why
На dev нельзя надёжно прогнать операторский сценарий top-down распределения так, чтобы:
- создавался минимально необходимый набор документов;
- каждый созданный документ был полно заполнен по реквизитам и табличным частям;
- результат был прозрачно виден в UI и проверяем через OData.

Фактически наблюдаются системные блокеры: пустой master-data/bindings, неполные `document_policy`, неполная проекция publication attempts и отсутствие live UI acceptance path без моков.

## What Changes
- Добавить единый readiness-контур для pool run с machine-readable блокерами до фактической публикации:
  - master-data completeness и Organization->Party binding coverage;
  - полнота `document_policy` для режима `minimal_documents_full_payload`;
  - готовность OData verification.
- Добавить контракт режима `минимум документов, полное заполнение`:
  - минимизация числа документов допускается только при сохранении полноты payload каждого документа;
  - fail-closed при отсутствии обязательных реквизитов или строк табличных частей.
- Ужесточить прозрачность execution/read-model:
  - агрегация publication attempts из всех atomic `publication_odata` узлов;
  - детерминированное отображение `readiness_blockers` и `verification_status` в run inspection/report.
- Добавить OData verifier контракт по опубликованным refs:
  - доступ через UTF-8 Basic auth;
  - сверка обязательных полей и табличных частей против completeness profile.
- Зафиксировать live UI acceptance path для dev:
  - run create/confirm/retry проходит через реальный API без тестовых моков;
  - оператор видит блокеры и статус верификации в одном прозрачном процессе.

## Impact
- Affected specs:
  - `pool-distribution-runs`
  - `pool-document-policy`
  - `pool-master-data-hub`
  - `pool-master-data-hub-ui`
  - `pool-odata-publication`
  - `pool-workflow-execution-core`
- Affected code:
  - `orchestrator/apps/intercompany_pools/*` (readiness gate, policy/fullness checks, report model)
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/api_internal/views_workflows.py`
  - `go-services/worker/internal/drivers/poolops/*` (attempt/result compatibility path)
  - `frontend/src/pages/Pools/*` и browser e2e
  - backend integration tests + UI live e2e + OData verification tests
