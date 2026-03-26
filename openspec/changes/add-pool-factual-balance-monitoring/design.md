## Context
Существующий контракт `pool-distribution-runs` фиксирует lifecycle `PoolRun`, direction-specific input и run-local report для расчёта/публикации. Это покрывает execution path, но не закрывает целевой операторский сценарий:

- бухгалтер получает внешний реестр поступлений;
- выбирает стартовую "подушку" вручную;
- запускает распределение суммы по topology;
- позже создаёт реестр реализаций, который выравнивает factual balance на leaf-узлах;
- ожидает увидеть по всем ИБ minute-scale актуальную картину, где суммы зависли и что переносится в следующий квартал.

Главный архитектурный разрыв состоит в том, что текущий run report описывает расчётный runtime артефакт, а пользователю нужен factual balance, построенный по реальным документам и регистрам ИБ, в том числе после ручных действий в 1С.

## Goals
- Ввести canonical batch intake для внешних реестров поступлений и реализаций.
- Поддержать запуск top-down run от явной стартовой организации без жёсткой привязки к одной "подушке".
- Материализовать factual balance projection по `pool / organization / edge / quarter / batch`.
- Держать в projection три денежные меры: `amount_with_vat`, `amount_without_vat`, `vat_amount`.
- Показывать бухгалтеру near-real-time summary/drill-down с явной индикацией, где сумма застряла.
- Отделить batch settlement status от технического lifecycle `PoolRun.status`.
- Поддержать quarter carry-forward на том же узле.

## Non-Goals
- Не меняем фиксированный lifecycle `PoolRun.status`; settlement status вводится отдельно.
- Не пытаемся автоматически исправлять ручные расхождения в 1С.
- Не требуем в первой итерации точной line-level связи между реализацией и исходной строкой прихода.
- Не требуем backfill для исторических batch/run до включения change.
- Не фиксируем в этом change окончательный список регистров БП для бухгалтерского эталона; это отдельное исследование внутри delivery.

## Decisions

### Decision: Разделить batch settlement и run execution
`PoolRun` остаётся execution сущностью с текущим FSM (`draft -> validated -> publishing -> partial_success|published|failed`). Для бизнес-статуса баланса вводится отдельная batch/projection сущность со status/read-model уровня:

- `ingested`
- `distributed`
- `partially_closed`
- `closed`
- `carried_forward`
- `attention_required`

Это позволяет не ломать существующий facade contract и одновременно показать пользователю реальную степень закрытия суммы.

### Decision: Source of truth для factual balance это реальные документы и регистры ИБ
Баланс не должен считаться по ожидаемым суммам из distribution artifact. Projection строится по фактическим данным ИБ:

- документам, созданным через Command Center;
- движениям/регистрам, влияющим на баланс;
- ручным документам пользователя, если они видны в ИБ.

Runtime artifacts Command Center остаются provenance-слоем и помогают атрибуции, но не подменяют фактическое состояние.

### Decision: Materialized read model вместо on-demand расчёта
Для 700 ИБ и minute-scale обновления нужен централизованный materialized projection в Command Center. UI не должен пересчитывать баланс прямыми запросами в ИБ. Projection обновляется:

- немедленно после собственных действий Command Center;
- фоновыми worker sync циклами по changed-since watermark;
- с явной меткой freshness/staleness, если ИБ недоступна или находится в maintenance.

### Decision: Traceability через `pool_run_id` плюс отдельный канал для unattributed документов
Для документов, созданных через Command Center, traceability фиксируется через `pool_run_id` и/или отдельный регистр расширения в 1С. Для ручных документов без traceability projection хранит вклад как `unattributed`:

- они влияют на factual totals организации/квартала;
- они не должны silently распределяться по конкретному batch/edge;
- пользователь later review flow сможет их разметить.

### Decision: Один внешний batch порождает ровно один pool_run
`one batch = one pool_run` фиксирует traceability и упрощает операторское объяснение: бухгалтер видит, какой реестр породил какой run и какие дальнейшие движения/остатки из него выросли.

### Decision: Реализации закрывают баланс агрегатно, а не line-by-line
В первом релизе фактическая реализация выравнивает накопленный баланс на узле/квартале без требования прямой связи с исходной строкой прихода. Для продажи из batch intake обязателен leaf-node scope; поддержка промежуточных узлов остаётся follow-up.

### Decision: Quarter carry-forward считается на том же узле
Остаток, дошедший до leaf-узла и не закрытый фактическими реализациями, переносится в следующий квартал на том же узле. Возврат суммы "назад" по цепочке вне явной продажи в рамках этого change не поддерживается.

## Alternatives Considered

### Рассчитывать dashboard только по run artifacts
Отклонено. Такой подход ломается сразу после ручных действий пользователя в 1С и не даёт factual picture.

### Расширить `PoolRun.status` settlement-статусами
Отклонено. Это смешивает execution lifecycle с бизнес-закрытием баланса и конфликтует с уже зафиксированным контрактом `pool-distribution-runs`.

### Автоматически распределять manual realizations между пулами
Отклонено для первой итерации. Правила атрибуции при участии одной организации в нескольких пулах ещё не стабилизированы и требуют отдельного operator review механизма.

## Risks / Trade-offs
- Неопределённый бухгалтерский эталон: нужно отдельно исследовать, какие именно отчёты/регистры БП считать reference implementation для balance parity.
- Polling 700 ИБ создаёт риск по throughput и freshness; потребуется worker sharding, watermarks и backpressure.
- Документы без traceability будут создавать operator workload на review, но это лучше, чем silently искажать pool/batch attribution.
- Initial leaf-only settlement не закрывает будущий сценарий продаж на промежуточных узлах; это нужно учитывать в data model, чтобы не блокировать расширение.

## Migration Plan
1. Ввести новые batch/projection contracts и read-model surfaces без изменения существующего `PoolRun` lifecycle.
2. Добавить traceability markers для новых документов, создаваемых Command Center.
3. Включить factual polling только для новых batch/run после rollout.
4. Отдельно подключить operator review flow для unattributed документов.
5. После стабилизации сверить projection с выбранными бухгалтерскими отчётами БП и при необходимости скорректировать mapping регистров.

## Open Questions
- Какие конкретно отчёты БП и какие регистры должны считаться бухгалтерским эталоном для factual balance.
- Как именно распределять manual realizations между несколькими пулами, если одна организация участвует в нескольких пулах одного квартала.
- Нужен ли отдельный priority/attention scoring поверх ненулевого остатка, или первой версии достаточно строгого "ненулевой остаток = сигнал".
