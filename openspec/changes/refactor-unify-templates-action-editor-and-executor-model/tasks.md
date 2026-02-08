## 1. Spec & Contract Alignment
- [ ] 1.1 Обновить `operation-templates`: закрепить единый modal editor UX для `template` и `action_catalog` внутри `/templates`.
- [ ] 1.2 Обновить `ui-action-catalog-editor`: закрепить shared editor component/pipeline для двух surfaces и убрать обязательность ручного `driver` выбора.
- [ ] 1.3 Обновить `operation-definitions-catalog`: зафиксировать canonical mapping `executor.kind -> driver` и fail-closed валидацию mismatch.

## 2. Frontend: Unified Editor UX
- [ ] 2.1 Выделить общий `OperationExposureEditor` (action-style tabs) и подключить его для templates surface.
- [ ] 2.2 Перенести template-specific поля в единый editor shell без отдельной modal-ветки `DriverCommandBuilder`.
- [ ] 2.3 Удалить в unified editor ручной selector `driver` для canonical kinds; `driver` должен выводиться/деривироваться автоматически.
- [ ] 2.4 Выровнять сериализацию/десериализацию template/action через единый adapter слой и закрыть расхождения execution payload.

## 3. Backend: Canonical Executor Model
- [ ] 3.1 Добавить нормализацию executor payload на write-path (`kind/driver` canonicalization).
- [ ] 3.2 Добавить fail-closed валидацию конфликтных комбинаций `kind/driver`.
- [ ] 3.3 Обновить fingerprint/dedup логику так, чтобы redundant `driver` не создавал отдельные definition при canonical kinds.
- [ ] 3.4 Добавить migration/normalization для существующих unified records + diagnostics для неавтоматически разрешимых конфликтов.

## 4. Verification & Documentation
- [ ] 4.1 Обновить frontend unit/e2e тесты для единого editor UX (Templates + Action Catalog parity).
- [ ] 4.2 Обновить backend тесты нормализации/валидации/migration по `kind/driver`.
- [ ] 4.3 Обновить docs операторов (`/templates`) и release notes по breaking-change.
- [ ] 4.4 Прогнать `openspec validate refactor-unify-templates-action-editor-and-executor-model --strict --no-interactive`.
