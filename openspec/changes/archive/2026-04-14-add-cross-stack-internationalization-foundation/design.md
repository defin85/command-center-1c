## Context

`CommandCenter1C` уже ведёт себя как bilingual-ready продукт, но не как продукт с оформленной i18n архитектурой.

Прямые признаки:
- shell и route surfaces содержат mix русского и английского copy;
- platform root (`frontend/src/App.tsx`) уже централизует `antd` `ConfigProvider`, но управляет только `theme`, не `locale`;
- shell bootstrap (`/api/v2/system/bootstrap/`) уже является canonical read-model для identity/tenant/access/capabilities, но не для locale;
- API v2 уже в основном возвращает стабильные `code`/`error_code`, а frontend местами локализует их сам (`PoolRunsRouteCanvas`);
- в `frontend/src` накоплены десятки raw `toLocale*` вызовов и жёстких locale-тегов, из-за чего форматирование не управляется одним источником истины;
- backend уже включает Django i18n baseline (`USE_I18N = True`) и даже использует `{% load i18n %}` в admin templates, но request-scoped locale contract для SPA и admin не оформлен.

Отсюда основной вывод: задача не в том, чтобы “добавить библиотеку переводов”, а в том, чтобы:
1. назначить одного owner-а для effective locale;
2. разделить перевод UI copy, locale-aware formatting и domain/business data;
3. не сломать существующий code-first API error contract;
4. сохранить platform governance и staged rollout.

## Goals

- Ввести один canonical locale context для SPA shell, platform primitives и synchronous backend text surfaces.
- Сделать operator-facing copy переводимым через единый frontend runtime и namespace catalogs.
- Централизовать formatting для даты, времени, чисел, списков и relative time.
- Сохранить machine-readable API errors как основной контракт для SPA.
- Подготовить staged migration с governance guards, а не массовую ручную замену строк без правил.

## Non-Goals

- Не переводить 1C/business payload values и не “локализовывать данные”, которые должны оставаться доменными значениями.
- Не менять execution semantics worker/job flows из-за языка интерфейса.
- Не внедрять server-backed roaming preferences в первой волне.
- Не переводить все existing surfaces одной поставкой.
- Не делать backend свободным источником UX copy для SPA через translated `detail`.

## Locked Decisions

### 1. Operator-facing UI copy локализуется во frontend, а не через translated API payload как primary path

Причина:
- frontend уже владеет page composition и user-visible interaction semantics;
- API уже кодоцентричен (`code`, `error_code`);
- локализованный free-text `detail` плохо совместим с test stability и contract-first API.

Следствие:
- known API problem codes маппятся во frontend на локализованный UX copy;
- raw `detail` остаётся diagnostic fallback для unmapped/advanced cases.

### 2. Shell bootstrap остаётся canonical owner глобального locale context

Новый locale probe endpoint не нужен. Если shell уже инициализирует identity, tenant и capabilities, язык должен жить в том же read-model.

Следствие:
- `/api/v2/system/bootstrap/` должен вернуть `i18n` summary;
- `App`, `MainLayout`, `AuthzProvider` и platform layer читают язык из того же shell context.

### 3. Явный SPA locale override должен идти отдельным app header, а не скрытой зависимостью от browser `Accept-Language`

Для first visit браузерный `Accept-Language` полезен, но он не подходит как единственный источник истины после ручного переключения языка пользователем.

Следствие:
- canonical explicit override: `X-CC1C-Locale`;
- backend resolution order: explicit app override -> supported browser signal -> deployment default;
- later server-backed sync возможен отдельным change, но текущий контракт уже будет готов к нему.

### 4. Первичная поставка остаётся local-first для persistence пользовательского выбора

В репозитории уже есть established pattern local-first preferences (`auth_token`, `active_tenant_id`, table preferences, responsive direction, workspace presentation preferences in active OpenSpec change).

Следствие:
- язык можно безопасно сохранять local-first в первой волне;
- bootstrap отражает resolved locale, но не требует отдельной БД-модели на старте.

### 5. Platform governance обязана ловить locale bypass так же, как она уже ловит layout bypass

Без этого change быстро деградирует в `toLocaleString()` и route-local vendor locale imports.

Следствие:
- `ui-frontend-governance` должен получить lintable boundary для raw locale formatting и route-local locale wiring.

## External References

- i18next docs: fallback, namespace loading, selector-based TypeScript keys, built-in Intl formatting
  - https://www.i18next.com/principles/fallback
  - https://www.i18next.com/overview/typescript
  - https://www.i18next.com/translation-function/formatting
  - https://react.i18next.com/latest/usetranslation-hook
