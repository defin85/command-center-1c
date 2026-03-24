## 1. Контракт
- [x] 1.1 Зафиксировать в spec, что `/decisions` поддерживает отдельный clone flow для независимого decision resource, а не только revise/rollover одного и того же `decision_table_id`.
- [x] 1.2 Зафиксировать, что clone использует source revision только как editable seed, публикует новый `decision_table_id` без `parent_version_id` и не обходит target metadata validation.
- [x] 1.3 Зафиксировать analyst-facing distinction между `rollover` и `clone`: rollover создаёт новую revision существующего ресурса, clone создаёт новый independent resource.

## 2. Frontend clone flow
- [x] 2.1 Добавить на `/decisions` explicit action `Clone selected revision` для поддерживаемых `document_policy` revisions.
- [x] 2.2 Открывать editor в clone mode с предзаполненным policy/name/description, editable `decision_table_id` и без `parent_version_id`.
- [x] 2.3 Показать source summary и copy, явно объясняющие independent clone semantics и отсутствие auto-rebind.
- [x] 2.4 Переиспользовать existing save path так, чтобы publish clone отправлял create payload с новым `decision_table_id`, текущим target database context и без `parent_version_id`.

## 3. Проверки
- [x] 3.1 Добавить frontend tests на entry point clone flow, payload publish и copy про independent resource semantics.
- [x] 3.2 Прогнать релевантные `vitest` и `openspec validate add-decision-revision-clone-flow --strict --no-interactive`.
