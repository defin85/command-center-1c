# Change: add-decision-revision-transfer-workbench

## Почему
- Guided rollover для `decision_revision` уже существует, но он описывает только publish новой concrete revision из source revision под target database. Для аналитика это всё ещё выглядит как низкоуровневый revise flow, а не как удобный перенос готового "схематоза" между разными metadata context.
- Аналитику нужен явный authoring-сценарий: взять рабочую concrete revision, выбрать target database, увидеть что перенеслось автоматически, исправить только проблемные места и выпустить новую concrete revision.
- Введение abstract `Decision revision` ради этого сценария избыточно: текущий runtime/binding contract уже опирается на concrete pinned revisions, deterministic materialization и auditable provenance.

## Что меняется
- `/decisions` получает first-class `transfer workbench` для concrete `decision_revision`.
- Transfer flow стартует от существующей source revision и target database; система резолвит target `configuration profile` и `metadata snapshot`, строит явный transfer report и открывает draft новой revision на основе source revision.
- Transfer report различает `matched`, `ambiguous`, `missing` и `incompatible` mapping/result items; publish новой revision остаётся fail-closed, пока аналитик не разрешит все неготовые к переносу элементы.
- Результат transfer flow всегда остаётся новой concrete revision с `parent_version_id = source revision`, target metadata provenance и без автоматической перепривязки существующих workflow/binding consumers.
- Default selection surfaces для workflow/binding продолжают показывать только ready-to-pin concrete revisions; abstract revisions/blueprints в этот change не входят.

## Impact
- Affected specs:
  - `workflow-decision-modeling`
  - `pool-document-policy`
- Affected code:
  - `frontend/src/pages/Decisions/**`
  - `frontend/src/api/**`
  - `contracts/orchestrator/**`
  - `orchestrator/apps/api_v2/**`
  - `orchestrator/apps/templates/workflow/**`
  - тесты decision authoring/read-model surface