- Ant Design i18n: `ConfigProvider locale={...}` as global vendor locale owner
  - https://ant.design/docs/react/i18n/
- Django translation flow: `LocaleMiddleware`, `Accept-Language`, supported `LANGUAGES`
  - https://docs.djangoproject.com/en/5.2/topics/i18n/translation/
- ECMAScript Intl baseline for locale-aware formatting
  - https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat/DateTimeFormat
- Alternative stack for comparison: FormatJS / React Intl
  - https://formatjs.github.io/docs/react-intl/
  - https://formatjs.github.io/docs/tooling/babel-plugin/

## Audit Verdict

Proceed, but only with a staged, frontend-first design:
- use one shared frontend i18n runtime;
- keep API errors code-first;
- expose locale in shell bootstrap;
- centralize formatting and AntD locale mapping;
- explicitly exclude worker-generated business outputs from first wave.

Не рекомендовано:
- переводить SPA через backend `detail` strings;
- внедрять locale state route-by-route без shell context;
- оставлять raw `toLocale*` и route-local `ConfigProvider locale`.

## Audit Matrix

| Area | Current Evidence | Risk | Decision |
|---|---|---|---|
| Shell locale ownership | `/api/v2/system/bootstrap/` не содержит locale context | High | расширить bootstrap `i18n` summary |
| Vendor locale | `App.tsx` использует `ConfigProvider`, но без `locale` | High | platform layer управляет `antd` locale centrally |
| User-facing formatting | `55` raw `toLocale*` calls, `10` hardcoded locale tags | High | shared formatter layer + governance rule |
| Error localization | API already returns stable `code`, frontend already maps selected codes | Medium | стандартизовать code-to-copy mapping во frontend |
| Backend i18n readiness | `USE_I18N = True`, templates use `{% load i18n %}`, but request locale contract absent | Medium | request-scoped locale for admin/templates only in first wave |
| Preference persistence | repo already uses local-first preferences heavily | Low | keep locale persistence local-first in phase 1 |
| Async worker outputs | long-running flows and artifacts exist across services | High if in-scope | explicitly out of scope for first rollout |

## Options Considered

### Option A. `i18next` + `react-i18next` + shared Intl formatters

Плюсы:
- хорошо подходит для incremental migration большого React/Vite/TS codebase;
- поддерживает namespaces и lazy loading;
- имеет typed key path с `enableSelector`, причём официально поддерживает large dictionaries через `enableSelector: "optimize"`;
- built-in formatting опирается на `Intl`, поэтому форматирование и copy могут жить в одном runtime;
- легко сделать fallback для dynamic error-code keys.

Минусы:
- extraction workflow менее opinionated, чем у Lingui/FormatJS;
- для governance всё равно придётся отдельно строить lint/test rules.

### Option B. `react-intl` / FormatJS

Плюсы:
- сильная ICU-first модель;
- богатые declarative/imperative APIs;
- официальный Babel/TS transformer для extraction и validation.

Минусы:
- более invasive migration для уже существующего large JSX codebase;
- сильнее завязан на message descriptor discipline и tooling changes в build path;
- менее удобен для очень постепенного route-by-route перехода, если в коде уже много ad hoc string assembly и platform wrappers.

### Option C. Lingui

Плюсы:
- сильное extraction/compile tooling;
- good fit для teams, которые хотят translator-facing workflow довольно рано.

Минусы:
- потребует нового CLI/plugin workflow и macro discipline;
- в текущем repo это даёт больше process surface, чем требуется для первой волны.

## Recommendation

Выбрать Option A:
- `i18next` + `react-i18next` в frontend;
- `enableSelector: "optimize"` для typed keys без деградации IDE/perf на большом словаре;
- namespace-based catalogs (`shell`, `common`, `errors`, `platform`, route/domain namespaces);
- shared formatter layer поверх `Intl.*`;
- central mapping `app locale -> antd locale pack`;
- request-scoped backend locale через `X-CC1C-Locale` + browser fallback;
- Django `LocaleMiddleware` только как server-text enabler, а не как primary UX localization engine для SPA.

## Architecture

### Locale model

Canonical public locale ids:
- `ru`
- `en`

Internal mappings:
- `ru` -> `ru_RU` for `antd`
- `en` -> `en_US` for `antd`

`Intl` formatting работает с BCP 47 tag напрямую (`ru`, `en`, optionally resolved region-specific variants).

### Locale resolution

Frontend effective locale precedence:
1. explicit local-first operator selection;
2. bootstrap `effective_locale` on first authenticated load;
3. browser signal;
4. deployment default.

Backend request-scoped precedence:
1. `X-CC1C-Locale` if present and supported;
2. browser `Accept-Language` if supported;
3. deployment default.

### Shell contract

