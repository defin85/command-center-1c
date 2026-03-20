## 1. Спецификация usability-контракта
- [x] 1.1 Зафиксировать в `ui-web-interface-guidelines`, что stateful workspace routes обязаны синхронизировать primary filter/selection state с URL, а placeholder-only control names не считаются достаточным label path.
- [x] 1.2 Зафиксировать в `ui-web-interface-guidelines`, что primary selection в master-detail surfaces должна использовать semantic trigger и явный selected state, а не только row click или interactive `div`.
- [x] 1.3 Зафиксировать в `workflow-decision-modeling` task-first contract для `/decisions`: shareable route context, один явный primary authoring path, progressive disclosure для diagnostics/advanced data.
- [x] 1.4 Зафиксировать в `pool-binding-profiles` operator-first contract для `/pools/binding-profiles`: shareable catalog state, keyboard-first profile selection и summary-first detail hierarchy.

## 2. Shared shell и interaction baseline
- [x] 2.1 Добавить persistent labels/`aria-label` для tenant selector и route-level controls на `/decisions` и `/pools/binding-profiles`.
- [x] 2.2 Внедрить минимальный route-level URL-state sync для двух маршрутов без ввода нового глобального state framework, если локальная схема закрывает задачу проще.
- [x] 2.3 Устранить mouse-first selection patterns: заменить selection affordances на semantic controls с явным selected state и keyboard path.

## 3. `/decisions` remediation
- [x] 3.1 Синхронизировать `database`, `decision`, `snapshot filter` с query params и обеспечить корректный deep-link/back-forward path.
- [x] 3.2 Перестроить action hierarchy так, чтобы `New policy` оставался primary action, а import/secondary actions не конкурировали с основным authoring flow.
- [x] 3.3 Увести metadata-heavy diagnostics и advanced/raw authoring context в explicit progressive disclosure, сохранив handoff в `/databases`.
- [x] 3.4 Переписать page copy в task language, не требующем знания всей платформенной терминологии с первого экрана.

## 4. `/pools/binding-profiles` remediation
- [x] 4.1 Синхронизировать `search`, `selected profile`, `detail drawer` с query params и обеспечить shareable catalog context.
- [x] 4.2 Сделать profile selection keyboard-first и discoverable без row-click-only поведения.
- [x] 4.3 Пересобрать detail pane как operator summary: что это за профиль, где используется, что можно сделать дальше; opaque pins и raw JSON оставить вторичным слоем.
- [x] 4.4 Оставить usage loading explicit, но встроить его в более понятный next-step flow и copy.

## 5. Проверки и выпуск
- [x] 5.1 Добавить/обновить route-level tests на URL-state restore, semantic selection, persistent labels и progressive disclosure.
- [x] 5.2 Добавить/обновить browser smoke на `/decisions` и `/pools/binding-profiles`, подтверждающий deep-link, keyboard selection и отсутствие placeholder-only critical controls.
- [x] 5.3 Прогнать `openspec validate improve-decisions-binding-profiles-usability --strict --no-interactive` и релевантные frontend checks после реализации.
