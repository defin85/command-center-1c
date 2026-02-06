# Spec Delta: extensions-action-catalog

## ADDED Requirements
### Requirement: `extensions.set_flags` MUST иметь явный target binding
Система ДОЛЖНА (SHALL) требовать для actions с `capability="extensions.set_flags"` явный маппинг бизнес-таргета расширения в command-level параметр через поле `executor.target_binding.extension_name_param`.

#### Scenario: Валидный binding задан
- **GIVEN** action имеет `capability="extensions.set_flags"`
- **AND** `executor.target_binding.extension_name_param` задан непустой строкой
- **WHEN** каталог проходит валидацию
- **THEN** binding принимается как контракт target-мэппинга для данного action

#### Scenario: Binding отсутствует
- **GIVEN** action имеет `capability="extensions.set_flags"`
- **AND** `executor.target_binding.extension_name_param` отсутствует или пуст
- **WHEN** staff сохраняет `ui.action_catalog`
- **THEN** backend отклоняет сохранение с ошибкой валидации (fail-closed)

### Requirement: Binding для `extensions.set_flags` MUST валидироваться против схемы команды
Система ДОЛЖНА (SHALL) проверять, что `executor.target_binding.extension_name_param` существует в `commands_by_id.<command_id>.params_by_name` выбранной команды.

#### Scenario: Binding указывает на неизвестный параметр команды
- **GIVEN** `executor.command_id` указывает на валидную команду драйвера
- **AND** `executor.target_binding.extension_name_param` не найден в `params_by_name` этой команды
- **WHEN** staff сохраняет `ui.action_catalog`
- **THEN** backend возвращает ошибку валидации с путём до `executor.target_binding.extension_name_param`
- **AND** каталог не сохраняется

#### Scenario: Binding указывает на параметр из schema команды
- **GIVEN** `executor.target_binding.extension_name_param` совпадает с ключом в `params_by_name` выбранной команды
- **WHEN** staff сохраняет `ui.action_catalog`
- **THEN** валидация binding проходит успешно
