## 1. Контракт и API
- [ ] 1.1 Зафиксировать в spec и API/read-model stateless two-phase contract для transfer workbench: server-evaluated `transfer preview` и `transfer publish` для concrete `decision_revision`.
- [ ] 1.2 Зафиксировать shape `transfer preview`: source revision, target database, resolved configuration profile / metadata snapshot и transfer report.
- [ ] 1.3 Зафиксировать metadata identity contract для transfer matching: primary signal — stable design-time IDs из `ConfigDumpInfo.xml`/`ibcmd`-enriched snapshot, fallback — canonical metadata path/name + type/shape.
- [ ] 1.4 Зафиксировать fail-closed правила `transfer publish`: publish повторно валидирует report и создаёт новую revision только после разрешения всех `ambiguous` / `missing` / `incompatible` элементов.
- [ ] 1.5 Зафиксировать provenance resulting revision и границу между default ready-to-pin selection и source-only transfer mode.

## 2. Backend transfer semantics
- [ ] 2.1 Реализовать enrichment metadata snapshot/read-model stable design-time IDs из `ConfigDumpInfo.xml`/`ibcmd`, не требуя от standard OData отдавать эти IDs напрямую.
- [ ] 2.2 Реализовать построение transfer report против target metadata snapshot выбранной ИБ с классификацией `matched` / `ambiguous` / `missing` / `incompatible`.
- [ ] 2.3 Реализовать fallback matching по canonical metadata path/name + type/shape для OData-only/partial-ID случаев и стандартных атрибутов без доступного design-time ID.
- [ ] 2.4 Реализовать server-side `transfer preview` как authoring/read-model surface без отдельного persistent draft artifact.
- [ ] 2.5 Переиспользовать существующий publish path так, чтобы `transfer publish` создавал новую concrete revision с `parent_version_id`, target metadata provenance и без auto-rebind consumers.
- [ ] 2.6 Добавить fail-closed validation errors для unresolved transfer items и отдать их в analyst-facing API/read-model.

## 3. Frontend analyst workbench
- [ ] 3.1 Добавить в `/decisions` явную entry point для transfer из source revision в target database context.
- [ ] 3.2 Показать source/target context, transfer report и guided remap surface для unresolved items.
- [ ] 3.3 Сохранить default compatible selection как primary ready-to-pin mode и отделить его от diagnostics/source-selection mode.

## 4. Проверки и документация
- [ ] 4.1 Добавить backend tests на ID-based matching, fallback matching, transfer report, publish новой revision, target provenance и fail-closed ошибки при unresolved remap.
- [ ] 4.2 Добавить frontend tests на transfer entry point, source/target context display, remap UX и отсутствие auto-rebind ожиданий.
- [ ] 4.3 Обновить analyst-facing docs по `/decisions`: transfer flow, ограничения auto-remap и различие между pin candidate и source template.
- [ ] 4.4 Прогнать `openspec validate add-decision-revision-transfer-workbench --strict --no-interactive` и релевантные contract/test validations.
