# Debug Toolkit (autonomous-feedback-loop)

Статус: supplemental runtime toolkit.
Canonical agent-facing onboarding surface: `docs/agent/INDEX.md`.

Этот файл описывает локальную debug-инфраструктуру для быстрого цикла:
`проверка -> гипотеза -> runtime-eval -> фикс -> повторная проверка`.

Все команды запускаются из корня репозитория.

## Быстрый старт

```bash
./scripts/dev/start-all.sh
./debug/probe.sh all
./debug/runtime-inventory.sh
```

Для Beads/Dolt server mode:

```bash
./debug/start-dolt.sh
systemctl --user status beads-dolt.service --no-pager
```

## Инвентарь команд

1. `./debug/runtime-inventory.sh`
Показывает карту рантаймов (entrypoint, health, eval, тест-команды).

2. `./debug/runtime-inventory.sh --json`
Тот же инвентарь в JSON для скриптов/агентов.

3. `./debug/probe.sh all`
Проверяет процесс (`pid`) и HTTP health для рантаймов.

4. `./debug/probe.sh <runtime>`
Точечная проверка одного рантайма:
`orchestrator | event-subscriber | api-gateway | worker | worker-workflows | frontend`.

5. `./debug/restart-runtime.sh <runtime>`
Перезапускает рантайм через `scripts/dev/restart.sh` и сразу делает `probe`.

6. `./debug/eval-django.sh "<python code>"`
Выполняет код в `orchestrator/manage.py shell -c ...` строго через `orchestrator/venv`.

Пример:

```bash
./debug/eval-django.sh "from apps.databases.models import Database; print(Database.objects.count())"
```

7. `./debug/start-chromium-cdp.sh [port] [target_url] [profile_dir] [log_file]`
Поднимает Chromium с CDP (по умолчанию `127.0.0.1:9222`) и гарантирует наличие target-страницы.

8. `./debug/eval-frontend.sh "<js expression>" [url_pattern]`
Автоматически поднимает CDP (если не запущен), затем выполняет JS через `scripts/dev/chrome-debug.py`.

Пример:

```bash
./debug/eval-frontend.sh "document.title"
./debug/eval-frontend.sh "window.location.href" "localhost:15173"
```

9. `./debug/receiver.py --port 3333`
Локальный HTTP receiver для sandbox-интеграций (эндпоинты: `GET /health`, `POST /log`).

10. `./debug/start-dolt.sh`
Переводит текущий Beads-репозиторий в shared Dolt server storage, запускает `systemd --user` сервис `beads-dolt.service` и валидирует доступ через `bd doctor --server`.

Сервис общий для всех Beads-репозиториев и использует каталог:
`~/.local/share/beads/dolt-server`

Инварианты:
- база проекта живёт как реальный каталог `~/.local/share/beads/dolt-server/<database>`;
- `metadata.json` должен содержать `dolt_mode: "server"`;
- при первой миграции legacy Beads Dolt working state из `.beads/` архивируется в `~/.local/share/beads/dolt-backups/`;
- пароль не хранится в репозитории, используется `BEADS_DOLT_PASSWORD`.

## Проверенный live-цикл: `pool run -> dom_lesa`

Проверено `2026-03-24` на живом контуре до automatic alias adoption:
- pool: `top-down-pool`
- pool_id: `fc2588b5-18d7-47a5-bb4c-25fdd280fbe8`
- binding_id: `c011e46a-a109-45b9-a10d-20ca40832c0f`
- topology template: `top-down-template r3`
- execution pack: `top-down-execution-pack r3`
- target database: `dom_lesa_7726446503`
- tenant_id: `4d29aa0d-3fcc-41b2-878a-28f84f6f75ec`

Текущий structural slot contract:
- `root -> organization_1` = `sale`
- `organization_1 -> organization_2` = `receipt_internal`
- `organization_2 -> organization_3` = `receipt_leaf`
- `organization_2 -> organization_4` = `receipt_leaf`

Исторический execution-pack mapping на момент live-прогона:
- `sale -> realization r1`
- `receipt_internal -> receipt r1`
- `receipt_leaf -> receipt r1`

