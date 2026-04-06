## 1. Operator workspace completeness

- [x] 1.1 Довести factual workspace так, чтобы batch settlement и edge drill-down показывали `incoming_amount`, `outgoing_amount` и `open_balance` как operator-facing поля, а не только часть этих данных. 
- [x] 1.2 Показать carry-forward linkage в operator surface для batch/status `carried_forward`, включая target quarter и source/target factual context без необходимости смотреть raw JSON. (после 1.1)
- [x] 1.3 Добавить operator-facing refresh/retry control для factual sync в контексте текущего `pool + quarter`, чтобы пользователь не зависел от implicit GET refresh или debug/internal endpoint'ов. (после 1.1; можно параллельно с 1.2)
- [x] 1.4 Обновить frontend/API acceptance tests на factual workspace, чтобы доказать видимость closed amount, carry-forward context и shipped refresh path. (после 1.1, 1.2 и 1.3)

## 2. Rollout cadence activation

- [x] 2.1 Ввести canonical activity classifier для factual sync, который различает `active`, `warm` и `cold` contexts на общем orchestrator path вместо contract-only tiers. 
- [x] 2.2 Провести этот classifier через workspace-triggered sync, operator-triggered refresh, scheduler-managed sync и workflow contract так, чтобы `warm` cadence реально использовался для подходящих non-active open contexts без регрессии `active=120s` и nightly closed-quarter reconcile. (после 2.1)
- [x] 2.3 Обновить runtime/worker tests и observability-facing assertions, чтобы выбор `warm` tier был доказан автоматизированно. (после 2.2)

## 3. Verification

- [x] 3.1 Прогнать релевантные backend tests для factual workspace, scheduling, carry-forward и workflow contract.
- [x] 3.2 Прогнать релевантные frontend tests для `/pools/factual` и run-to-factual handoff.
- [x] 3.3 Прогнать релевантные worker tests для factual scheduler/contract wiring.
- [x] 3.4 Прогнать `openspec validate update-pool-factual-monitoring-operator-drilldown-and-rollout-tiers --strict --no-interactive`.
