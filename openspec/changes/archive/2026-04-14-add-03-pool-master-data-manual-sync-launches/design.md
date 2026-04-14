## Context
Штатный sync runtime уже существует и строго опирается на per-database scope `(tenant, database, entity)`:
- `PoolMasterDataSyncJob`, `PoolMasterDataSyncCheckpoint`, `PoolMasterDataSyncConflict` и outbox state привязаны к конкретной `Database`;
- child trigger path (`inbound`, `outbound`, `reconcile`) уже выполняет capability checks, policy resolution, server affinity resolution и enqueue workflow execution;
- `Sync` tab в UI сейчас работает как diagnostic/remediation surface, а не как полноценный launcher.

Запрос пользователя добавляет новую операторскую возможность, но не меняет source-of-truth и не требует нового sync runtime. Поэтому архитектурно правильный вариант — ввести parent launch request, который делает snapshot operator intent и асинхронно fan-out'ит существующие child scope jobs.

## Goals / Non-Goals

### Goals
- Дать оператору ручной запуск sync из UI по всем ИБ одного кластера или по явному набору ИБ.
- Поддержать `inbound`, `outbound` и `reconcile`.
- Сохранить существующий per-database child runtime как единственный исполняющий path.
- Сделать launch operator-transparent: history, detail, aggregate progress, per-scope outcomes.
- Избежать duplicate child jobs и показать coalescing явно.
- Оставить capability/policy/affinity fail-closed на child scope уровне.

### Non-Goals
- Не делать `PoolMasterDataSyncJob` кластерным или tenant-global объектом.
- Не смешивать manual sync launch с bootstrap import wizard.
- Не добавлять отдельный sync microservice, второй queue family или новый page foundation.
- Не давать UI права вручную подменять runtime scheduling contract.

## Decisions

### Decision: Вводим parent launch request вместо расширения `PoolMasterDataSyncJob`
Текущий `PoolMasterDataSyncJob` моделирует только child scope `(tenant, database, entity)` и не должен расширяться до nullable `database` или cluster-level meaning. Для operator batch launch вводится отдельный parent объект, например `PoolMasterDataSyncLaunchRequest`, и связанные `PoolMasterDataSyncLaunchItem`.

Причины:
- текущая модель, индексы и read-model уже построены вокруг обязательного `database_id`;
- cluster-wide intent и child scope execution — разные уровни абстракции;
- parent launch требует immutable snapshot и aggregate counters, которых не должно быть в child job.

### Decision: Target snapshot фиксируется на момент принятия запроса
Launch request хранит immutable snapshot:
- `mode`;
- `target_mode`;
- `cluster_id` для `cluster_all`, если применимо;
- список `database_ids`, реально вошедших в snapshot;
- `entity_scope`.

Это нужно, чтобы:
- повторное открытие launch detail показывало тот же набор целей;
- изменения cluster membership, RBAC refs или списка ИБ после принятия запроса не переписывали operator intent;
- remediation/debug не зависели от "текущего" состава кластера.

### Decision: Parent launch fan-out идёт асинхронно через workflow-backed orchestration
API request не должен синхронно обходить сотни child scope. После сохранения launch request система создаёт parent async execution path, который chunked вызывает существующие child triggers.

Предпочтительный вариант реализации:
- parent launch request получает собственный operation/workflow execution;
- pool-domain runtime получает новый step для fan-out launch items;
- child scopes по-прежнему создаются через существующие `trigger_pool_master_data_*_sync_job(...)`.

Это сохраняет основной контракт проекта: long-running domain work не исполняется целиком в API request/response.

### Decision: Parent launcher переиспользует существующие child trigger функции без bypass
Для каждого scope `(database, entity)` launcher вызывает только текущие child trigger entrypoint-ы:
- `trigger_pool_master_data_inbound_sync_job`
- `trigger_pool_master_data_outbound_sync_job`
- `trigger_pool_master_data_reconcile_sync_job`

Launcher не дублирует:
- capability gating;
- policy resolution;
- server affinity resolution;
- workflow enqueue contract;
- child conflict enqueue behavior.

### Decision: Активные child jobs коалесцируются, а не дублируются
Если для выбранного `(tenant, database, entity)` уже есть активный child sync job в совместимом направлении, новый batch launch item не создаёт duplicate child workflow. Вместо этого item получает status `coalesced` и ссылку на существующий `sync_job_id`.

