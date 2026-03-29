## ADDED Requirements

### Requirement: Pool batch intake MUST нормализовать внешние реестры в canonical batch
Система ДОЛЖНА (SHALL) принимать внешние реестры поступлений и реализаций как canonical `PoolBatch`, scoped к конкретному `pool`, с сохранением provenance:

- `batch_kind` (`receipt` или `sale`);
- `source_type` (`schema_template_upload`, `integration`, или иной явный source class);
- raw payload reference и metadata источника;
- выбранный оператором `pool`;
- accounting period, используемый для запуска/закрытия;
- schema/integration reference, по которому выполнялась нормализация.

Система ДОЛЖНА (SHALL) поддерживать произвольный внешний формат через `Pool Schema Templates` и future integration adapters, а не через жёстко прошитый формат одного реестра.

`PoolBatch` intake в рамках варианта `B` ДОЛЖЕН (SHALL) оставаться отдельной подсистемой, отвечающей только за нормализацию, provenance и запуск связанного run. Intake НЕ ДОЛЖЕН (SHALL NOT) напрямую материализовывать factual balance projection или manual review state.

#### Scenario: Бухгалтер загружает произвольный реестр поступлений через schema template
- **GIVEN** оператор выбрал `pool` и подходящий `Pool Schema Template`
- **WHEN** оператор загружает внешний файл реестра поступлений
- **THEN** система нормализует вход в canonical `receipt` batch
- **AND** сохраняет provenance batch, достаточный для последующего run lineage и аудита

### Requirement: Batch intake MUST fail-closed на невалидной схеме или обязательных mapping gaps
Система ДОЛЖНА (SHALL) отклонять batch intake до создания документов и run, если schema/integration mapping не позволяет однозначно получить обязательные поля batch normalization contract.

Система НЕ ДОЛЖНА (SHALL NOT) silently пропускать обязательные поля или подставлять скрытые fallback-значения для суммы, организации или периода.

#### Scenario: Отсутствие обязательного amount mapping блокирует intake
- **GIVEN** выбранный schema template не может извлечь сумму из входного payload
- **WHEN** оператор запускает intake
- **THEN** batch отклоняется валидацией
- **AND** run и документы не создаются

### Requirement: Receipt batch MUST запускать ровно один batch-backed top-down run от явной стартовой организации
Система ДОЛЖНА (SHALL) для `receipt` batch запускать ровно один `top_down` run, связанный с этим batch.

Оператор ДОЛЖЕН (SHALL) явно выбирать стартовую организацию (`start_organization`) из активной topology пула на период batch/run. Период batch-backed run ДОЛЖЕН (SHALL) совпадать с `period_start` / `period_end` run и использоваться как canonical accounting period batch.

Batch-backed create-run contract ДОЛЖЕН (SHALL) передавать явные `batch_id` и `start_organization_id` как часть direction-specific input. Existing manual `top_down` path с прямым `starting_amount` НЕ ДОЛЖЕН (SHALL NOT) silently заменяться batch contract.

Idempotency fingerprint для batch-backed create-run ДОЛЖЕН (SHALL) включать как минимум identity batch и выбранную стартовую организацию, чтобы повторный submit того же batch-backed запроса reuse'ил тот же `PoolRun`, а не создавал дубликат.

Система НЕ ДОЛЖНА (SHALL NOT) fan-out'ить один batch в несколько `PoolRun` без явного создания нового batch.

#### Scenario: Один реестр поступлений создаёт один top-down run
- **GIVEN** оператор загрузил `receipt` batch и выбрал стартовую организацию из активной topology
- **WHEN** intake завершается успешно
- **THEN** система создаёт ровно один связанный `PoolRun`
- **AND** batch/run lineage доступен в operator-facing read model

#### Scenario: Повторный submit того же `receipt` batch не создаёт дубликат run
- **GIVEN** для `receipt` batch уже существует run с тем же `batch_id`, `start_organization_id`, периодом и explicit binding reference
- **WHEN** оператор повторно отправляет тот же batch-backed create-run запрос
- **THEN** система возвращает существующий `PoolRun`
- **AND** не создаёт второй run для того же batch

### Requirement: Sale batch MUST создавать closing documents без обязательного line-level pairing с receipt rows
Система ДОЛЖНА (SHALL) поддерживать `sale` batch для создания фактических closing documents на active leaf-узлах topology выбранного периода.

Система НЕ ДОЛЖНА (SHALL NOT) требовать обязательной line-level связи продажи с исходными строками `receipt` batch, если aggregate factual balance узла/квартала может быть закрыт фактической реализацией.

В рамках этого change поддержка `sale` batch на промежуточных узлах НЕ ЯВЛЯЕТСЯ (SHALL NOT be considered) обязательной.

#### Scenario: Реестр реализаций закрывает aggregate balance leaf-узла
- **GIVEN** у leaf-узла есть незакрытый factual balance за квартал
- **WHEN** оператор загружает `sale` batch для этого leaf-узла
- **THEN** система создаёт closing documents
- **AND** дальнейшая factual projection уменьшает открытый остаток без line-level pairing с исходным `receipt` batch
