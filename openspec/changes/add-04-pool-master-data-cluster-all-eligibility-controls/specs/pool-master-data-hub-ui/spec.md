## ADDED Requirements

### Requirement: Sync launcher MUST показывать cluster-all eligibility diagnostics и handoff в `/databases`
Система ДОЛЖНА (SHALL) в `Launch Sync` drawer для `target_mode=cluster_all` показывать operator-facing summary по выбранному кластеру:
- количество `eligible` баз, которые войдут в launch snapshot;
- количество и список `excluded` баз, которые не войдут в snapshot;
- количество `unconfigured` баз, которые блокируют запуск.

UI ДОЛЖЕН (SHALL) явно объяснять, что:
- `eligible` базы будут включены в `cluster_all`;
- `excluded` базы намеренно не войдут в cluster-wide launch;
- `unconfigured` базы требуют operator decision в `/databases` до запуска.

При наличии `unconfigured` баз launcher НЕ ДОЛЖЕН (SHALL NOT) позволять submit и ДОЛЖЕН (SHALL) предлагать handoff в canonical `/databases` surface.

#### Scenario: Launcher блокирует `cluster_all` и отправляет оператора в `/databases`
- **GIVEN** оператор открыл `/pools/master-data?tab=sync`
- **AND** выбрал `target_mode=cluster_all` и конкретный кластер
- **AND** в этом кластере есть хотя бы одна `unconfigured` база
- **WHEN** UI загружает cluster eligibility summary
- **THEN** submit action остаётся заблокированной
- **AND** UI показывает machine-readable объяснение причины блокировки
- **AND** оператор получает явный handoff в `/databases` для исправления eligibility

#### Scenario: Launcher показывает excluded members без ложного обещания запуска
- **GIVEN** оператор выбрал `cluster_all` для кластера, где часть баз помечена `excluded`
- **WHEN** UI показывает eligibility summary
- **THEN** интерфейс явно сообщает, что эти базы не войдут в launch snapshot
- **AND** оператор не воспринимает `cluster_all` как запуск по всем базам кластера без исключений

### Requirement: Sync launcher MUST подсказывать explicit override path для исключений
Если оператору нужен разовый запуск по базе, которая не входит в текущий `cluster_all` snapshot, UI ДОЛЖЕН (SHALL) объяснять, что для этого используется `target_mode=database_set`, а не неявное расширение `cluster_all`.

#### Scenario: Оператор видит путь для one-off запуска по исключённой базе
- **GIVEN** выбранный кластер содержит базы со state `excluded`
- **WHEN** оператор изучает eligibility diagnostics в `Launch Sync` drawer
- **THEN** UI подсказывает, что one-off запуск для таких баз выполняется через `database_set`
- **AND** launcher не пытается silently включить их в `cluster_all`
