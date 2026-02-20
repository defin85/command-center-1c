## 0. Coordination and Sequencing
- [ ] 0.1 Зафиксировать, что `refactor-04` реализуется в два UI-трека:
  - Track UI-A: declutter IA (`/pools/catalog`, `/pools/runs`) и progressive disclosure.
  - Track UI-B: финальная интеграция diagnostics с observability полями из `refactor-03`.
- [ ] 0.2 Зафиксировать blocker для Track UI-B: стабилизированные поля `/operations` (`root_operation_id`, `execution_consumer`, `lane`) и согласованные client types.
- [ ] 0.3 Согласовать fallback-поведение UI на миграционное окно до закрытия Track UI-B (без блокировки основной работы оператора).

## 1. UX Baseline и scope фиксация
- [ ] 1.1 Зафиксировать текущие overloaded-участки `/pools/catalog`, `/pools/runs`, `/pools/templates` (скриншоты + краткий сценарный аудит).
- [ ] 1.2 Утвердить целевую IA-структуру страниц (task zones/tabs, состав primary/secondary actions, advanced disclosure).

## 2. `/pools/catalog` — task-oriented разбиение (приоритет 1)
- [ ] 2.1 Разделить сценарии каталога на отдельные рабочие зоны (организации, пулы, topology editing, graph preview) без потери существующего функционала.
- [ ] 2.2 Сократить одновременно видимые действия и поля до контекста активной зоны; сохранить tenant-safe guard для mutating actions.
- [ ] 2.3 Вынести advanced JSON/metadata-поля topology editor в отдельный раскрываемый слой (по умолчанию скрыт).

## 3. `/pools/runs` — stage-based workflow (приоритет 1)
- [ ] 3.1 Разделить сценарии create/inspect/safe/retry на отдельные логические этапы UI.
- [ ] 3.2 Сохранить единый контекст выбранного run между этапами (без ручного повторного выбора на каждом шаге).
- [ ] 3.3 Перевести heavy diagnostics (`Run Input`, summaries, diagnostics JSON) в progressive disclosure.

## 4. `/pools/templates` — baseline retention
- [ ] 4.1 Подтвердить, что существующий edit-flow (`Edit` action + create/edit modal + prefill + JSON validation) не деградирует после declutter.
- [ ] 4.2 Подтвердить совместимость update endpoint (`PUT /api/v2/pools/schema-templates/{template_id}/`) и связанных контрактов/типов.
- [ ] 4.3 Добавить UX-полировку формы шаблонов только при необходимости, без расширения scope change.

## 5. Diagnostics Integration with Runtime Contract (Track UI-B)
- [ ] 5.1 Привязать diagnostics UI к финальным observability полям из `refactor-03` после стабилизации контрактов.
- [ ] 5.2 Убрать временные адаптеры/ветвления parsing логики после завершения миграционного окна.

## 6. Тесты и валидация поведения
- [ ] 6.1 Добавить/обновить frontend tests для новых IA-сценариев, stage-flow и progressive disclosure.
- [ ] 6.2 Добавить/обновить backend tests и contract checks для шаблонов и diagnostics-интеграции (если контракт затронут).
- [ ] 6.3 Прогнать релевантные линтеры и целевые тестовые наборы (`ruff`, frontend `vitest`, OpenSpec validation).

## 7. Контроль качества UX
- [ ] 7.1 Провести smoke-проход операторских сценариев на трёх страницах и зафиксировать, что количество одновременно видимых controls уменьшилось.
- [ ] 7.2 Подготовить короткий post-change UX report (что стало проще, какие advanced блоки скрыты по умолчанию).
