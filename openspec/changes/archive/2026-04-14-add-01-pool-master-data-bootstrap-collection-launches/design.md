## Context
Система уже умеет делать staged bootstrap import из одной ИБ:
- preflight/dry-run gating;
- child job и chunk execution;
- retry failed chunks;
- idempotent canonical/binding upsert;
- inbound-origin safety для anti-ping-pong.

Но операторский кейс "собрать reference layer по всем ИБ" требует надстройки другого уровня:
- единый batch request;
- batch-level preview и aggregate dry-run;
- immutable snapshot выбранных ИБ;
- история и детализация общего сбора.

Это делает multi-database collection архитектурно похожим на cluster-wide manual sync launch, но с важным отличием: child runtime здесь не sync job, а существующий per-database bootstrap import job с его staged lifecycle.

## Goals / Non-Goals

### Goals
- Дать оператору batch-level сбор canonical reference из `cluster_all` или `database_set`.
- Сохранить существующий staged lifecycle bootstrap import.
- Переиспользовать текущие per-database bootstrap jobs как child execution unit.
- Сделать collection operator-transparent: history, detail, aggregate preview/progress, per-database outcome.
- Не изобретать новый global merge algorithm поверх canonical hub.

### Non-Goals
- Не заменять current per-database bootstrap import.
- Не объединять collection и rollout в один overload-ed API.
- Не изменять semantics child bootstrap executor/chunk order.
- Не позволять UI silently решать cross-infobase conflicts без backend diagnostics.

## Decisions

### Decision: Вводим parent collection request поверх существующего per-database bootstrap job
Per-database `PoolMasterDataBootstrapImportJob` остаётся child execution unit для одной базы. Для batch collection вводится отдельный parent объект, например `PoolMasterDataBootstrapCollectionRequest`, и связанные `PoolMasterDataBootstrapCollectionItem`.

Причины:
- текущий child job уже стабилен и покрыт staged lifecycle;
- parent batch должен хранить immutable snapshot, aggregate preview и history;
- попытка сделать child bootstrap job multi-database сломает существующие инварианты UI/API и модели данных.

### Decision: Batch-level lifecycle повторяет staged bootstrap semantics
Parent collection request имеет тот же operator lifecycle:
- `preflight`;
- `dry_run`;
- `execute`;
- `finalize`.

Но шаги интерпретируются как aggregate orchestration над child database items:
- `preflight` проверяет target snapshot и запускает/агрегирует per-database preflight;
- `dry_run` агрегирует per-database dry-run summaries;
- `execute` fan-out'ит child execute jobs;
- `finalize` фиксирует batch outcome.

Это сохраняет знакомый оператору mental model и не создаёт второго, конфликтующего lifecycle.

### Decision: Immutable target snapshot обязателен
Parent collection request хранит immutable snapshot:
- `target_mode`;
- `cluster_id`, если выбран `cluster_all`;
- итоговый список `database_ids`;
- `entity_scope`.

Это нужно, чтобы:
- batch preview и execute работали по одним и тем же целям;
- изменение состава кластера не переписывало уже просмотренный dry-run;
- оператор видел детерминированную историю того, что именно было собрано.

### Decision: Parent batch не invent-ит новый canonical merge algorithm
Multi-database collection — это orchestration change, а не новый merge semantics change. Child apply продолжает использовать существующий canonical resolve+upsert path и его current conflict behavior.

Следствия:
- если разные ИБ дают конфликтующие данные для одного canonical scope, это всплывает через existing diagnostics/fail-closed behavior;
- batch collection не выполняет silent "умный merge";
- если в будущем понадобится отдельная global normalization policy, это отдельный change.

### Decision: Child bootstrap jobs могут коалесцироваться
Если для отдельной базы уже идёт совместимый child bootstrap import job, новый parent item не должен создавать duplicate child executor. Вместо этого item получает `coalesced` outcome и ссылку на существующий child job.

### Decision: UI остаётся в `Bootstrap Import` зоне
Multi-database collection не требует нового route. В `Bootstrap Import` зоне появляется выбор режима работы:
- single database bootstrap;
- multi-database collection.

Или эквивалентный launcher/segmented control внутри того же workspace shell.

Такой вариант минимизирует IA churn и делает связь между одиночным и batch bootstrap очевидной.

### Decision: Cluster/database selection использует cluster-aware refs
Текущий `SimpleDatabaseRef` недостаточен, потому что не содержит `cluster_id`. Для batch collection UI должен использовать refs с `cluster_id` и отдельный cluster list.

Server-side target resolution остаётся обязательной и не доверяет frontend snapshot blindly.

### Decision: V1 не добавляет parent-level cancel
У child job уже есть свои статусы и retry path. Parent-level cancel вводит больше инвариантов, чем пользы в первой итерации. В `V1` достаточно:
- create batch request;
- увидеть dry-run/execution detail;
- следить за progress и child outcomes.

## Alternatives Considered

### Alternative: Расширить текущий child bootstrap job до multi-database
Отклонено.

Минусы:
- ломает уже shipped single-database contract;
- смешивает batch intent и child execution в одной модели;
- усложняет `retry failed chunks`, который сейчас естественно scoped к одной базе.

### Alternative: Рассматривать multi-database collection как `inbound sync`
Отклонено.

`inbound sync` и `bootstrap import` уже разные контракты:
- inbound sync работает от checkpointed exchange-plan polling;
- bootstrap import — staged первичный импорт с explicit preflight/dry-run/report.

Для reference collection пользователю нужен именно второй путь, просто в batch orchestration форме.

## Risks / Trade-offs
- Batch collection добавляет второй read-model рядом с child bootstrap jobs.
  - Это нормально: parent batch моделирует orchestration, child jobs моделируют фактическое исполнение по ИБ.
- Aggregate dry-run может быть тяжёлым на больших кластерах.
  - Нужен chunked fan-out и partial progress вместо синхронного ожидания всего результата в request.
- Пользователь может ожидать "идеальный единый reference" без конфликтов.
  - Change этого не обещает; он orchestration-only над существующим canonical apply path.

## Verification Gates
- `POST` batch collection request возвращает parent identifier быстро и не исполняет full import в request/response.
- Batch target snapshot детерминирован и не меняется после принятия запроса.
- Повторный запуск по базе с уже активным child bootstrap job не создаёт duplicate child job.
- Batch `dry_run` и `execute` сохраняют aggregate counters и per-database detail.
- UI не теряет выбранный scope после Problem Details ошибок.
- OpenAPI и generated frontend contracts обновлены вместе с API.
