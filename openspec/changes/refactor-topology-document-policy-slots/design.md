## Контекст

Текущая схема уже развела authoring по слоям:
- `/decisions` для `document_policy` revisions;
- `/workflows` для orchestration;
- `pool_workflow_binding` для pinning workflow/decision revisions.

Но runtime все еще опирается на single compiled policy на весь binding/run. Это хорошо видно по текущему preview/runtime path:
- binding decision evaluation выбирает первый `document_policy` output и складывает его в один `compiled_document_policy`;
- document plan compile уже работает per allocation/per target database, но применяет к каждому target один и тот же compiled policy;
- legacy fallback `edge.metadata.document_policy` и `pool.metadata.document_policy` до сих пор остается рабочим путем.

Из-за этого нельзя штатно выразить сценарий:
- одно ребро пула публикуется как `sale` chain;
- другое ребро этого же пула публикуется как `purchase` chain;
- оба сценария живут в одном run и одном binding.

## Цели

- Сохранить `Bindings` как canonical pinning layer.
- Сделать `Topology` источником истины для выбора publication slot на конкретном edge.
- Сохранить `/decisions` как единственный primary authoring surface для concrete `document_policy`.
- Перевести runtime на per-edge resolution policy без возврата к inline policy authoring в topology.
- Убрать shipped legacy `document_policy` authoring/import из `Topology Editor`.

## Не-цели

- Не вводить `abstract decision revision` или новый runnable artifact поверх existing decisions.
- Не переносить per-edge document typing в `Workflows`.
- Не превращать `Bindings` в неявный fallback или временный compatibility layer.
- Не выносить selector из `edge.metadata` в отдельное top-level поле в рамках этого change.

## Решение

### 1. Topology edge хранит только selector, а не full policy

Для MVP publication slot хранится в `edge.metadata.document_policy_key`.

Этот key:
- описывает, какой policy slot применять к конкретному ребру;
- не содержит inline `document_policy`;
- редактируется в `Topology Editor` рядом со structural metadata ребра.

`Topology` отвечает на вопрос "какой slot применять на этом ребре", но не на вопрос "как устроен сам policy".

### 2. Binding decisions становятся именованными publication slots

`pool_workflow_binding.decisions[]` уже хранит `decision_key`. Этот change закрепляет его как canonical slot name для policy-bearing decisions внутри binding.

Требования к binding slot layer:
- `decision_key` уникален в пределах binding;
- binding может pin-ить несколько policy-bearing decisions;
- topology edge selector резолвится только против pinned decisions выбранного binding.

Это означает и UI-сдвиг: binding workspace больше не должен выглядеть как низкоуровневый редактор raw decision refs. Для аналитика binding должен читаться как набор именованных publication slots, покрывающих topology edges.

### 3. Runtime резолвит policy per edge

Во время compile `document_plan_artifact` runtime:
1. берет `edge.metadata.document_policy_key`;
2. ищет matching `decision_key` в selected binding;
3. получает concrete `document_policy` из соответствующего decision output;
4. применяет этот policy только к данному edge allocation / target database.

Fail-closed случаи:
- у ребра нет `document_policy_key`;
- в binding нет matching `decision_key`;
- matching decision не materialize'ит valid `document_policy`;
- в binding есть duplicate `decision_key`.

### 4. Workflows остаются orchestration-only

`Workflow` в этой схеме отвечает за:
- подготовку input;
- distribution;
- approval/reconciliation/master-data gates;
- publication stage orchestration;
- retry/verification flow.

`Workflow` не хранит per-edge/per-organization matrix document types. Один и тот же workflow должен переиспользоваться на пулах с разными topology slots.

### 5. Legacy document policy уходит из shipped Topology surface

После cutover:
- `Topology Editor` не предоставляет inline editor/import для `edge.metadata.document_policy`;
- mutating topology path блокирует новые authoring payload'ы с `edge.metadata.document_policy` и `pool.metadata.document_policy`;
- runtime preview/run path не использует legacy topology policy как fallback source-of-truth.

