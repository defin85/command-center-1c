## ADDED Requirements

### Requirement: `/pools/catalog` MUST hand off reusable topology template authoring to dedicated workspace
Система ДОЛЖНА (SHALL) рассматривать `/pools/catalog` как consumer path для topology template instantiation, а reusable topology template authoring ДОЛЖНА (SHALL) выполнять через dedicated route `/pools/topology-templates`.

Если оператору в `/pools/catalog` не хватает подходящего topology template или нужно изменить reusable shape graph, интерфейс НЕ ДОЛЖЕН (SHALL NOT) оставлять его в dead-end состоянии с требованием вручную заполнять catalog вне UI.

#### Scenario: В topology editor отсутствует подходящий reusable template
- **GIVEN** оператор открыл `/pools/catalog` и находится в template-based topology path
- **AND** topology template catalog пуст или в нём нет подходящей reusable схемы
- **WHEN** оператору нужно создать новый reusable template
- **THEN** UI показывает явный handoff в `/pools/topology-templates`
- **AND** оператору не нужно покидать product surface ради прямого API-вызова

### Requirement: Handoff между `/pools/catalog` и `/pools/topology-templates` MUST сохранять pool topology context
Система ДОЛЖНА (SHALL) сохранять selected `pool`, topology task context и relevant return state при переходе из `/pools/catalog` в `/pools/topology-templates` и обратно.

Возврат из reusable template workspace НЕ ДОЛЖЕН (SHALL NOT) требовать повторного ручного выбора `pool` и topology task, если оператор пришёл из конкретного pool context.

#### Scenario: Оператор возвращается из reusable template workspace в тот же pool topology task
- **GIVEN** оператор открыл `/pools/catalog` для конкретного `pool` и перешёл в `/pools/topology-templates` через topology handoff
- **WHEN** он завершает create или revise flow reusable template и возвращается назад
- **THEN** `/pools/catalog` восстанавливает тот же `pool` и topology task context
- **AND** оператор может продолжить instantiation без повторного ручного выбора нужного pool
