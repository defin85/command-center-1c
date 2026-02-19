# Rollout checklist + rollback drill: update-pool-publication-odata-auth-mapping

Дата: 2026-02-18

## 1. Цель
- Выполнить cutover `pool.publication_odata` на mapping-only auth через `/rbac` (Infobase Users).
- Зафиксировать обязательный operator sign-off для `staging` и `prod`.

## 2. Preconditions (обязательные перед релизным окном)
- [ ] Пройден preflight coverage report:
  ```bash
  cd /home/egor/code/command-center-1c/orchestrator
  ./venv/bin/python manage.py preflight_pool_publication_auth_mapping \
    --strategy both \
    --actor-username <operator_username> \
    --period-date <YYYY-MM-DD> \
    --json --strict
  ```
- [ ] `openspec validate update-pool-publication-odata-auth-mapping --strict --no-interactive` = PASS.
- [ ] Backend/worker/frontend regression suite = PASS.
- [ ] Назначены ответственные: orchestrator, worker, frontend, ops/operator.

## 3. Staging checklist
- [ ] Развернуть candidate build (orchestrator + worker + frontend).
- [ ] Проверить `/rbac` mappings для target databases (actor + service, если требуется fallback режим).
- [ ] Выполнить smoke e2e сценарий публикации:
  - actor success;
  - missing mapping fail-closed (`ODATA_MAPPING_NOT_CONFIGURED`);
  - ambiguous mapping fail-closed (`ODATA_MAPPING_AMBIGUOUS`).
- [ ] Проверить telemetry labels в логах:
  - `actor_success`
  - `service_success`
  - `missing_mapping`
  - `ambiguous_mapping`
  - `invalid_auth_context`
- [ ] Выполнить rollback drill (раздел 5) и зафиксировать результат.
- [ ] Получить staging operator sign-off (раздел 6).

## 4. Production checklist
- [ ] Подтвердить, что staging checklist выполнен полностью.
- [ ] Повторно запустить preflight coverage (`--strict`) на production-like данных.
- [ ] Открыть релизное окно и развернуть production build.
- [ ] Выполнить post-deploy smoke:
  - pool run create (actor mapping);
  - pool publication step через worker `pool.publication_odata`;
  - проверка diagnostics/read-model без регрессии.
- [ ] Подтвердить отсутствие fallback на legacy `Database.username/password`.
- [ ] Получить production operator sign-off (раздел 6).

## 5. Rollback drill/runbook
### 5.1 Триггеры rollback
- Массовые fail-closed ошибки из-за mapping coverage gap.
- Рост ошибок публикации выше согласованного порога.
- Критическая деградация публикации (невозможность восстановить в пределах окна).

### 5.2 Действия rollback
1. Остановить запуск новых pool run публикаций (операционный stop gate).
2. Откатить релиз на предыдущий стабильный пакет orchestrator/worker/frontend.
3. Перезапустить worker pods/процессы.
4. Проверить, что публикация выполняется по предыдущей стабильной схеме.
5. Зафиксировать инцидент и список проблемных баз для remediation в `/rbac`.

### 5.3 Критерии успешного rollback drill
- [ ] Время восстановления в целевом SLO окна.
- [ ] Публикация выполняется без критических ошибок.
- [ ] Операционный протокол обновлён (что откатили, когда, кем, почему).

## 6. Mandatory operator sign-off
### Staging sign-off
- Дата/время:
- Оператор:
- Результат: `GO` / `NO-GO`
- Комментарий:

### Production sign-off
- Дата/время:
- Оператор:
- Результат: `GO-LIVE` / `ROLLBACK`
- Комментарий:

