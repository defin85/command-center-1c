## MODIFIED Requirements

### Requirement: Manual sync launch MUST поддерживать target mode `cluster_all` и `database_set`
Система ДОЛЖНА (SHALL) принимать operator-initiated manual sync launch request в одном из режимов:
- `inbound`;
- `outbound`;
- `reconcile`.

Launch request ДОЛЖЕН (SHALL) поддерживать target mode:
- `cluster_all` — все базы выбранного кластера, для которых explicit `cluster_all` eligibility state равен `eligible`;
- `database_set` — явный список выбранных ИБ.

Для `cluster_all` система ДОЛЖНА (SHALL) оценивать каждую базу выбранного кластера по machine-readable eligibility state:
- `eligible` — база включается в immutable target snapshot;
- `excluded` — база не включается в target snapshot и публикуется в resolution diagnostics как intentional exclusion;
- `unconfigured` — create request отклоняется fail-closed, parent launch request не создаётся.

Система ДОЛЖНА (SHALL) фиксировать immutable snapshot реально включённых target databases в момент принятия запроса и сохранять resolution summary по `excluded` базам для operator-facing history/detail.

Система НЕ ДОЛЖНА (SHALL NOT) переписывать target snapshot уже созданного launch request, если после этого изменился состав кластера, eligibility state или список доступных ИБ.

Система НЕ ДОЛЖНА (SHALL NOT) выводить eligibility для `cluster_all` только из runtime readiness, OData health, metadata snapshot или других эвристик без явного operator-managed state.

#### Scenario: Cluster-wide launch включает только `eligible` базы и сохраняет exclusions
- **GIVEN** оператор создаёт launch request с `target_mode=cluster_all`
- **AND** в выбранном кластере есть `db-1` и `db-2` со state `eligible`, а `db-3` со state `excluded`
- **WHEN** API принимает запрос
- **THEN** immutable target snapshot содержит только `db-1` и `db-2`
- **AND** launch detail сохраняет machine-readable resolution summary, что `db-3` был исключён из `cluster_all`
- **AND** parent launch request создаётся успешно

#### Scenario: `cluster_all` блокируется, пока по базе не принято явное решение
- **GIVEN** оператор создаёт launch request с `target_mode=cluster_all`
- **AND** в выбранном кластере есть хотя бы одна база `db-4` со state `unconfigured`
- **WHEN** API валидирует request
- **THEN** запрос отклоняется fail-closed с machine-readable diagnostic
- **AND** parent launch request не создаётся

#### Scenario: `database_set` не ломается из-за `cluster_all` eligibility state
- **GIVEN** оператор отправляет manual launch с `target_mode=database_set`
- **AND** одна из выбранных баз имеет `cluster_all` eligibility state `excluded`
- **WHEN** запрос проходит обычные tenant/access/policy проверки
- **THEN** eligibility state для `cluster_all` сам по себе не отклоняет `database_set` request
- **AND** explicit database selection остаётся допустимым operator override path