Legacy становится remediation concern:
- существующую policy надо перевести в decision revision;
- binding должен получить named slot refs;
- topology edge должен получить `document_policy_key`.

### 6. Topology Editor требует отдельного UI-рефакторинга

Этот change не сводится к удалению legacy поля. `Topology Editor` меняет свою analyst-facing роль:
- вместо legacy `document_policy` panel он становится slot-oriented workspace;
- edge editing должен показывать `document_policy_key` как first-class control;
- UI должен уметь объяснить, покрыт ли выбранный edge matching binding slot'ом;
- remediation для legacy topology policy должна быть встроенной и blocking, а не спрятанной в advanced JSON.

Минимальный ожидаемый UX после cutover:
- structural edge editing и slot assignment находятся в одном рабочем потоке;
- inline JSON/policy builder для новых схем отсутствует;
- при наличии selected pool binding UI показывает status `resolved / missing / ambiguous` для slot coverage;
- если topology зависит от legacy `document_policy`, editor показывает remediation screen вместо полурабочего mixed-mode editor.

Это важно явно фиксировать в change, чтобы implementation не деградировал в "backend уже живет по slot model, а frontend все еще выглядит как legacy policy editor с переименованным полем".

### 7. Binding workspace тоже требует UI-рефакторинга

Если topology editor становится slot-oriented, binding workspace тоже должен сменить mental model:
- primary сущность в UI это named publication slot, а не raw `decision_table_id`;
- binding screen должен показывать matrix/summary "slot -> decision revision -> покрытые edges";
- аналитик должен видеть непокрытые topology selectors до запуска run;
- preview должен быть продолжением того же UX, а не отдельным diagnostic JSON surface.

Минимальный ожидаемый UX после cutover:
- bindings screen показывает named slots как first-class rows/cards;
- для каждого slot видно pinned decision revision и статус topology coverage;
- missing или ambiguous coverage видны до preview/create-run;
- ручной ввод raw ids не является primary path даже в advanced mode.

## Альтернативы и почему они отвергнуты

### Перенести точную привязку в Workflows

Отвергнуто, потому что workflow layer отвечает за orchestration, а не за per-edge publication matrix. Иначе workflow definition начнет зависеть от concrete topology layout и organization targets.

### Отказаться от Bindings

Отвергнуто, потому что bindings уже решают pinning, lineage, effective period и explicit run selection. Удаление bindings вернет pinning-семантику либо в topology, либо в workflow, что ухудшит auditability и runtime determinism.

### Оставить inline `document_policy` в Topology как "advanced mode"

Отвергнуто, потому что это сохраняет dual source-of-truth и мешает окончательному cutover на `/decisions`.

### Ограничиться backend cutover без UI-рефакторинга Topology Editor

Отвергнуто, потому что тогда operator surface останется ментально legacy-first и продолжит подталкивать аналитика к поиску document authoring внутри topology вместо slot assignment + `/decisions`.

### Оставить Bindings low-level editor'ом raw decision refs

Отвергнуто, потому что при slot-oriented topology такой UI заставит аналитика мысленно сопоставлять edge selectors и decision refs вручную. Это сохраняет скрытую сложность и повышает риск missing slot уже на этапе run preview.

## Миграция

Перед включением cutover для shipped operator path legacy topology policy должна быть ремедиирована:
1. materialize legacy `document_policy` в decision revision;
2. pin resulting revision в binding с нужным `decision_key`;
3. проставить `edge.metadata.document_policy_key` на каждом ребре;
4. проверить per-edge binding preview parity;
5. только после этого отключать legacy runtime fallback.

Исторические данные могут сохранять legacy payload как provenance, но default shipped authoring/runtime path не должен опираться на него после cutover.

## Предположения

- Для MVP selector остается в `edge.metadata.document_policy_key`; перенос в top-level edge field может быть отдельным future change.
- `pool.metadata.document_policy` выводится из штатного path вместе с `edge.metadata.document_policy`, чтобы не оставлять второй legacy source-of-truth.
