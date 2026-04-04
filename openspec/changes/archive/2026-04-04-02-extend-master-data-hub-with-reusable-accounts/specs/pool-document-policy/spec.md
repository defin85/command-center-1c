## ADDED Requirements

### Requirement: Document policy mapping MUST поддерживать canonical GLAccount tokens с metadata-aware validation
Система ДОЛЖНА (SHALL) поддерживать token `master_data.gl_account.<canonical_id>.ref` в `field_mapping` и других совместимых mapping surfaces `document_policy`.

Compile/validation path ДОЛЖЕН (SHALL):
- проверять существование field path в metadata snapshot;
- проверять, что field path типизирован как ссылка на chart-of-accounts object;
- использовать reusable-data binding semantics для target ИБ.

Система НЕ ДОЛЖНА (SHALL NOT) принимать account token только по heuristics имени поля или по свободной строке account code.

#### Scenario: Account token компилируется для типизированного chart-of-accounts field
- **GIVEN** policy использует `master_data.gl_account.sales-revenue.ref`
- **AND** target metadata snapshot подтверждает, что выбранное поле является ссылкой на chart-of-accounts object
- **WHEN** runtime выполняет compile document plan
- **THEN** token считается валидным reusable-data reference
- **AND** downstream publication получает canonical account binding contract

#### Scenario: Name heuristic не заменяет typed metadata validation
- **GIVEN** поле документа содержит в имени слово, похожее на бухгалтерский счёт
- **AND** metadata snapshot не подтверждает chart-of-accounts reference semantics
- **WHEN** policy пытается использовать `master_data.gl_account.*.ref`
- **THEN** compile завершается fail-closed
- **AND** система не принимает token только из-за совпавшего имени поля
