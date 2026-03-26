## Контекст

В текущем shipped contract:
- `topology_template_revision` владеет abstract graph и structural slot namespace;
- `execution-pack revision` реализует named slot implementations;
- `pool` materialize'ит concrete topology через `slot_key -> organization_id`;
- runtime уже умеет переписывать topology-aware aliases
  `master_data.party.edge.*` / `master_data.contract.<id>.edge.*`
  в canonical static tokens до `master_data_gate`.

Проблема находится не в runtime compile, а в authoring/compatibility contract. Новые/revised reusable templates и execution packs всё ещё могут оставаться семантически reusable только по slot coverage, но при этом тащить hardcoded concrete participant refs в decision revisions. Тогда правка topology template не устраняет привязку к конкретным организациям/контрагентам.

## Goals / Non-Goals

- Goals:
  - Сделать topology-aware master-data aliases обязательным reusable contract для новых/revised template-oriented execution packs.
  - Жёстко запретить old concrete-ref authoring на canonical producer path `/pools/execution-packs` для новых и новых ревизий reusable execution packs.
  - Зафиксировать fail-closed compatibility/attach path для template-based pool assembly.
  - Сохранить разделение ownership: template владеет структурой, execution pack владеет reusable execution logic, pool владеет concrete slot assignments.
- Non-Goals:
  - Не конвертировать и не repair'ить historical pools/execution packs.
  - Не расширять grammar alias contract.
  - Не переносить reusable decision authoring в `/pools/catalog`.

## Решения

### 1. Переиспользовать существующий alias runtime contract без нового DSL

Этот change не вводит новый syntax для `document_policy`. Authoring surfaces обязаны считать уже shipped topology-aware aliases canonical reusable contract для topology-derived `party/contract` participants.

Это минимальный путь: runtime compile, fail-closed diagnostics и master-data gate уже реализованы отдельно.

### 2. Canonical producer path блокирует concrete participant refs для всех новых и новых ревизий execution packs

Отдельный opt-in marker для “template-compatible mode” не нужен.

После rollout этого change canonical create/revise path в `/pools/execution-packs` должен считать topology-aware contract обязательным для reusable execution logic:
- если slot использует topology-derived `party` или `contract` participants, authoring обязан использовать aliases;
- если revision остаётся concrete-ref-bound, publish/revise завершается fail-closed;
- historical rows остаются вне scope и не repair'ятся этим change.

Rationale:
- исчезает двусмысленность, когда именно включать строгую проверку;
- reusable execution pack перестаёт зависеть от скрытого policy intent;
- `/pools/catalog` остаётся consumer/assembly path, а не местом принятия решения о “правильности” reusable logic.

### 3. Совместимость template <-> execution pack должна проверять не только slot coverage

Текущего summary вида `matched/missing slots` недостаточно. Для reusable template path нужен ещё один blocking dimension:
- slot реализован structurally;
- slot реализован topology-aware master-data contract'ом, а не concrete refs.

Иначе execution pack формально совместим по `slot_key`, но всё ещё не reusable между разными `pool`.

### 4. Concrete participant refs запрещаются только для topology-derived participants reusable path

Запрет не является глобальным для любого `document_policy`.

Для новых/revised execution packs в template-oriented path:
- `party` и `contract`, происходящие из topology edge, должны использовать topology-aware aliases;
- static canonical tokens для `item` и `tax_profile` остаются допустимыми;
- existing historical packs вне scope этого change.

### 5. Stable diagnostics и compatibility summary должны быть общими для producer и consumer path

Execution-pack create/revise path и template-based attach path должны использовать один и тот же semantic classification contract.

Минимально нужны:
- machine-readable code для concrete-ref-bound reusable logic;
- diagnostic payload с `slot_key`, decision revision reference и `field_or_table_path`;
- compatibility summary, где structural slot coverage и master-data contract readiness видны отдельно.

Rationale:
- backend и frontend не расходятся в трактовке одной и той же проблемы;
- `/pools/execution-packs` объясняет, что именно надо исправить;
- `/pools/catalog` может fail-close'ить attach/preview/save без повторного “угадывания” причины.

### 6. `/pools/catalog` остаётся consumer/assembly surface

`/pools/catalog` не должен silently repair'ить reusable logic и не должен author'ить hardcoded participant refs inline.

Его задача:
- materialize concrete topology из template + slot assignments;
- выбрать reusable execution pack;
- проверить topology-aware compatibility;
- fail-closed заблокировать attach/preview/run и отдать handoff в `/pools/execution-packs` и `/decisions`, если выбранный pack остаётся concrete-ref-bound.

## Альтернативы

### Auto-rewrite concrete refs в alias contract на attach path

Отклонено. Attach path не знает авторское намерение для всех topology-derived fields и не должен silently переписывать reusable logic как side effect consumer flow.

### Хранить concrete participant refs на уровне template или pool

Отклонено. Это ломает reusable ownership границы и возвращает систему к hardcoded pool-specific contract вместо template + execution pack reuse.

## Риски / Trade-offs

- Требуется semantic classification decision policies по field mappings, а не только structural slot coverage.
  - Mitigation: классифицировать только topology-derived `party/contract` refs и не считать `item/tax_profile` drift'ом.
- Historical execution packs останутся существовать параллельно.
  - Mitigation: явно зафиксировать, что change покрывает только новые/revised template-oriented resources и должен блокировать shipped default path, а не repair historical residue.

## Migration Plan

1. Добавить semantic validation и stable diagnostics на create/revise reusable execution packs.
2. Добавить compatibility classification для reusable template/execution-pack pairing с отдельными structural и master-data markers.
3. Добавить blocking diagnostics и handoffs в `/pools/execution-packs` и `/pools/catalog`.
4. Нормализовать docs и UI copy на `/pools/execution-packs` как canonical route.
5. Обновить operator docs для new/revised path.

Destructive reset или cleanup historical pools/execution packs остаётся отдельным последующим change.