Shipped rollout для topology-aware alias revisions:
- deploy-time default path: `python manage.py migrate` выполняет data migration `0030_adopt_top_down_execution_pack_aliases` и идемпотентно обновляет все tenant-профили `top-down-execution-pack`;
- migration создает alias-aware ревизии для `sale` и reusable `receipt`, затем repin-ит все `PoolWorkflowBinding` на latest execution-pack revision;
- manual remediation path: `python manage.py adopt_top_down_execution_pack_aliases --actor <username> --tenant-slug <tenant-slug>`;
- manual command оставлен для backfill/retry в контурах, где migration не была применена или нужен явный rerun;
- дополнительные опции command: `--binding-profile-code` и `--contract-canonical-id`; по умолчанию используются `top-down-execution-pack` и `osnovnoy`.

Подтвержденный путь:

```bash
export CC1C_BASE_URL=http://localhost:15173
export CC1C_TENANT_ID=4d29aa0d-3fcc-41b2-878a-28f84f6f75ec
export CC1C_POOL_ID=fc2588b5-18d7-47a5-bb4c-25fdd280fbe8
export CC1C_BINDING_ID=c011e46a-a109-45b9-a10d-20ca40832c0f
export CC1C_PERIOD_START=2026-03-24
export CC1C_AMOUNT=88888.88
export CC1C_UI_USER=admin
export CC1C_UI_PASSWORD='...'
export CC1C_ODATA_USER=odata.user
export CC1C_ODATA_PASSWORD='...'
```

UI automation note:
- Для `Pool Runs -> Create -> Starting amount` в `antd` `InputNumber` не использовать `chrome_devtools.fill()`: он дописывает строку поверх formatted value и искажает сумму.
- Надёжный путь для агентного UI-прогона: сфокусировать поле, `Ctrl+A`, затем печатать сумму с клавиатуры и уводить фокус (`Tab`).

1. Получить JWT:

```bash
curl --noproxy '*' -sS -H 'Content-Type: application/json' \
  -d "{\"username\":\"$CC1C_UI_USER\",\"password\":\"$CC1C_UI_PASSWORD\"}" \
  "$CC1C_BASE_URL/api/token"
```

2. Создать `safe` run:

```bash
curl --noproxy '*' -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID" \
  -H 'Content-Type: application/json' \
  -d "{\"pool_id\":\"$CC1C_POOL_ID\",\"pool_workflow_binding_id\":\"$CC1C_BINDING_ID\",\"direction\":\"top_down\",\"period_start\":\"$CC1C_PERIOD_START\",\"run_input\":{\"starting_amount\":\"$CC1C_AMOUNT\"},\"mode\":\"safe\"}" \
  "$CC1C_BASE_URL/api/v2/pools/runs/"
```

3. Подтвердить публикацию. `Idempotency-Key` обязателен:

```bash
curl --noproxy '*' -sS -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID" \
  -H "Idempotency-Key: debug-confirm-$(date +%s)" \
  "$CC1C_BASE_URL/api/v2/pools/runs/$RUN_ID/confirm-publication/"
```

4. Поллить report до terminal state:

```bash
curl --noproxy '*' -sS \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID" \
  "$CC1C_BASE_URL/api/v2/pools/runs/$RUN_ID/report/"
```

5. Проверить созданный документ через OData по `Ref_Key`:

```bash
curl --noproxy '*' -k -sS \
  -u "$CC1C_ODATA_USER:$CC1C_ODATA_PASSWORD" \
  "https://192.168.32.143/dom_lesa_7726446503/odata/standard.odata/Document_%D0%9F%D0%BE%D1%81%D1%82%D1%83%D0%BF%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5%D0%A2%D0%BE%D0%B2%D0%B0%D1%80%D0%BE%D0%B2%D0%A3%D1%81%D0%BB%D1%83%D0%B3(guid%27$DOC_REF_KEY%27)?$format=json"
```

Что реально увидел:
- `POST /api/v2/pools/runs/` создал run `2c27dcf6-e2d9-4fbf-a9f0-9c9de92b33ff`
- `confirm-publication` вернул `202 Accepted`
- `GET /api/v2/pools/runs/2c27dcf6-e2d9-4fbf-a9f0-9c9de92b33ff/report/` в финале показал:
  - `status = published`
  - `workflow_status = completed`
  - `approval_state = approved`
  - `publication_step_state = completed`
- worker log подтвердил реальные side effects:
  - `POST /dom_lesa_7726446503/odata/standard.odata//Document_ПоступлениеТоваровУслуг -> 201`
  - `PATCH /dom_lesa_7726446503/odata/standard.odata//Document_ПоступлениеТоваровУслуг(guid'b0a52b52-274e-11f1-9d20-000c29b79fe4') -> 200`
