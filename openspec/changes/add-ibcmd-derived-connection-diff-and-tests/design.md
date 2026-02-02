# Design: Derived `ibcmd` connection — сводка+diff в UI и provenance fallback в preview

## Контекст
В `scope=per_database` для `ibcmd_cli` connection может резолвиться per target из `Database.metadata.ibcmd_connection`.
Это даёт гибкость (mixed mode), но ухудшает прозрачность: пользователь видит “derived” без понимания реальных effective значений.

Отдельно, staff-only preview (`/api/v2/ui/execution-plan/preview/`) уже показывает bindings с `resolve_at=worker`, но сейчас provenance для offline DBMS metadata не отражает fallback из `Database.metadata` (когда offline профиль не содержит `dbms/db_server/db_name`).

## Цели дизайна
- UI: показывать пользователю *что именно будет использовано* (сводка) и *что отличается* (diff) при derived connection.
- Preview: сделать provenance правдоподобным и объясняющим (профиль базы vs `Database.metadata`), без раскрытия секретов.
- Сохранить простоту: не вводить новые production endpoints без необходимости.

## Опции
### Option A (предпочтительно): UI diff вычисляется на фронте из данных баз
Источник данных:
- `Database.ibcmd_connection` (профиль подключения без секретов)
- `Database.dbms/db_server/db_name` (DBMS metadata базы, как fallback для offline)

Алгоритм (conceptual):
1) Для каждой выбранной базы вычислить `effective_mode`:
   - `remote`, если профиль позволяет remote (`mode=remote` или `mode=auto` + `remote_url`);
   - иначе `offline` (если есть offline профиль с `config/data`).
2) Собрать “effective connection snapshot” per target:
   - remote: `remote_url`
   - offline: `config`, `data`, `db_path`
   - offline DBMS triplet: значение берётся из профиля (если задано), иначе из `Database.metadata` (`dbms/db_server/db_name`)
3) Построить summary:
   - counts по `effective_mode` + флаг `mixed_mode`
4) Построить diff:
   - ключи, где среди таргетов более одного уникального значения (например `remote_url`, `offline.config`, `offline.data`, `offline.db_name`)
   - выводить значения и количество таргетов, на которых встречается каждое значение
   - для больших N ограничить детализацию (например показывать top-K значений и “+N more”)

Плюсы:
- Не требует новых backend endpoints.
- Доступно не только staff (важно для Operations).

Минусы:
- Нужно аккуратно выбирать способ загрузки данных выбранных баз (возможен N+1, если нет bulk endpoint).

### Option B: отдельный backend endpoint “describe derived connection”
Сделать API, который принимает `database_ids` и возвращает summary+diff+provenance.
Плюсы: точность и отсутствие N+1.
Минусы: новый контракт, RBAC/tenant, поддержка.

В рамках MVP выбираем Option A; если упрёмся в производительность на 700+ базах — вернёмся к Option B отдельным change.

## Preview provenance fallback (staff-only)
Требование: preview bindings должны явно показывать, что `dbms/db_server/db_name` могут приходить:
- либо из `database.ibcmd_connection_profile.offline.*` (если профиль задаёт эти значения),
- либо из `Database.metadata.*` (fallback).

MVP-реализация (без изменения контракта):
- добавлять bindings-строки для fallback источников (worker, pending), чтобы в таблице provenance было видно оба пути.
- (опционально) если preview анализирует выбранные базы и видит, что профиль всегда задаёт ключ, можно пометить fallback как `status=skipped`/`reason=not_needed` (если модель bindings это допускает).

## UX ограничения
- Для N баз выводить:
  - summary всегда;
  - diff по ключам — с лимитами (по числу ключей, по числу значений, по числу примеров баз).

