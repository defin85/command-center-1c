# Debug Toolkit (autonomous-feedback-loop)

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
- при первой миграции legacy `.beads/dolt` архивируется в `~/.local/share/beads/dolt-backups/`;
- пароль не хранится в репозитории, используется `BEADS_DOLT_PASSWORD`.

## Проверенный live-цикл: `pool run -> dom_lesa`

Проверено `2026-03-24` на живом контуре:
- pool: `top-down-pool`
- pool_id: `fc2588b5-18d7-47a5-bb4c-25fdd280fbe8`
- binding_id: `c011e46a-a109-45b9-a10d-20ca40832c0f`
- target database: `dom_lesa_7726446503`
- tenant_id: `4d29aa0d-3fcc-41b2-878a-28f84f6f75ec`

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
- `POST /api/v2/pools/runs/` создал run `5b696ed1-359a-4187-afa9-752437c15d21`
- `confirm-publication` вернул `202 Accepted`
- `GET /api/v2/pools/runs/5b696ed1-359a-4187-afa9-752437c15d21/report/` в финале показал:
  - `status = published`
  - `workflow_status = completed`
  - `approval_state = approved`
  - `publication_step_state = completed`
- worker log подтвердил реальные side effects:
  - `POST /dom_lesa_7726446503/odata/standard.odata//Document_ПоступлениеТоваровУслуг -> 201`
  - `PATCH /dom_lesa_7726446503/odata/standard.odata//Document_ПоступлениеТоваровУслуг(guid'f005e12c-274b-11f1-9d20-000c29b79fe4') -> 200`
- OData single-entity GET подтвердил:
  - `Ref_Key = f005e12c-274b-11f1-9d20-000c29b79fe4`
  - `Number = 0000-000040`
  - `Date = 2023-10-03T12:00:00`
  - `Posted = true`
  - `СуммаДокумента = 88888.88`

Нюанс:
- сразу после `confirm-publication` report может кратковременно показывать неактуальную промежуточную проекцию; верифицированный способ — поллить report и, при разборе инцидента, сверять `PoolPublicationAttempt`/worker log.

## Важные замечания

1. Для `eval-django.sh` обязателен `orchestrator/venv` с установленным Django.
2. Для `eval-frontend.sh` нужен Python-пакет `websockets` (используется `scripts/dev/chrome-debug.py`).
3. `chrome-debug.py` и интерактивный MCP chrome-devtools не стоит использовать одновременно на одной вкладке/CDP-сессии.
4. Для Beads/Dolt server mode ожидается доступный `systemd --user`; состояние сервиса проверяется через `systemctl --user status beads-dolt.service`.
