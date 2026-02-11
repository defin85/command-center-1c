# Runbook: Big-bang cutover на OperationExposure (один релиз)

Дата: 2026-02-11  
Change ID: `refactor-operation-exposure-bigbang-cutover`  
Статус: Draft для rehearsal, блокирует production cutover до успешного dry-run

## 1. Цель и границы

Цель релиза: в одном окне обслуживания перевести templates/runtime/RBAC/operations persistence на `OperationExposure(surface="template") + OperationDefinition` и удалить legacy projection `OperationTemplate`.

Обязательные границы:
- Cutover выполняется в фазах `preflight -> backfill -> switch -> contract`.
- После switch не допускается dual-read/dual-write на `OperationTemplate`.
- В рамках того же релиза удаляются legacy структуры:
  - `operation_templates`;
  - `templates_operation_template_permissions`;
  - `templates_operation_template_group_permissions`;
  - `batch_operations.template_id` FK/column (+ связанные constraints/indexes).
- Rollback только полный: restore pre-cutover backup + откат deploy.

## 2. Роли и коммуникации

- Release Commander: принимает финальное `Go/No-Go`.
- DB Engineer: backup/restore, миграции, контроль блокировок.
- Backend On-call: runtime/API smoke, error budget, логи.
- QA/Operator: smoke сценарии UI/API и валидация business-path.

Коммуникации:
- Канал релиза: `#release-operation-exposure-cutover`.
- Все шаги фиксируются с timestamp и статусом (`PASS/FAIL`).

## 3. Окно обслуживания

- Плановое окно: `120 минут` (target), `180 минут` (hard limit).
- Freeze:
  - запрет на merge/deploy в `orchestrator`, `contracts`, `frontend` вне cutover ветки;
  - остановка несогласованных миграций и ad-hoc SQL;
  - заморозка ручных операций, создающих новые template-based execution.
- Точка старта окна: `T0`.

## 4. Артефакты до старта (T-24h / T-2h)

Перед production-окном ДОЛЖНО быть подтверждено:
- Staging dry-run на production-like данных завершён успешно.
- Rollback rehearsal подтверждён (восстановление backup + previous deploy).
- Preflight критичные проверки дают `mismatch=0`.
- Runtime path gate не находит обращений к `OperationTemplate` в switch-контурах.
- Подготовлены:
  - backup location и проверка доступности restore;
  - артефакт предыдущего deploy для instant rollback;
  - список smoke сценариев и ответственных.

## 5. Пошаговый план cutover

## 5.1 Phase A: Preflight (T0..T+25m)

Цель: доказать, что switch/contract безопасны.

Чек-лист:
- Alias uniqueness для `operation_exposure(surface="template")`.
- Referential consistency:
  - legacy template permissions;
  - template refs в operations metadata/batch records.
- RBAC parity (direct/group/effective-access).
- Runtime path gate:
  - нет критичных runtime/internal/rbac обращений к `OperationTemplate`.

Правило:
- Любой critical mismatch > 0 = `No-Go`.
- В случае `No-Go` переход к `Section 8 (Abort до switch)`.

## 5.2 Phase B: Backup (T+25m..T+40m)

Цель: зафиксировать точку полного восстановления.

Чек-лист:
- Создан pre-cutover backup БД.
- Проверена целостность backup (метаданные + размер + быстрый restore-check).
- Зафиксирован backup id/path в релизном логе.
- Подтверждена доступность previous deploy artifact.
- Рекомендованный инструмент исполнения: `scripts/rollout/backup-restore-operation-exposure-cutover.sh`.

Правило:
- Нет валидного backup -> `No-Go`.

## 5.3 Phase C: Backfill/Expand (T+40m..T+80m)

Цель: подготовить exposure-only состояние до switch.

Шаги:
- Применить миграции expand (exposure permission structures и сопутствующие индексы).
- Выполнить backfill:
  - legacy template permissions -> exposure permissions;
  - operation metadata -> `template_id` (alias) + `template_exposure_id`.
- Выполнить parity-сверки:
  - direct/group permissions;
  - effective access smoke-выборки.

Правило:
- Parity mismatch > 0 по критичным проверкам = `No-Go`.

## 5.4 Phase D: Switch (T+80m..T+105m)

Цель: включить runtime/API paths только на exposure модели.

Шаги:
- Включить runtime resolve template через `OperationExposure(alias)` + `OperationDefinition`.
- Перевести internal template endpoints на exposure-read path.
- Перевести template RBAC endpoints/effective-access/refs на exposure permissions.
- Включить fail-closed runtime semantics:
  - `TEMPLATE_NOT_FOUND`;
  - `TEMPLATE_NOT_PUBLISHED`;
  - `TEMPLATE_INVALID`;
  - без fallback на `OperationTemplate`.

