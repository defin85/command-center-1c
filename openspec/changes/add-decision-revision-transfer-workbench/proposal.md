# Change: add-decision-revision-transfer-workbench

## Почему
- Guided rollover для `decision_revision` уже существует и уже закрывает базовый lifecycle: source revision -> target database -> publish новой concrete revision с `parent_version_id`. Для аналитика это всё ещё выглядит как низкоуровневый revise flow, а не как удобный перенос готового "схематоза" между разными metadata context.
- Аналитику нужен явный authoring-сценарий: взять рабочую concrete revision, выбрать target database, увидеть что перенеслось автоматически, исправить только проблемные места и выпустить новую concrete revision.
- Введение abstract `Decision revision` ради этого сценария избыточно: текущий runtime/binding contract уже опирается на concrete pinned revisions, deterministic materialization и auditable provenance.

## Что меняется
- Change расширяет уже доставленный guided rollover в `/decisions` до explicit transfer workbench, а не вводит parallel authoring flow с нуля.
- Existing source revision + target database rollover flow становится baseline transport для transfer semantics; поверх него система добавляет явный transfer report, guided remap и source-only transfer mode.
- Архитектурно transfer flow фиксируется как stateless two-phase contract: server-evaluated `transfer preview`, за которым следует `transfer publish` или эквивалентный publish step поверх существующего revision publish path.
- Transfer report различает `matched`, `ambiguous`, `missing` и `incompatible` mapping/result items; publish новой revision остаётся fail-closed, пока аналитик не разрешит все неготовые к переносу элементы.
- Для auto-remap система использует stable design-time metadata identifiers из `ConfigDumpInfo.xml`/`ibcmd`-enriched snapshot как primary signal там, где они доступны; при их отсутствии применяется canonical metadata path/name + type/shape fallback с консервативной классификацией uncertain matches.
- Результат transfer flow всегда остаётся новой concrete revision с `parent_version_id = source revision`, target metadata provenance и без автоматической перепривязки существующих workflow/binding consumers.
- Default selection surfaces для workflow/binding продолжают показывать только ready-to-pin concrete revisions; abstract revisions/blueprints в этот change не входят.

## Impact
- Affected specs:
  - `workflow-decision-modeling`
  - `pool-document-policy`
- Related delivered baseline:
  - archived `add-decision-revision-rollover-ui` already shipped the initial guided rollover flow; этот change строится поверх него и не должен переописывать уже доставленный create/revise/rollover baseline.
- Affected code:
  - `frontend/src/pages/Decisions/**`
  - `frontend/src/api/**`
  - `contracts/orchestrator/**`
  - `orchestrator/apps/api_v2/**`
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/templates/workflow/**`
  - тесты decision authoring/read-model surface
