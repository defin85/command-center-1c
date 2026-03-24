# Change: add-decision-revision-clone-flow

## Почему
- Сейчас `/decisions` различает только два основных сценария повторного использования существующей revision: `revise` и guided `rollover`. Оба сценария создают новую revision того же `decision_table_id`.
- Аналитику нужен отдельный сценарий: взять готовую revision как seed, но опубликовать независимую копию с новым `decision_table_id`, чтобы дальше развивать её как отдельный decision resource, а не как ветку существующего lineage.
- Формально backend уже умеет создать новый independent resource через обычный create payload без `parent_version_id`, но в UI нет явного action и продуктового контракта, который отделяет `clone` от `rollover`.

## Что меняется
- `/decisions` получает явный lifecycle action `Clone selected revision` рядом с existing revise/rollover flows.
- Clone flow использует выбранную revision только как editable seed: builder/raw JSON, name и description предзаполняются из source revision.
- Clone flow НЕ передаёт `parent_version_id`, требует новый уникальный `decision_table_id` и публикует independent decision resource через existing create/publish path.
- Clone flow использует выбранную target database и её resolved metadata context так же, как обычный create flow; source revision не обходит target metadata validation.
- UI явно объясняет, что clone создаёт отдельный resource без auto-rebind существующих workflow/binding consumers.
- Existing rollover semantics и активный change `add-decision-revision-transfer-workbench` не переопределяются: rollover остаётся сценарием новой revision того же ресурса, transfer workbench остаётся metadata-aware переносом между context'ами поверх rollover baseline.

## Impact
- Affected specs:
  - `workflow-decision-modeling`
  - `pool-document-policy`
- Affected code:
  - `frontend/src/pages/Decisions/**`
  - `frontend/src/pages/Decisions/__tests__/**`
  - при необходимости analyst-facing copy/docs для `/decisions`

## Не входит в change
- Новый backend endpoint или отдельный persistent clone artifact.
- Автоматическая перепривязка существующих bindings/workflows на cloned decision.
- Изменение guided rollover/transfer semantics.
