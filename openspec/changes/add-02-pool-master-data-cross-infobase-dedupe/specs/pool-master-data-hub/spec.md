## ADDED Requirements

### Requirement: Cross-infobase semantic dedupe MUST формировать стабильный canonical source-of-truth с provenance
Система ДОЛЖНА (SHALL) уметь резолвить несколько source records одной tenant-scoped reusable entity family, пришедших из разных ИБ, в один стабильный canonical source-of-truth cluster, если explicit dedupe policy считает эти записи одной и той же бизнес-сущностью.

Система ДОЛЖНА (SHALL) сохранять provenance для каждого source record как минимум с полями:
- `source_database_id`;
- source object key (`ib_ref_key` или эквивалентный source reference/fingerprint);
- `origin_kind`;
- link на origin batch/job/launch;
- normalized match signals;
- resolution status/reason.

Если новый source record попадает в уже resolved cluster, система ДОЛЖНА (SHALL) переиспользовать existing canonical entity вместо создания duplicate canonical row из-за порядка поступления данных.

Система НЕ ДОЛЖНА (SHALL NOT) использовать target-local `ib_ref_key` как cross-infobase identity reusable entity.

#### Scenario: Две записи `Party` из разных ИБ сходятся в один canonical cluster
- **GIVEN** batch collection импортировал `Party` из `db-1` и `db-2`
- **AND** entity-specific dedupe policy распознаёт их как одну и ту же бизнес-сущность
- **WHEN** система выполняет semantic dedupe
- **THEN** создаётся или переиспользуется один canonical `Party`
- **AND** provenance хранит оба source records отдельно
- **AND** binding/ref данные каждой ИБ остаются target-local, а не становятся global identity

#### Scenario: Повторный импорт не создаёт duplicate canonical entity для already-resolved cluster
- **GIVEN** canonical `Item` уже связан с resolved dedupe cluster
- **WHEN** новый source record из другой ИБ попадает в тот же cluster
- **THEN** система переиспользует существующий canonical `Item`
- **AND** не создаёт второй canonical row только из-за нового порядка ingress

### Requirement: Cross-infobase semantic dedupe MUST быть registry-driven и fail-closed
Система ДОЛЖНА (SHALL) описывать automatic cross-infobase dedupe через backend-owned executable registry policy per entity type.

Registry policy ДОЛЖЕН (SHALL) определять как минимум:
- разрешён ли automatic dedupe для entity type;
- identity signals и normalization rules;
- deterministic survivor precedence;
- review-required conditions;
- rollout eligibility.

Система ДОЛЖНА (SHALL) трактовать отсутствие explicit dedupe capability как запрет на automatic cross-infobase dedupe и automatic source-of-truth promotion.

Система НЕ ДОЛЖНА (SHALL NOT) автоматически dedupe'ить entity type только потому, что он bootstrap-capable, token-exposed или sync-capable.

#### Scenario: Entity type без dedupe capability не auto-merge'ится
- **GIVEN** registry не объявляет automatic dedupe capability для `gl_account_set`
- **WHEN** collection/inbound ingress приносит несколько похожих source records этого типа
- **THEN** система не выполняет implicit automatic merge
- **AND** type остаётся fail-closed относительно automatic source-of-truth promotion

#### Scenario: Новый entity type не становится dedupe-capable из-за одного enum/API entry
- **GIVEN** команда добавила новый reusable entity type в API surface
- **WHEN** registry policy для cross-infobase dedupe ещё не объявлена
- **THEN** automatic dedupe и automatic canonical promotion остаются заблокированными
- **AND** система не считает этот type доставленным только по факту появления в enum или endpoint namespace

### Requirement: Ambiguous dedupe MUST создавать review-required resolution и блокировать source-of-truth consumption
Если source records частично совпадают, но explicit dedupe policy не может безопасно принять automatic resolution, система ДОЛЖНА (SHALL) создавать persisted review-required resolution item.

Review item ДОЛЖЕН (SHALL) включать как минимум:
- `entity_type`;
- candidate cluster identifier;
- `reason_code`;
- `conflicting_fields`;
- список source records;
- proposed survivor/result, если он уже вычислен.

Система ДОЛЖНА (SHALL) блокировать outbound rollout/manual sync launch/publication для affected canonical scope, пока resolution status не станет `resolved_auto` или `resolved_manual`.

Система ДОЛЖНА (SHALL) возвращать machine-readable blocker/outcome code `MASTER_DATA_DEDUPE_REVIEW_REQUIRED` или эквивалентный canonical code этого семейства.

Система НЕ ДОЛЖНА (SHALL NOT) silently выбирать canonical survivor в ambiguous case.

#### Scenario: Неоднозначный `Contract` создаёт review item вместо automatic merge
- **GIVEN** source records `Contract` из двух ИБ совпадают по части identity signals, но конфликтуют по owner-scoped данным
- **WHEN** система выполняет semantic dedupe
- **THEN** создаётся review-required resolution item с machine-readable `reason_code`
- **AND** canonical source-of-truth не продвигается автоматически дальше по pipeline

#### Scenario: Unresolved dedupe блокирует rollout/publication consumption
- **GIVEN** canonical `Party` связан с dedupe cluster в статусе `pending_review`
- **WHEN** runtime пытается использовать эту сущность для outbound rollout или publication
- **THEN** side effects блокируются fail-closed
- **AND** оператор получает machine-readable blocker `MASTER_DATA_DEDUPE_REVIEW_REQUIRED`
