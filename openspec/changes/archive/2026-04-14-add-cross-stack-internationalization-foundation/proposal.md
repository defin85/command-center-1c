# Change: add-cross-stack-internationalization-foundation

## Почему

В текущей ветке интернационализация уже нужна, но архитектурно не оформлена:
- frontend содержит смешанный operator-facing copy на русском и английском, route-level ad hoc `i18n` props и локальные message maps вместо одного канонического слоя;
- в `frontend/src` уже есть не менее `55` прямых вызовов `toLocaleString()/toLocaleDateString()/toLocaleTimeString()` и не менее `10` жёстко прошитых locale-тегов вроде `ru-RU`, что делает форматирование непредсказуемым и плохо тестируемым;
- `App.tsx` использует `antd` `ConfigProvider`, но не управляет `locale`, поэтому vendor-copy, даты и empty states не синхронизированы с будущим языком UI;
- `orchestrator` включает `USE_I18N = True`, но shell bootstrap не отдаёт locale context, а backend не имеет явного request-scoped locale contract для SPA;
- API уже в основном опирается на стабильные machine-readable `code`/`error_code`, а значит локализацию пользовательских ошибок лучше проектировать поверх code-first контракта, а не через ad hoc перевод `detail`.

Без отдельного cross-stack change команда почти неизбежно продолжит внедрять локализацию route-by-route: где-то через `i18n`-props, где-то через raw `toLocale*`, где-то через локализованный backend `detail`. Это создаст inconsistent UX, усложнит тестирование и сломает governance model для platform-owned frontend.

## Что меняется

- Добавить новый capability `ui-internationalization-foundation`.
- Зафиксировать единый locale contract для shell и SPA:
  - initial supported locales: `ru`, `en`;
  - canonical public locale ids: BCP 47 language tags;
  - explicit SPA override через `X-CC1C-Locale`;
  - shell bootstrap как canonical read-model для `supported_locales`, `default_locale`, `effective_locale`.
- Зафиксировать frontend-first i18n layer для operator-facing copy:
  - shared provider/runtime;
  - namespace-based catalogs;
  - lazy loading и fallback;
  - shared formatters для date/time/number/list/relative time.
- Зафиксировать, что operator-facing API errors для SPA остаются code-first:
  - backend сохраняет стабильные machine-readable `code`;
  - frontend отображает локализованный UX copy по `code`;
  - raw `detail` остаётся вторичным diagnostic fallback, а не главным UX контрактом.
- Зафиксировать request-scoped backend locale для Django admin/server-rendered surfaces без скрытого расширения scope на worker-generated business artifacts.
- Доработать связанные specs:
  - `ui-platform-foundation`
  - `ui-realtime-query-runtime`
  - `ui-frontend-governance`

## Impact

- Affected specs:
  - `ui-internationalization-foundation` (new)
  - `ui-platform-foundation`
  - `ui-realtime-query-runtime`
  - `ui-frontend-governance`
- Affected code (expected, when implementing this change):
  - `frontend/src/App.tsx`
  - `frontend/src/main.tsx`
  - `frontend/src/components/platform/**`
  - `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/src/api/client.ts`
  - `frontend/src/api/queries/shellBootstrap.ts`
  - `frontend/src/pages/**`
  - `frontend/src/utils/**`
  - `frontend/src/hooks/**`
  - `frontend/eslint.config.js`
  - `frontend/tests/browser/**`
  - `orchestrator/config/settings/base.py`
  - `orchestrator/apps/api_v2/views/system.py`
  - `orchestrator/apps/api_v2/tests/**`
  - `go-services/api-gateway/internal/middleware/**`
  - `contracts/orchestrator/**`

## Explicitly Out Of Scope

- Перевод бизнес-данных, приходящих из 1C, OData payload-ов и доменных значений, которые являются частью исходных данных, а не UI copy.
- Локализация worker-generated business documents, long-running artifacts, писем и offline-export bundles в первой итерации.
- URL language prefixes, отдельные `/ru/...` и `/en/...` route trees.
- Внедрение server-backed roaming sync пользовательского языка между устройствами в первой итерации.
- Полный одномоментный перевод всех route/page surfaces в один change без staged rollout.

## Assumptions

- Platform-governed operator UI будет внедрять i18n инкрементально, но новые и materially rewritten governed surfaces не должны создавать новый ad hoc copy layer.
- Первый rollout может хранить явный выбор языка local-first в SPA, если request-scoped locale и reload persistence соблюдены.
- `shell bootstrap` остаётся canonical owner глобального shell context и получает i18n summary вместо отдельного locale-probe endpoint.
- Если product owner не утвердит другой default отдельно, change исходит из configurable deployment default с рекомендуемым baseline `ru`.