- OData single-entity GET подтвердил:
  - `Ref_Key = b0a52b52-274e-11f1-9d20-000c29b79fe4`
  - `Number = 0000-000001`
  - `Date = 2026-03-24T00:00:00`
  - `Posted = true`
  - `СуммаДокумента = 77777.77`

После фикса:
- `Date` в published document теперь берётся из `PoolRun.period_start` и сериализуется как `YYYY-MM-DDT00:00:00`.
- `compiled_document_policy_slots` в runtime projection по-прежнему показывают исходный policy snapshot; подмена делается на этапе materialization document plan artifact.
- `ДатаВходящегоДокумента` пока остаётся из policy sample и не привязана к `period_start`.

Нюанс:
- сразу после `confirm-publication` report может кратковременно показывать неактуальную промежуточную проекцию; верифицированный способ — поллить report и, при разборе инцидента, сверять `PoolPublicationAttempt`/worker log.

## Подготовленный live/dev-цикл: `batch-backed run -> factual workspace`

Статус на `2026-03-28`:
- `receipt batch -> distribution/publication -> run report` идёт по live path;
- operator route `/pools/factual` и public factual API опубликованы;
- `GET /api/v2/pools/factual/workspace/` теперь сам поднимает worker-backed factual refresh на default path, если checkpoint отсутствует или протух;
- manual review идёт через `POST /api/v2/pools/factual/review-actions/`, без `dev-bridge` для штатного operator path.
- receipt intake для default operator path идёт через `/pools/runs` → `Create canonical batch` → linked inspect/run context, а не через ручной ввод batch UUID.
- для settlement focus всегда сохраняй `quarter_start` в `/pools/factual`; без него workspace может показать не тот quarter snapshot.
- manual reconcile для late correction проверяй через `action=reconcile`, а attributable items через `action=attribute`, затем переполли workspace summary и review queue.

Дополнительно подтверждено на `2026-03-29`:
- published-surfaces preflight возвращает `decision=go` на pilot path при наличии published OData surfaces;
- live path `receipt batch -> linked safe run -> confirm-publication -> report=status=published -> factual workspace summary` проходит на default runtime wiring;
- для live contour обязательны активный public `Pool Schema Template` и actor/service mapping, достаточный для publication/factual OData calls в целевых ИБ;
- acceptance point для safe-mode публикации: поллить report до `publication_step_state=completed` или `status=published`, а не оценивать первый промежуточный snapshot сразу после `confirm-publication`.

Минимальные env vars:

```bash
export CC1C_BASE_URL=http://localhost:15173
export CC1C_TENANT_ID=<tenant-uuid>
export CC1C_POOL_ID=<pool-uuid>
export CC1C_BINDING_ID=<workflow-binding-uuid>
export CC1C_BATCH_ID=<receipt-batch-uuid>
export CC1C_START_ORGANIZATION_ID=<organization-uuid>
export CC1C_EDGE_ID=<pool-edge-version-uuid>
export CC1C_SCHEMA_TEMPLATE_ID=<schema-template-uuid>
export CC1C_PERIOD_START=2026-01-01
export CC1C_PERIOD_END=2026-03-31
export CC1C_UI_USER=admin
export CC1C_UI_PASSWORD='...'
```

Как быстро подобрать `batch/start organization/edge` для пилотного пула:

```bash
./debug/eval-django.sh "from apps.intercompany_pools.models import PoolBatch, PoolEdgeVersion; print(list(PoolBatch.objects.filter(pool_id='$CC1C_POOL_ID').order_by('-created_at').values('id','period_start','start_organization_id','source_reference')[:5])); print(list(PoolEdgeVersion.objects.filter(pool_id='$CC1C_POOL_ID').order_by('effective_from').values('id','parent_node__organization__name','child_node__organization__name')[:10]))"
```

1. Получить JWT:

```bash
ACCESS_TOKEN=$(curl --noproxy '*' -sS -H 'Content-Type: application/json' \
  -d "{\"username\":\"$CC1C_UI_USER\",\"password\":\"$CC1C_UI_PASSWORD\"}" \
  "$CC1C_BASE_URL/api/token" | python -c "import json,sys; print(json.load(sys.stdin)['access'])")
```