`/api/v2/system/bootstrap/` adds:

```json
{
  "i18n": {
    "supported_locales": ["ru", "en"],
    "default_locale": "ru",
    "requested_locale": "en",
    "effective_locale": "en"
  }
}
```

`requested_locale` may be omitted/null when there was no explicit override.

### Frontend runtime

Recommended structure:

```text
frontend/src/i18n/
  index.ts
  I18nProvider.tsx
  localeStore.ts
  localeBridge.ts
  formatters.ts
  resources.ts
  locales/
    ru/
      common.json
      shell.json
      errors.json
      platform.json
      ...
    en/
      common.json
      shell.json
      errors.json
      platform.json
      ...
```

Key runtime responsibilities:
- initialize `i18next`;
- lazy-load namespaces by route;
- expose `useAppTranslation(ns?)`;
- expose stable formatters;
- sync current locale to `antd` `ConfigProvider`;
- persist explicit operator override;
- feed current locale into `apiClient`.

### API errors

Frontend should use fallback-capable dynamic keys for codes, e.g.:
- `errors.problem.POOL_WORKFLOW_BINDING_REQUIRED`
- fallback to `errors.problem.unspecific`

This aligns with i18next’s documented support for key fallback and preserves stable contracts.

### Formatting

All user-visible formatting goes through shared helpers:
- `formatDateTime`
- `formatDate`
- `formatTime`
- `formatNumber`
- `formatRelativeTime`
- `formatList`

Route/page code should not call raw `toLocaleString()` as primary rendering path.

### Backend

Backend responsibilities in first wave:
- resolve request locale;
- expose bootstrap i18n summary;
- make locale available to Django translation context for admin/templates/synchronous server text;
- keep problem `code` stable;
- avoid translating business/domain payload values by default.

### Rollout

Phase 1 foundation:
- shell + common + errors + platform namespaces;
- locale switcher in shared shell;
- central formatting layer;
- header propagation and bootstrap contract.

Phase 2 pilot routes:
- `/`
- `/system-status`
- `/clusters`
- `/rbac`

Reason:
- high operator visibility;
- manageable scope;
- already shell-governed and platform-sensitive.

Phase 3 domain-heavy routes:
- `/databases`
- `/operations`
- `/pools/*`
- `/workflows`
- `/templates`

This phase must happen only after formatter and error-code patterns stabilize.

## Exact Wording Fixes

- `ui-realtime-query-runtime` should explicitly include locale summary in shell bootstrap requirement, because current wording only mentions identity/tenant/access/capabilities and leaves locale ownership ambiguous.
- `ui-platform-foundation` should explicitly say that platform layer owns locale provider, vendor locale bridge and shared formatters, otherwise route-local `ConfigProvider locale` remains loophole-permitted.
- `ui-frontend-governance` should explicitly ban raw locale formatting and route-local locale pack wiring on governed surfaces; otherwise the intended i18n boundary remains unenforceable.

## Execution Plan

1. Extend OpenSpec contracts:
   - add `ui-internationalization-foundation`
   - patch `ui-platform-foundation`
   - patch `ui-realtime-query-runtime`
   - patch `ui-frontend-governance`
2. Build frontend i18n runtime and shell locale store.
3. Extend shell bootstrap and request locale propagation.
4. Add governance/lint coverage for raw locale bypass.
5. Migrate shell/common/errors and pilot routes.
6. Add browser/contract regression coverage.
7. Roll forward route families in bounded waves.

## Quality Gates

- OpenSpec strict validation passes.
- Frontend unit tests cover locale resolution, catalogs, formatters and error-code fallback.
- Browser test covers language switch + reload on at least one governed route.
- Contract tests cover bootstrap `i18n` block and locale precedence.
- Governance checks fail on raw `toLocale*` and route-local locale provider bypass for governed surfaces.

## Risks

- Mixed-language UI during migration waves.
  - Mitigation: translate shell/common/errors first; track per-route readiness explicitly.
- Over-localizing backend `detail` and creating contract drift.
  - Mitigation: keep SPA on code-first mapping.
- Tooling drift if translation catalogs grow large.
  - Mitigation: `enableSelector: "optimize"`, route namespaces, lazy loading.
- Hidden async surfaces later demanding locale persistence beyond request scope.
  - Mitigation: keep worker-generated outputs out of scope now and open a dedicated follow-up change if needed.

## Assumptions And Open Questions

- Assumption: first supported locales are `ru` and `en`.
- Assumption: deployment default remains configurable and can be `ru`.
- Open question: should explicit locale picker live only in shell header, or also in a future user settings workspace.
- Open question: whether server-backed roaming locale preference is needed for staff users before async/export surfaces enter scope.
