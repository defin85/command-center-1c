## 1. Contract

- [ ] 1.1 Добавить новый capability `ui-internationalization-foundation` с требованиями по locale resolution, shell bootstrap, catalogs, formatting и code-first API errors.
- [ ] 1.2 Доработать `ui-realtime-query-runtime`, чтобы shell bootstrap contract включал `i18n` summary и не требовал отдельного locale-probe path. (после 1.1)
- [ ] 1.3 Доработать `ui-platform-foundation`, чтобы platform layer владел locale provider, vendor locale bridge и shared formatters. (после 1.1)
- [ ] 1.4 Доработать `ui-frontend-governance`, чтобы governed surfaces не могли обходить canonical i18n layer через raw `toLocale*`, route-local locale packs или route-local provider wiring. (после 1.1)

## 2. Frontend foundation

- [ ] 2.1 Внедрить `frontend/src/i18n/**`: shared runtime, namespace catalogs, local-first locale store, typed keys и formatters. (после 1.1, 1.3)
- [ ] 2.2 Подключить `App.tsx`, `MainLayout`, platform primitives и `apiClient` к effective locale и `X-CC1C-Locale`. (после 2.1)
- [ ] 2.3 Перевести shell/common/errors/platform namespaces и pilot surfaces первой волны на canonical i18n layer. (после 2.2)

## 3. Backend and contracts

- [ ] 3.1 Добавить request-scoped locale resolution в gateway/orchestrator и отразить `i18n` summary в `/api/v2/system/bootstrap/`. (после 1.2)
- [ ] 3.2 Подключить Django translation context для admin/server-rendered templates без смены public SPA error contract на string-only payloads. (после 3.1)
- [ ] 3.3 Обновить OpenAPI и generated clients для bootstrap i18n fields и locale header, если они становятся частью публичного API. (после 3.1)

## 4. Verification

- [ ] 4.1 Добавить frontend unit coverage на locale resolution, persistence, namespace fallback, formatter helpers и problem-code localization. (после 2.2)
- [ ] 4.2 Добавить browser coverage на language switch + reload и на согласованность shell/vendor locale хотя бы для одного governed route. (после 2.3)
- [ ] 4.3 Добавить backend/contract coverage на `X-CC1C-Locale` precedence, bootstrap `i18n` summary и fallback to default locale. (после 3.1)
- [ ] 4.4 Прогнать `openspec validate add-cross-stack-internationalization-foundation --strict --no-interactive`.
