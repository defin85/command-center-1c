## ADDED Requirements
### Requirement: Publication attempts projection MUST агрегировать результаты всех atomic `publication_odata` nodes
Workflow status updater MUST строить attempts read-model не из первого найденного publication payload, а из полного набора atomic publication nodes текущего execution.

#### Scenario: Run report включает попытки из всех publication_odata узлов
- **GIVEN** workflow execution содержит несколько atomic publication nodes
- **WHEN** status updater проецирует attempts в run read-model
- **THEN** `pool_publication_attempts` отражает совокупность всех узлов текущего execution
- **AND** UI report не теряет успешные и failed attempts из отдельных atomic шагов

### Requirement: Run inspection read-model MUST включать readiness и verification статусы в стабильной структуре
Pools facade MUST возвращать в run/report детерминированные поля `readiness_blockers`, `verification_status` и `verification_summary`, чтобы оператор мог пройти весь процесс без анализа внутренних payload.

#### Scenario: Оператор получает единый прозрачный статус run
- **GIVEN** run прошёл readiness preflight и post-run verification
- **WHEN** оператор запрашивает run report
- **THEN** ответ содержит стабильную структуру readiness и verification полей
- **AND** отсутствие данных возвращается как явное состояние (`not_ready`/`not_verified`), а не молчаливый пропуск
