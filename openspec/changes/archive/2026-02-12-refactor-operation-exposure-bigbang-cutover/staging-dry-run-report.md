# Отчёт: backup/restore + dry-run rehearsal для cutover

Дата: 2026-02-11  
Change ID: `refactor-operation-exposure-bigbang-cutover`

## 1. Контекст

Для задачи `1.3` подготовлен отдельный скрипт rehearsal:

- `scripts/rollout/backup-restore-operation-exposure-cutover.sh`

Скрипт покрывает:
- backup PostgreSQL (`pg_dump` + `gzip`);
- checksum (`sha256sum`);
- restore-check в временную БД;
- smoke-проверки ключевых таблиц (`operation_templates`, `operation_exposures`, `batch_operations`);
- cleanup временной БД.

## 2. Локальный dry-run (выполнено)

Команда:

```bash
cd /home/egor/code/command-center-1c
./scripts/rollout/backup-restore-operation-exposure-cutover.sh --dry-run
```

Результат:
- Статус команды: `exit code 0`.
- Проверка prerequisites: `PASS`.
- Полный pipeline backup/checksum/restore-check/smoke/check-cleanup выведен в dry-run режиме.

Ключевые строки из вывода:
- `Step 1/4: creating backup dump`
- `Step 2/4: creating checksum`
- `Step 3/4: restore validation to temporary database (...)`
- `Step 4/4: basic restore smoke checks`
- `Backup/restore rehearsal finished`

## 3. Staging rehearsal (production-like data)

Статус: `требует запуска в staging окружении`.

Команда для staging:

```bash
cd /home/egor/code/command-center-1c
./scripts/rollout/backup-restore-operation-exposure-cutover.sh
```

Критерии PASS на staging:
- backup-файл и `.sha256` созданы;
- restore-check в временную БД выполняется без ошибок;
- smoke-запросы к `operation_templates` / `operation_exposures` / `batch_operations` успешны;
- временная БД удалена в cleanup;
- итоговый `exit code 0`.

## 4. Локальный non-dry rehearsal (диагностический прогон)

Команда:

```bash
cd /home/egor/code/command-center-1c
./scripts/rollout/backup-restore-operation-exposure-cutover.sh --backup-dir /tmp/operation-exposure-cutover-rehearsal
```

Результат:
- backup и checksum созданы;
- restore во временную БД выполнен;
- на этапе smoke получен fail:
  - `Expected table 'operation_templates' is missing in database ...`
- cleanup временной БД выполнен (подтверждено в логе).

Вывод:
- скрипт корректно переводит прогон в `No-Go` при несоответствии схемы;
- для staging/prod rehearsal обязательна БД с ожидаемой схемой cutover-контура.

## 5. Примечание по rollback-политике

Данный rehearsal поддерживает требование change:
- rollback рассматривается только как полный откат релиза:
  - restore pre-cutover backup БД;
  - откат deploy до previous artifact.