Smoke-проверки (обязательные):
- workflow operation execution;
- internal get-template/render-template;
- template RBAC/effective-access;
- enqueue/details provenance (наличие `template_id` + `template_exposure_id` для новых записей).

## 5.5 Phase E: Contract (T+105m..T+120m)

Цель: удалить legacy projection в том же релизе.

Шаги:
- Удалить:
  - `operation_templates`;
  - `templates_operation_template_permissions`;
  - `templates_operation_template_group_permissions`;
  - `batch_operations.template_id` FK/column + связанные constraints/indexes.
- Повторить critical smoke после удаления legacy схемы.

Критерий успешного завершения:
- Runtime/API smoke PASS;
- legacy tables/FK отсутствуют;
- в логах нет runtime обращений к `OperationTemplate`.

## 6. Go / No-Go критерии

## 6.1 Go

Релиз получает `Go`, если одновременно выполнено:
- preflight critical mismatches = `0`;
- RBAC parity mismatch = `0` для обязательной smoke-выборки;
- runtime/internal template resolve failures = `0`;
- staging rehearsal успешно воспроизводит production steps;
- rollback rehearsal подтверждён;
- post-switch и post-contract smoke = PASS.

## 6.2 No-Go

Релиз получает `No-Go`, если наблюдается хотя бы одно:
- alias collision или referential inconsistency без автокоррекции в окне;
- mismatch > 0 в критичных parity проверках;
- наличие критичных runtime/internal/rbac path зависимостей от `OperationTemplate`;
- невозможность гарантированного restore rollback пути;
- критический smoke FAIL в switch/contract фазах.

## 7. Post-cutover подтверждение (до закрытия окна)

- Data consistency подтверждена (exposure links и metadata согласованы).
- RBAC parity подтверждена.
- Legacy runtime references отсутствуют.
- Release log заполнен:
  - время фаз;
  - результаты проверок;
  - инциденты/решения;
  - финальный статус.

## 8. Процедуры abort/rollback

## 8.1 Abort до switch

Условия:
- `No-Go` в preflight/backfill.

Действия:
- Не выполнять switch/contract.
- Завершить окно в pre-cutover состоянии.
- Зафиксировать причины и remediation план.

## 8.2 Rollback после switch/contract (только полный)

Условия:
- Критическая регрессия после switch/contract (runtime outage, массовые ошибки, несогласованность данных).

Шаги:
1. Объявить `SEV-1`, freeze write-трафик в affected контуре.
2. Остановить/ограничить pipeline, создающий новые template-based executions.
3. Выполнить restore pre-cutover backup БД.
4. Откатить application deploy до previous release artifact.
5. Прогнать минимальный smoke для подтверждения восстановления.
6. Зафиксировать инцидент, root-cause hypothesis и план повторной попытки.

Ограничение:
- Частичный rollback (только код или только схема) запрещён.

## 9. Checklist для релизного протокола

- [ ] Preflight PASS (`mismatch=0` по критичным проверкам).
- [ ] Backup создан и верифицирован.
- [ ] Backfill завершён, parity PASS.
- [ ] Switch выполнен, smoke PASS.
- [ ] Contract (drop legacy) выполнен, smoke PASS.
- [ ] Post-cutover consistency/RBAC/runtime checks PASS.
- [ ] Финальный статус зафиксирован (`GO-LIVE` или `ROLLBACK`).

## 10. Команды (шаблон для релизного окна)

Ниже шаблон командного протокола. Конкретные команды preflight/gate реализуются задачами `1.2` и `1.4`.

```bash
# 0) Перейти в репозиторий
cd /home/egor/code/command-center-1c

# 1) Backup + restore rehearsal (production-like staging / production window)
./scripts/rollout/backup-restore-operation-exposure-cutover.sh

# 2) Применить миграции
cd orchestrator
../.venv/bin/python manage.py migrate

# 3) Backfill (dry-run на rehearsal, commit в production cutover)
../.venv/bin/python manage.py backfill_operation_catalog --dry-run
../.venv/bin/python manage.py backfill_operation_exposure_permissions --dry-run --strict-parity --json
../.venv/bin/python manage.py backfill_operation_template_metadata --dry-run --strict --json

# 4) Production backfill (без dry-run) - после PASS preflight
../.venv/bin/python manage.py backfill_operation_catalog
../.venv/bin/python manage.py backfill_operation_exposure_permissions --strict-parity --json
../.venv/bin/python manage.py backfill_operation_template_metadata --strict --json

# 5) Здесь выполняются preflight/gate команды из задач 1.2/1.4
#    (обязательное условие: critical mismatches = 0)
../.venv/bin/python manage.py preflight_operation_exposure_cutover --strict --json
../.venv/bin/python manage.py gate_operation_template_references --strict --json
```
