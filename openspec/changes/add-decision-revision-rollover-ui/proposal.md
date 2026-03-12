# Change: Добавить guided rollover flow для decision revisions под новый релиз ИБ

## Почему
Сейчас аналитик технически может выпустить новую `decision_revision` под новый metadata context, если знает внутренний revise flow, вручную выбирает старую revision как seed и сохраняет её с `database_id` выбранной ИБ. Этот путь рабочий, но не выглядит как штатный сценарий перевыпуска policy под новый релиз ИБ.

После перехода на business-identity compatibility same-release revisions должны оставаться видимыми по умолчанию между ИБ одной и той же конфигурации. Но rollover между релизами всё равно нужен как отдельный UX-сценарий: команде нужен явный analyst-facing механизм, который позволяет взять revision предыдущего релиза как источник, выпустить новую revision под выбранную ИБ и сохранить fail-closed validation против нового target metadata snapshot без ручного API-клиента и без неявной автоперепривязки consumers.

## Что меняется
- Добавляется явный guided UI flow в `/decisions` для создания новой `decision_revision` из существующей revision под metadata context выбранной ИБ.
- UI явно показывает `source revision`, `target database` и resolved target metadata context до публикации новой revision.
- Default compatible selection остаётся привязанным к active business-identity contract, но revision вне target compatible set (например, revision предыдущего релиза) могут использоваться как explicit source для rollover flow.
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
  - `update-business-configuration-identity-for-decision-reuse` задаёт новый compatibility contract для `/decisions`; rollover flow должен строиться поверх business-identity matching и не возвращать `metadata_hash`/publication drift в роль primary filter semantics.
