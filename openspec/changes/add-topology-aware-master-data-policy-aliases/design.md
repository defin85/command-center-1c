## Контекст

Текущий workflow-centric runtime уже умеет:
- materialize `slot_key -> document_policy` один раз на binding preview/create-run;
- компилировать `document_plan_artifact` per edge;
- запускать `master_data_gate` по canonical `master_data.*` токенам;
- блокировать publication, если для target organization отсутствует `Organization->Party` binding.

При этом current static master-data token contract уже покрывает все shipped entity types:
- `master_data.party.<canonical_id>.<role>.ref`
- `master_data.item.<canonical_id>.ref`
- `master_data.contract.<canonical_id>.<owner_counterparty>.ref`
- `master_data.tax_profile.<canonical_id>.ref`

Но reusable `document_policy` до сих пор topology-blind:
- party tokens требуют заранее знать `canonical_id`;
- contract tokens требуют заранее знать owner counterparty canonical id;
- один и тот же `receipt_leaf` policy нельзя безопасно переиспользовать на двух child edges с разными
  counterparties без копирования policy или literal GUID;
- для `top-down-pool` это уже привело к hardcoded counterparties в `realization` / `receipt`.

Отдельное ограничение: этот change НЕ меняет существующую модель ownership target database. Один edge продолжает
компилироваться в ту target database semantics, которые уже использует runtime. Change касается только того,
какие canonical participants подставляются в policy, а не того, в каких базах появляются paired sale/receipt
документы.

## Цели

- Сделать `document_policy` reusable across edges без hardcoded seller/buyer GUID.
- Сохранить `document_plan_artifact` как детерминированный downstream contract с уже нормализованными canonical
  `master_data.*` токенами.
- Явно сохранить поддержку всех текущих master-data entity types, а не сузить runtime contract до `party/contract`.
- Не тащить topology-aware alias grammar в `master_data_gate` и OData payload глубже, чем это необходимо.
- Определить fail-closed behavior для missing `Organization->Party` binding и missing role на topology participant.

## Не-цели

- Не менять current `slot_key -> policy` evaluation model на per-edge decision re-evaluation.
- Не вводить новый external dependency или новый expression engine.
- Не менять target-database ownership model для `document_plan_artifact`.
- Не синтезировать paired seller-side document автоматически, если topology/slots его явно не моделируют.
- Не менять existing static `master_data.party.<canonical>.*` и `master_data.contract.<canonical>.*` grammar.
- Не вводить topology-aware alias grammar для `item` и `tax_profile` в рамках этого change.
- Не реализовывать в этом change operator-facing UI/contract для выбора `item` и `tax_profile` на старте run;
  требуется только сохранить совместимый downstream contract для такого будущего path.

## Решение

### 0. Layered master-data token model

В этой схеме нужно явно развести два слоя:

- static canonical tokens как универсальный путь для всех текущих master-data entity types;
- topology-aware aliases как additive path только для participant-derived сущностей.

Это означает:
- `party`, `item`, `contract`, `tax_profile` продолжают поддерживаться через текущий static token grammar;
- новый alias dialect не подменяет и не сужает shipped static contract;
- любая future operator-driven подстановка `item` / `tax_profile` на старте run должна materialize'иться в те же
  static canonical tokens до downstream `master_data_gate`.

### 1. Вводим topology-aware alias grammar только для party/contract participants

Новый dialect:

- `master_data.party.edge.parent.organization.ref`
- `master_data.party.edge.parent.counterparty.ref`
- `master_data.party.edge.child.organization.ref`
- `master_data.party.edge.child.counterparty.ref`
- `master_data.contract.<contract_canonical_id>.edge.parent.ref`
- `master_data.contract.<contract_canonical_id>.edge.child.ref`

Семантика:
- `edge.parent` и `edge.child` адресуют организации активного topology edge;
- `organization` требует `Organization.master_party` с `is_our_organization=true`;
- `counterparty` требует тот же bound party с `is_counterparty=true`;
- `contract.<id>.edge.parent|child.ref` выбирает owner counterparty canonical id от соответствующего topology
  participant и после resolution переписывается в текущий static contract token format.

Ограничение по scope:
- `item` и `tax_profile` не получают `edge.parent|child` semantics, потому что topology сама по себе не несет
  business-значения "какая номенклатура" или "какая ставка НДС";
- для них сохраняется только static canonical token path;
- если позже оператор будет выбирать `item` / `tax_profile` при старте run, эти значения должны попадать в compile
  artifact как те же static canonical tokens, а не как отдельный topology alias dialect.

### 2. Резолвить aliases нужно в `document_plan_artifact` compile, а не в `master_data_gate`

Причины:
- artifact должен оставаться deterministic и audit-friendly;
- downstream `master_data_gate` уже умеет работать со static canonical token grammar;
- retry/readiness/publication path меньше меняется, если alias dialect не уходит ниже compile stage.