2. Перед расширением pilot cohort прогнать published-surfaces preflight на тех же ИБ:

```bash
cd orchestrator && ./venv/bin/python manage.py preflight_pool_factual_sync \
  --pool-id "$CC1C_POOL_ID" \
  --quarter-start "$CC1C_PERIOD_START" \
  --requested-by-username "$CC1C_UI_USER" \
  --database-id <pilot-db-uuid> \
  --json \
  --strict
```

Ожидаемое поведение:
- metadata refresh проходит через canonical Command Center path;
- decision `go` означает, что required published surfaces доступны и live bounded read probe завершился без direct DB path;
- успешный probe подтверждай по `live_probe.boundary_probes.<surface>.probe_ok=true`, а `boundary_reads.<surface>` трактуй только как row-count snapshot, который может быть `0` на пустом bounded slice;
- JSON output сохраняем как pilot/preflight evidence для rollout gate `0.3`; reference bundle см. в `openspec/changes/archive/2026-03-29-add-pool-factual-balance-monitoring/artifacts/2026-03-29-pilot-preflight-evidence.json`.

3. Создать canonical `receipt` batch и получить связанный `safe` `top_down` run:

```bash
RECEIPT_RESPONSE=$(curl --noproxy '*' -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID" \
  -H 'Content-Type: application/json' \
  -d "{\"pool_id\":\"$CC1C_POOL_ID\",\"batch_kind\":\"receipt\",\"source_type\":\"schema_template_upload\",\"schema_template_id\":\"$CC1C_SCHEMA_TEMPLATE_ID\",\"pool_workflow_binding_id\":\"$CC1C_BINDING_ID\",\"start_organization_id\":\"$CC1C_START_ORGANIZATION_ID\",\"period_start\":\"$CC1C_PERIOD_START\",\"period_end\":\"$CC1C_PERIOD_END\",\"source_reference\":\"receipt-debug\",\"json_payload\":[{\"inn\":\"730000000001\",\"amount\":\"100.00\",\"external_id\":\"debug-receipt-001\"}]}" \
  "$CC1C_BASE_URL/api/v2/pools/batches/")
CC1C_BATCH_ID=$(printf '%s' "$RECEIPT_RESPONSE" | python -c "import json,sys; print(json.load(sys.stdin)['batch']['id'])")
RUN_ID=$(printf '%s' "$RECEIPT_RESPONSE" | python -c "import json,sys; print(json.load(sys.stdin)['run']['id'])")
```

4. Подтвердить публикацию и дополлить report до terminal execution state:

```bash
curl --noproxy '*' -sS -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID" \
  -H "Idempotency-Key: factual-confirm-$(date +%s)" \
  "$CC1C_BASE_URL/api/v2/pools/runs/$RUN_ID/confirm-publication/"
```

```bash
curl --noproxy '*' -sS \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID" \
  "$CC1C_BASE_URL/api/v2/pools/runs/$RUN_ID/report/"
```

5. Открыть operator-facing factual route из run context:

```bash
printf '%s\n' "$CC1C_BASE_URL/pools/factual?pool=$CC1C_POOL_ID&run=$RUN_ID&quarter_start=$CC1C_PERIOD_START&focus=settlement&detail=1"
printf '%s\n' "$CC1C_BASE_URL/pools/factual?pool=$CC1C_POOL_ID&run=$RUN_ID&quarter_start=$CC1C_PERIOD_START&focus=review&detail=1"
```

6. Дополлить factual workspace API до появления checkpoint/sync summary:

```bash
curl --noproxy '*' -sS \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID" \
  "$CC1C_BASE_URL/api/v2/pools/factual/workspace/?pool_id=$CC1C_POOL_ID&quarter_start=$CC1C_PERIOD_START"
```

Ожидаемое поведение:
- при первом вызове endpoint создаёт/подхватывает `PoolFactualSyncCheckpoint` и стартует worker-backed sync;
- при повторных вызовах возвращает backend-fed summary / settlement / review queue;
- если checkpoint свежий или уже `running`, лишний workflow не стартует;
- `summary.backlog_total` присутствует в payload и не скрывает stale/read-backlog состояние за одним только `source_availability`;
- reference snapshot для live default path см. в `openspec/changes/archive/2026-03-29-add-pool-factual-balance-monitoring/artifacts/2026-03-29-live-default-path-evidence.md`.

