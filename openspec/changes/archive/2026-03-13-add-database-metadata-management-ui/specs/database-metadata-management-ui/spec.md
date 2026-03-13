## ADDED Requirements
### Requirement: `/databases` MUST предоставлять канонический metadata management surface для выбранной ИБ
Система ДОЛЖНА (SHALL) предоставлять на route `/databases` operator-facing surface для управления configuration profile и metadata snapshot выбранной информационной базы без использования ручного API-клиента.

Этот surface ДОЛЖЕН (SHALL) быть доступен из per-database actions existing UI и показывать как минимум:
- `config_name`;
- `config_version`;
- `config_generation_id`;
- verification status и relevant timestamps;
- `snapshot_id`;
- `resolution_mode`;
- `metadata_hash`;
- `observed_metadata_hash`;
- `publication_drift`;
- `provenance_database_id`.

Change НЕ ДОЛЖЕН (SHALL NOT) требовать отдельный top-level route, если тот же contract можно разместить как panel/drawer внутри `/databases`.

#### Scenario: Оператор открывает metadata management surface из `/databases`
- **GIVEN** оператор работает со списком баз на `/databases`
- **WHEN** он открывает metadata management controls конкретной ИБ
- **THEN** UI показывает отдельно business identity / reuse key и metadata snapshot state
- **AND** оператору не требуется переходить в `/pools/catalog` или использовать ручной API-клиент для базового осмотра состояния

### Requirement: `/databases` MUST явно разделять re-verify identity и refresh snapshot
Система ДОЛЖНА (SHALL) предоставлять в metadata management surface два разных действия:
- `Re-verify configuration identity`;
- `Refresh metadata snapshot`.

UI ДОЛЖЕН (SHALL) явно объяснять, что:
- `Re-verify configuration identity` относится к business identity / reuse key конфигурации и ведёт через async operation path;
- `Refresh metadata snapshot` относится к содержимому metadata snapshot и publication drift diagnostics;
- эти действия НЕ ДОЛЖНЫ (SHALL NOT) быть объединены под одним двусмысленным control label.

#### Scenario: Оператор запускает re-verify identity
- **GIVEN** у выбранной ИБ нужно перепроверить `config_name/config_version` и verification state
- **WHEN** оператор нажимает `Re-verify configuration identity`
- **THEN** UI запускает async flow и показывает machine-readable outcome или handoff в `/operations`
- **AND** текст UI не выдаёт этот запуск за обычный snapshot refresh

#### Scenario: Оператор запускает refresh metadata snapshot
- **GIVEN** у выбранной ИБ нужно обновить нормализованный metadata snapshot
- **WHEN** оператор нажимает `Refresh metadata snapshot`
- **THEN** UI обновляет snapshot state и drift markers
- **AND** текст UI не выдаёт это действие за перепроверку business identity конфигурации

### Requirement: `/databases` MUST показывать fail-closed state и actionable guidance
Если current profile или current snapshot отсутствует, находится в переходном состоянии или требует пользовательского вмешательства, metadata management surface ДОЛЖЕН (SHALL):
- показывать fail-closed status;
- объяснять, какой именно слой отсутствует (`configuration profile` vs `metadata snapshot`);
- подсказывать следующий допустимый action в рамках того же surface или через handoff в `/operations`.

Система НЕ ДОЛЖНА (SHALL NOT) скрывать отсутствие profile/snapshot за generic сообщением "reload metadata".

#### Scenario: UI различает отсутствие profile и отсутствие snapshot
- **GIVEN** для выбранной ИБ отсутствует verified configuration profile или отсутствует current metadata snapshot
- **WHEN** оператор открывает metadata management surface
- **THEN** UI показывает, какой именно слой недоступен
- **AND** предлагает подходящий следующий шаг вместо общего недиагностичного reload-сообщения
