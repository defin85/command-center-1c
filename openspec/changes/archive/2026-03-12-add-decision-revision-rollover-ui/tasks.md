## 1. UX и surface `/decisions`
- [x] 1.1 Спроектировать explicit rollover entry point в `/decisions` для сценария "создать новую revision для выбранной ИБ из существующей revision".
- [x] 1.2 Обновить список/detail surface так, чтобы аналитик мог выбрать revision вне default compatible selection как source для rollover flow без снятия fail-closed ограничений на публикацию.
- [x] 1.3 Добавить в editor/source-target summary явные маркеры `source revision`, `target database` и target metadata context перед сохранением.

## 2. Publish semantics
- [x] 2.1 Переиспользовать существующий create/revise path `/api/v2/decisions` с `parent_version_id` и `database_id`, не вводя отдельный mutate endpoint без доказанной необходимости.
- [x] 2.2 Явно зафиксировать в UI, что rollover flow создаёт новую revision и не перепривязывает существующие workflow/binding consumers автоматически.
- [x] 2.3 Сохранить fail-closed поведение: новая revision публикуется только если source policy проходит validation против resolved metadata snapshot выбранной ИБ.

## 3. Проверка
- [x] 3.1 Добавить frontend tests на guided rollover из revision предыдущего релиза / вне target compatible set под новую ИБ, включая source-target summary и корректный `postDecisionsCollection` payload.
- [x] 3.2 Добавить/обновить тесты на fail-closed publish при несовместимости source policy с target metadata snapshot.
- [x] 3.3 Прогнать минимальный релевантный verification set (`vitest` по `/Decisions` и точечные backend tests только если будут затронуты API semantics) и зафиксировать результаты.
