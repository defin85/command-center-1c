# Change: UTF-8 OData credentials для кириллицы в metadata и publication path

## Why
Сейчас metadata path в `/api/v2/pools/odata-metadata/catalog` отклоняет логин/пароль с символами вне latin-1 до HTTP-запроса к OData. На практике это блокирует использование service/actor пользователей 1С с кириллическими credentials.

Проблема усиливается тем, что Python `requests` в `HTTPBasicAuth` кодирует строки через `latin1`, из-за чего non-latin credentials ломаются до отправки запроса.

Для 1C web services это противоречит операторскому ожиданию: 1C:Enterprise документирует передачу username/password в UTF-8.

## What Changes
- Для metadata catalog read/refresh перейти на явное формирование `Authorization: Basic ...` из `UTF-8(username:password)` вместо implicit `requests auth=(username, password)`.
- Убрать reject-only ветку для non-latin credentials (`latin-1 unsupported`) в metadata path.
- Сохранить mapping-only политику для metadata auth (`InfobaseUserMapping` only, без fallback на `Database.username/password`).
- Явно зафиксировать классификацию metadata auth-ошибок: `401/403` от OData endpoint возвращаются как fail-closed `ODATA_MAPPING_NOT_CONFIGURED` (без секрета в detail), а не как локальная client-side encoding ошибка.
- Зафиксировать контракт для publication path: credentials из mapping должны проходить transport+worker без потери Unicode-символов (включая кириллицу).
- Добавить тесты на UTF-8 credentials для metadata path и publication transport path (actor/service) и регрессионный тест на ASCII-совместимость.
- Обновить operator-facing диагностику: ошибки должны отражать реальную причину (`missing/ambiguous/rejected by endpoint`), а не локальное ограничение latin-1 клиента.

## Impact
- Affected specs:
  - `organization-pool-catalog`
  - `worker-odata-transport-core`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/metadata_catalog.py`
  - `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py`
  - `go-services/worker/internal/odata/client.go`
  - `go-services/worker/internal/drivers/poolops/publication_transport.go`
  - `go-services/worker/internal/drivers/poolops/*_test.go`

## Dependencies
- Mapping-only auth flow из change `add-03-pool-metadata-driven-policy-builder` должен оставаться неизменным.
- Безопасная эксплуатация предполагает HTTPS/TLS для всех OData endpoint'ов, где передаются Basic credentials.
- Rollout в production разрешён только при подтверждённом HTTPS/TLS на целевых OData endpoint'ах (no-go при plain HTTP).

## Non-Goals
- Не добавляется fallback на legacy `Database.username/password`.
- Не добавляется отдельный compatibility mode с forced latin-1/CP1251 кодировкой.
- Не меняется RBAC-модель или UX экранов `/rbac`, кроме корректной поддержки уже введённых Unicode credentials.
