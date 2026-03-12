# Change: Добавить guided rollover flow для decision revisions под новый релиз ИБ

## Почему
Сейчас аналитик технически может выпустить новую `decision_revision` под новый metadata context, если вручную покажет несовместимые revision, выберет старую revision, откроет её на редактирование и сохранит с `database_id` выбранной ИБ. Этот путь рабочий, но скрыт в diagnostics UX и не выглядит как штатный сценарий перевыпуска policy под новый релиз ИБ.

При обновлении ИБ команде нужен явный analyst-facing механизм, который позволяет взять существующую revision как источник, выпустить новую revision под выбранную ИБ и сохранить fail-closed validation против нового metadata snapshot без ручного API-клиента и без неявной автоперепривязки consumers.

## Что меняется
- Добавляется явный guided UI flow в `/decisions` для создания новой `decision_revision` из существующей revision под metadata context выбранной ИБ.
- UI явно показывает `source revision`, `target database` и resolved target metadata context до публикации новой revision.
- Несовместимые revision остаются скрыты по умолчанию в matching-snapshot режиме, но могут использоваться как explicit source для rollover flow.
- Публикация новой revision продолжает использовать существующий metadata-aware backend validation path и сохраняет новый metadata context только в новой revision.
- Flow не меняет существующие workflow/binding refs автоматически; результатом остаётся новая pinned revision, которую можно выбрать отдельно.

## Влияние
- Затронутые спецификации:
  - `workflow-decision-modeling`
  - `pool-document-policy`
- Затронутые области кода:
  - `frontend/src/pages/Decisions/**`
  - `frontend/src/components/workflow/**` при необходимости переиспользования decision picker patterns
  - тесты `frontend/src/pages/Decisions/__tests__/**`
- Связанные активные change:
  - `add-config-generation-id-metadata-snapshots` изменяет тот же authoring surface `/decisions`; новый flow должен оставаться совместимым с отдельным отображением provenance markers и не конфликтовать с ними по semantics.
