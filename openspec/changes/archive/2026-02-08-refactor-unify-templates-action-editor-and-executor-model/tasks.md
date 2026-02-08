## 1. Spec & Contract Alignment
- [x] 1.1 Обновить `operation-templates`: закрепить единый modal editor UX для `template` и `action_catalog` внутри `/templates`.
- [x] 1.2 Обновить `ui-action-catalog-editor`: закрепить shared editor component/pipeline для двух surfaces и убрать обязательность ручного `driver` выбора.
- [x] 1.3 Обновить `operation-definitions-catalog`: зафиксировать canonical mapping `executor.kind -> driver` и fail-closed валидацию mismatch.

## 2. Frontend: Unified Editor UX
- [x] 2.1 Выделить общий `OperationExposureEditor` (action-style tabs) и подключить его для templates surface.
- [x] 2.2 Перенести template-specific поля в единый editor shell без отдельной modal-ветки `DriverCommandBuilder`.
- [x] 2.3 Удалить в unified editor ручной selector `driver` для canonical kinds; `driver` должен выводиться/деривироваться автоматически.
- [x] 2.4 Выровнять сериализацию/десериализацию template/action через единый adapter слой и закрыть расхождения execution payload.

## 3. Backend: Canonical Executor Model
- [x] 3.1 Добавить нормализацию executor payload на write-path (`kind/driver` canonicalization).
- [x] 3.2 Добавить fail-closed валидацию конфликтных комбинаций `kind/driver`.
- [x] 3.3 Обновить fingerprint/dedup логику так, чтобы redundant `driver` не создавал отдельные definition при canonical kinds.
- [x] 3.4 Добавить migration/normalization для существующих unified records + diagnostics для неавтоматически разрешимых конфликтов.

## 4. Verification & Documentation
- [x] 4.1 Обновить frontend unit/e2e тесты для единого editor UX (Templates + Action Catalog parity).
- [x] 4.2 Обновить backend тесты нормализации/валидации/migration по `kind/driver`.
- [x] 4.3 Обновить docs операторов (`/templates`) и release notes по breaking-change.
- [x] 4.4 Прогнать `openspec validate refactor-unify-templates-action-editor-and-executor-model --strict --no-interactive`.
