## Context
`extensions.set_flags` — зарезервированный capability, который использует business-input `extension_name`, но исполняется через schema-driven `ibcmd_cli` команду с собственной схемой `params_by_name`.

Сейчас связь между `extension_name` и конкретным command param не является явным контрактом: это зависит от ручной конфигурации `params`/`additional_args` и токенов, что приводит к runtime-ошибкам драйвера.

## Goals / Non-Goals
- Goals:
  - Сделать маппинг таргета (`extension_name`) явным и проверяемым на config-time.
  - Убрать класс ошибок “обязательный параметр команды не подставлен” из runtime.
  - Сохранить текущий action-механизм и не ломать планирование/preview UX.
- Non-Goals:
  - Не проектировать универсальный binding-DSL для всех capability.
  - Не менять модель `extensions_flags_policy` и `apply_mask`.

## Decisions
- Decision: добавить capability-specific поле `executor.target_binding.extension_name_param` для `extensions.set_flags`.
  - Why: поле компактное, однозначное и достаточно для текущего проблемного класса (`name`/`extension` и т.п.).
- Decision: валидацию binding выполнять при обновлении `ui.action_catalog` (fail-closed), сверяя binding с effective driver catalog (`params_by_name`).
  - Why: ошибка должна выявляться до запуска операции.
- Decision: plan/apply подставляет `extension_name` в bound param перед preview/execute, а не пытается угадывать binding по токенам.
  - Why: детерминированность и прогнозируемость поведения.
- Decision: совместимый режим НЕ вводится; rollout выполняется сразу в strict fail-closed без fallback.
  - Why: fallback сохраняет архитектурную неоднозначность и оставляет источник runtime-ошибок.
- Decision: UI Editor получает backend hints для `target_binding` и guided input.
  - Why: сократить шанс некорректной конфигурации и убрать “магические” неявные договорённости.

## Alternatives Considered
- Альтернатива A: оставаться на токенах (`$extension_name`) и просто улучшить ошибки.
  - Плюсы: минимальные изменения.
  - Минусы: не устраняет архитектурную неоднозначность; ошибки остаются runtime-first.
- Альтернатива B: автоматически извлекать binding из `additional_args`/`params`.
  - Плюсы: меньше новых полей.
  - Минусы: хрупкая эвристика, чувствительная к формату команд и пользовательским шаблонам.

Выбран вариант с явным полем binding как минимальный надёжный контракт.

## Risks / Trade-offs
- Риск: изменение является breaking для существующих `extensions.set_flags` actions без binding.
  - Mitigation: явная диагностика валидации + migration guide/чеклист обновления.
- Риск: в effective driver catalog могут быть неполные `params_by_name`.
  - Mitigation: fail-closed с понятной ошибкой “binding param not found in command schema”.
- Trade-off: добавляется ещё одно capability-specific поле в editor.
  - Benefit: устраняется неопределённость, которая сейчас приводит к продовым runtime-сбоям.

## Migration Plan
1. Добавить поддержку `executor.target_binding.extension_name_param` в schema и backend validation.
2. Обновить UI hints/editor для явного ввода binding.
3. Включить fail-closed проверку в plan/apply для `extensions.set_flags`.
4. Прогнать тесты и обновить операторскую документацию по заполнению binding.

## Open Questions
- Нет.
