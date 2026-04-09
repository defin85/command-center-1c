## 1. Capability and vocabulary

- [ ] 1.1 Зафиксировать vocabulary: `workspaceKind` описывает route family, а `presentation mode` описывает только допустимый layout variant внутри совместимого surface.
- [ ] 1.2 Добавить новый capability `ui-workspace-presentation-preferences` с user-visible requirements по supported modes, precedence, persistence и unsupported-route behaviour. (после 1.1)
- [ ] 1.3 Доработать `ui-platform-foundation` и `ui-frontend-governance`, чтобы platform primitives и inventory enforcement поддерживали эту модель без размывания текущих UI boundaries. (после 1.2)

## 2. Rollout contract

- [ ] 2.1 Зафиксировать effective mode precedence: per-route override -> global default -> route default -> responsive fallback. (после 1.2)
- [ ] 2.2 Зафиксировать invariant, что narrow viewport всегда использует mobile-safe detail fallback независимо от desktop preference. (после 2.1)
- [ ] 2.3 Зафиксировать initial eligibility policy и rollout scope: pilot для routes с mature selected-entity/detail contract, явные exclusions для incompatible workspace families. (после 1.3)

## 3. Validation and delivery gates

- [ ] 3.1 Зафиксировать минимальный validation matrix для opted-in routes: unit coverage на mode resolution/persistence и browser coverage на `split`, `drawer` и narrow fallback. (после 2.1 и 2.2)
- [ ] 3.2 Зафиксировать, что governance validation отклоняет routes без explicit inventory declaration allowed/default modes и отклоняет incompatible mode declarations. (после 1.3)
- [ ] 3.3 Прогнать `openspec validate add-ui-workspace-presentation-preferences --strict --no-interactive`.