7. Открыть operator-facing factual route из browser и дождаться backend-fed summary:

```bash
printf '%s\n' "$CC1C_BASE_URL/pools/factual?pool=$CC1C_POOL_ID&run=$RUN_ID&quarter_start=$CC1C_PERIOD_START&focus=settlement&detail=1"
printf '%s\n' "$CC1C_BASE_URL/pools/factual?pool=$CC1C_POOL_ID&run=$RUN_ID&quarter_start=$CC1C_PERIOD_START&focus=review&detail=1"
```

8. Выполнить operator action по review item через public API:

```bash
curl --noproxy '*' -sS -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID" \
  -H 'Content-Type: application/json' \
  -d "{\"review_item_id\":\"<review-item-uuid>\",\"action\":\"reconcile\",\"note\":\"debug factual reconcile\"}" \
  "$CC1C_BASE_URL/api/v2/pools/factual/review-actions/"
```

Rollout telemetry и actionable alerts, которые должны быть зелёными перед расширением cohort:
- `cc1c_orchestrator_pool_factual_read_freshness_lag_seconds`: целевой budget `<= 120s`; `warning` при превышении budget, `critical` при `>= 600s` или если есть `blocked_external_sessions` / `unavailable`.
- `cc1c_orchestrator_pool_factual_read_backlog_total`: считает overdue/stale checkpoints read lane; `critical`, если backlog достигает rollout `global_read_cap=8`, иначе `warning`.
- `cc1c_orchestrator_pool_factual_review_pending_total{reason="unattributed"}` и `cc1c_orchestrator_pool_factual_review_pending_amount_with_vat{reason="unattributed"}`: любой ненулевой объём означает operator action `attribute` до расширения cohort.
- `cc1c_orchestrator_pool_factual_review_pending_total{reason="late_correction"}` и `cc1c_orchestrator_pool_factual_review_attention_required_total{reason="late_correction"}`: любой pending late correction считается `critical` и требует manual reconcile до period close / rollout widening.
- `cc1c_orchestrator_pool_factual_actionable_alert_state{alert_code,severity}`: агрегированный сигнал для four mandatory rollout alerts `freshness_lag`, `read_backlog`, `unattributed_volume`, `late_correction_queue`.

Что делать по сигналам:
- `freshness_lag`: проверить published 1C availability, `sessions_deny`, maintenance window и состояние read checkpoints; intake автоматически не выключать.
- `read_backlog`: сначала дренировать overdue checkpoints или уменьшить rollout cohort; не лечить backlog отключением batch intake по умолчанию.
- `unattributed_volume`: открыть `/pools/factual?...focus=review`, разметить документы и только после этого расширять rollout.
- `late_correction_queue`: выполнить manual reconcile и явно зафиксировать решение оператора до period close и следующего cohort step.

Failure-isolation policy:
- backlog/staleness/attention signals в `read/projection` и `reconcile/review` переводят эти подсистемы в degraded state, но сами по себе НЕ выключают `intake`;
- `intake` может перейти в `paused_by_operator` только после явного решения оператора; автоматический stop из telemetry/alerts не допускается;
- при degraded factual/read или review контуре default action: поднять alerts, удержать `intake` доступным и отдельно решить, нужен ли ручной pause для rollout cohort.

Что считать успехом на текущем этапе:
- `create run` и `confirm-publication` проходят по batch-backed пути без manual amount payload;
- report доходит до execution-terminal state;
- `/pools/factual?...focus=settlement` и `/pools/factual?...focus=review` открываются как отдельный workspace из того же pool/run context;
- `GET /api/v2/pools/factual/workspace/` возвращает backend-fed summary / settlements / review queue и при необходимости сам поднимает refresh workflow;
- `POST /api/v2/pools/factual/review-actions/` переводит review item в terminal review status без мутации `PoolRun.status`.

## Важные замечания

1. Для `eval-django.sh` обязателен `orchestrator/venv` с установленным Django.
2. Для `eval-frontend.sh` нужен Python-пакет `websockets` (используется `scripts/dev/chrome-debug.py`).
3. `chrome-debug.py` и интерактивный MCP chrome-devtools не стоит использовать одновременно на одной вкладке/CDP-сессии.
4. Для Beads/Dolt server mode ожидается доступный `systemd --user`; состояние сервиса проверяется через `systemctl --user status beads-dolt.service`.
