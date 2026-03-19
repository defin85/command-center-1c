## 1. Contract updates
- [ ] 1.1 Уточнить `pool-binding-profiles` для summary-first default detail path, advanced-only immutable pins и mobile-safe inspect flow.
- [ ] 1.2 Уточнить `ui-web-interface-guidelines` для accessible-name parity, sequential heading hierarchy и WCAG AA contrast на shared shell/platform-governed surfaces.

## 2. Shared primitives and shell hardening
- [ ] 2.1 Исправить shared shell/status/theme defects, которые воспроизводятся на `/pools/binding-profiles`: contrast для relevant shell/status states и visible-label/accessibility-name mismatch у stream status control. (после 1.2)
- [ ] 2.2 Доработать platform primitives только там, где это нужно для narrow-viewport usability на `/pools/binding-profiles` без clipping primary actions и с контролируемым secondary overflow. (после 1.1; можно параллельно с 2.1)

## 3. Binding profiles page remediation
- [ ] 3.1 Перевести default detail path на summary-first hierarchy и убрать opaque immutable pins из primary revision-history presentation, оставив их в explicit advanced disclosure. (после 1.1)
- [ ] 3.2 Исправить narrow-viewport inspect/revise/deactivate flow: primary actions не клипуются, selection control остаётся semantic и touch-safe, detail drawer остаётся operable без скрытого primary horizontal scroll. (после 2.2)
- [ ] 3.3 Исправить heading hierarchy и убрать audit-detected page-level accessibility defects на `/pools/binding-profiles`. (после 1.2)

## 4. Validation
- [ ] 4.1 Добавить/обновить unit and browser tests для `/pools/binding-profiles`: no clipping in mobile detail path, advanced-only technical pins, heading/a11y contracts, route-state сохранение detail drawer.
- [ ] 4.2 Прогнать `npm --prefix frontend run lint`, `npm --prefix frontend run test:run`, `npm --prefix frontend run test:browser:ui-platform`, `npm --prefix frontend run build`.
- [ ] 4.3 Прогнать `openspec validate harden-binding-profiles-ui-audit --strict --no-interactive`.