Алгоритм compile для каждого edge:
1. Найти `parent` и `child` node по `edge_ref`.
2. Взять `organization` из node model.
3. Для alias-bearing mapping значений получить `organization.master_party`.
4. Проверить наличие binding и нужной роли.
5. Переписать alias:
   - party alias -> `master_data.party.<canonical_id>.<role>.ref`
   - contract alias -> `master_data.contract.<contract_canonical_id>.<owner_counterparty_canonical_id>.ref`
6. Сохранить уже переписанные значения в `document_plan_artifact.targets[].chains[].documents[]`.

В результате `build_publication_payload_from_document_plan_artifact()` и `master_data_gate` продолжают работать с
canonical static token grammar и не зависят от topology alias syntax.

### 3. Fail-closed model

Новые и уточненные blocking состояния:

- `POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID`
  Используется, если token syntactically похож на topology-aware alias, но не соответствует допустимому grammar.

- `MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING`
  Используется, если `edge.parent` или `edge.child` organization не имеет `master_party`.

- `MASTER_DATA_PARTY_ROLE_MISSING`
  Используется, если `master_party` существует, но не несет требуемую роль:
  - `is_our_organization=true` для `organization`
  - `is_counterparty=true` для `counterparty`

Эти состояния должны блокировать preview/create-run до OData side effects.

### 4. Readiness должен считать topology participant blockers до publication

`Pool master-data hub` уже умеет возвращать blockers по `Organization->Party` binding и canonical entity resolve.
Новый change расширяет readiness semantics:

- alias resolution считается частью readiness/compile contract;
- blocker должен содержать `organization_id`, `database_id`, `edge_ref`, `participant_side` (`parent|child`) и
  `required_role` (`organization|counterparty`), если причина связана с topology participant;
- если alias переписан успешно, downstream readiness/gate использует уже обычные static token blockers;
- static tokens для `item` и `tax_profile` продолжают проходить через existing readiness/gate semantics без
  topology-derived participant resolution.

### 5. Migration/adoption path для `top-down`

После rollout capability:
- `realization` policy переводится на
  - `Организация_Key = master_data.party.edge.parent.organization.ref`
  - `Контрагент_Key = master_data.party.edge.child.counterparty.ref`
  - `ДоговорКонтрагента_Key = master_data.contract.<contract>.edge.child.ref`
- `receipt` policy переводится на
  - `Организация_Key = master_data.party.edge.child.organization.ref`
  - `Контрагент_Key = master_data.party.edge.parent.counterparty.ref`
  - `ДоговорКонтрагента_Key = master_data.contract.<contract>.edge.parent.ref`

Это дает один reusable `receipt` policy для `receipt_internal` и `receipt_leaf` без копирования по каждому child
organization.

`Item` и `TaxProfile` для этого же execution pack остаются static canonical refs. В будущем operator-facing выбор на
старте run может переопределять их через run-scoped parameters, но resulting compile artifact все равно должен
содержать static canonical `master_data.item.*.ref` / `master_data.tax_profile.*.ref`.

## Альтернативы и почему они отвергнуты

### Тянуть alias grammar в `master_data_gate`

Отвергнуто, потому что тогда:
- `document_plan_artifact` перестает быть concrete downstream contract;
- readiness/gate/retry получают второй источник topology semantics;
- debugging становится хуже, так как canonical participants не видны в compile artifact.

### Делать decision evaluation заново для каждого edge

Отвергнуто, потому что seller/buyer resolution здесь зависит не от новой decision logic, а от runtime topology
participants. Повторная evaluation сломает determinism и не нужна, если policy использует aliases.

### Хардкодить `realization-top-down`, `receipt-leaf-a`, `receipt-leaf-b`

Отвергнуто, потому что это не reusable path и снова превращает execution pack в набор pool-specific policy copies.

### Делать generic topology alias DSL сразу для всех master-data entity types

Отвергнуто, потому что у `item` и `tax_profile` сейчас нет естественной topology-derived semantics. Такой DSL только
смешает participant resolution с operator/business input и затруднит auditability.

## Риски и trade-offs

- Если некоторые `Organization.master_party` не имеют dual-role (`organization` + `counterparty`), rollout вскроет
  больше blockers, чем сейчас. Это ожидаемое fail-closed поведение.
- Topology-aware alias grammar расширяет contract `document_policy.v1`; нужна аккуратная обратная совместимость для
  existing static tokens.
- Перевод live `top-down` policies на alias dialect должен идти после rollout tests, иначе можно получить data drift
  между spec и фактическими decision revisions.
- Future operator-driven `item` / `tax_profile` selection потребует отдельного change на run-input / UI contract,
  но текущий change не должен его блокировать и не должен заранее зафиксировать несовместимый token path.