Это снижает duplicate load и делает повторный ручной запуск безопасным.

### Decision: Parent launch сохраняет mixed outcome по item'ам, а не откатывает весь batch из-за одного scope
После принятия валидного запроса parent launch считается допустимым даже если часть child scope:
- не прошла policy gate;
- не смогла разрешить `server_affinity`;
- упёрлась в runtime-disabled path;
- создала child conflict.

В этих случаях batch launch сохраняет item-level `failed`/`skipped` outcome с machine-readable reason и продолжает fan-out остальных scope. Это критично для кластерного запуска, где состояние отдельных ИБ неоднородно.

### Decision: UI остаётся внутри существующей `Sync` зоны
Новая возможность не требует нового route. `Launch Sync` lives inside `/pools/master-data?tab=sync`:
- верхняя action bar получает launcher drawer;
- ниже остаются `Sync Status` и `Conflict Queue`;
- рядом появляется `Launch History` / launch detail surface.

Это соответствует already-shipped operator mental model: всё про sync находится в одном workspace zone.

### Decision: Для cluster-aware target selection UI использует refs с `cluster_id`
Текущий `listPoolTargetDatabases()` возвращает только `{id, name}` и не подходит для cluster-wide selection. Для launcher UI надо использовать cluster-aware refs либо расширенный API ref surface, где доступны:
- список кластеров;
- список ИБ с `cluster_id`.

Server-side validation всё равно остаётся обязательной и не доверяет frontend snapshot blindly.

### Decision: Entity scope launcher'а остаётся registry-driven и capability-gated
В launcher entity options попадают только типы с нужными sync capabilities. Это означает:
- `GLAccount` не попадает в generic mutating launch entity scope;
- `GLAccountSet` не попадает туда тем более;
- новый entity type без explicit sync capability не должен magically появиться в UI launcher.

### Decision: `V1` не включает manual cancel/reprioritize
Для первой версии достаточно:
- создать launch;
- увидеть history/detail;
- перейти к child status/conflicts.

Cancel/reprioritize parent launch вводит дополнительные инварианты и может быть отдельным follow-up change после появления реального operator demand.

## Alternatives Considered

### Alternative: Делать cluster-level sync прямо в `PoolMasterDataSyncJob`
Отклонено.

Минусы:
- ломает существующую модель данных и индексы, где `database_id` обязателен;
- размывает границу между operator batch intent и child runtime execution;
- усложняет существующий read-model `Sync Status`, который уже scoped per database/entity.

### Alternative: Синхронно fan-out'ить child scopes прямо в API
Отклонено.

Минусы:
- нарушает existing contract для long-running work;
- плохо масштабируется на сотни ИБ;
- делает request latency и error handling зависимыми от числа target scope.

### Alternative: Использовать bootstrap import wizard как "сбор из ИБ"
Отклонено.

Bootstrap import и inbound sync — разные контракты:
- bootstrap import строит canonical данные из первичного источника с preflight/dry-run/execute;
- inbound sync продолжает shipped двусторонний runtime и опирается на checkpoints/exchange-plan polling.

## Risks / Trade-offs
- Parent launch introduces second sync-related read-model alongside `Sync Status`.
  - Это приемлемо, потому что он моделирует batch intent, а не per-scope runtime state.
- Mixed outcome может показаться оператору "частичным успехом".
  - Это лучше, чем silent drop или full rollback batch из-за одной проблемной ИБ.
- UI усложняется из-за cluster/database selector.
  - Это контролируемо, если оставить только `cluster_all` и `database_set`, без tenant-global mode.
- Нужен новый async fan-out path.
  - Он должен переиспользовать уже существующий reconcile scheduler pattern и child trigger entrypoint-ы.

## Verification Gates
- `POST` launch API возвращает `launch_id` быстро и не ждёт завершения всех child scopes.
- Parent launch snapshot детерминирован и не меняется после принятия запроса.
- Повторный запуск по уже активному scope не создаёт duplicate child sync job.
- Child scope по-прежнему проходит capability/policy/affinity gates на существующем runtime path.
- UI launcher показывает только sync-capable entity types.
- `cluster_all` и `database_set` покрыты unit/API tests.
- Launch history/detail даёт operator-facing aggregate counters и per-item diagnostics.
- OpenAPI и generated frontend contracts обновлены вместе с API.
