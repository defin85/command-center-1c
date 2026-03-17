# 2026-02-15: Pools API breaking change (`source_hash` removal) + UI full pool management

## Что изменилось

- `POST /api/v2/pools/runs/` больше **не принимает** поле `source_hash`.
- `POST /api/v2/pools/runs/` и `POST /api/v2/pools/workflow-bindings/preview/` без `pool_workflow_binding_id` отклоняются fail-closed, даже если по selector есть ровно один кандидат.
- Create-run контракт использует `run_input` как source-of-truth для входных данных.
- Create-run контракт использует `pool_workflow_binding_id` как pinned binding reference для workflow-centric запуска.
- Selector matching допустим только для UI prefill/assistive hint до submit.
- Idempotency для create-run теперь считается по:
  - `pool_id`
  - `pool_workflow_binding_id`
  - `pool_workflow_binding_revision` (attachment revision)
  - `binding_profile_revision_id` (pinned reusable revision)
  - `period_start`/`period_end`
  - `direction`
  - `canonicalized(run_input)`
- Смена `pool_workflow_binding_id`, `pool_workflow_binding_revision` или `binding_profile_revision_id` создаёт новый idempotency fingerprint.
- Read-контракт run:
  - поле `source_hash` удалено из публичного payload;
  - добавлены `run_input` (`object | null`) и `input_contract_version` (`run_input_v1 | legacy_pre_run_input`).
- Для topology mutating включён optimistic concurrency:
  - `GET /api/v2/pools/{pool_id}/graph/?date=...` возвращает `version`;
  - `POST /api/v2/pools/{pool_id}/topology-snapshot/upsert/` требует этот `version` и возвращает `409` (`TOPOLOGY_VERSION_CONFLICT`) при stale token.

## Миграция интеграций (обязательно)

1. Уберите `source_hash` из payload create-run.
2. Передавайте `pool_workflow_binding_id` и direction-specific `run_input` и для `POST /api/v2/pools/workflow-bindings/preview/`, и для `POST /api/v2/pools/runs/`.
3. Не рассчитывайте на server-side selector fallback: если binding не выбран, API вернёт `POOL_WORKFLOW_BINDING_REQUIRED` в `application/problem+json`.
4. Для идемпотентного retry повторяйте тот же `pool_workflow_binding_id`, тот же `pool_workflow_binding_revision` и тот же `binding_profile_revision_id`; смена любого из этих полей создаёт новый run fingerprint.
5. Обновите обработку ошибок create-run/topology mutating на `application/problem+json` (`type`, `title`, `status`, `detail`, `code`).
6. Для topology update всегда делайте round-trip:
   - сначала read (`graph`) и берите `version`;
   - затем upsert с тем же `version`.

## Пример create-run: было / стало

### Было (устарело)

```json
{
  "pool_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  "direction": "bottom_up",
  "period_start": "2026-01-01",
  "source_hash": "legacy-hash",
  "mode": "safe"
}
```

### Стало

```json
{
  "pool_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  "pool_workflow_binding_id": "binding-top-down-v3",
  "direction": "top_down",
  "period_start": "2026-01-01",
  "run_input": {
    "starting_amount": "100.00"
  },
  "mode": "safe"
}
```

## Совместимость historical runs

- Historical runs, созданные до cutover, продолжают читаться.
- Для них API возвращает:
  - `run_input: null`
  - `input_contract_version: "legacy_pre_run_input"`

## Rollback/диагностика

- Если после деплоя наблюдаются конфликты create-run идемпотентности:
  - проверьте, что клиент отправляет корректный `run_input` и не смешивает старый/новый контракт.
- Если topology update возвращает `409 TOPOLOGY_VERSION_CONFLICT`:
  - перечитайте graph и повторите update с новым `version`.
