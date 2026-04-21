# UI validation runtime evidence

Этот каталог является checked-in artifact path для frontend UI validation runtime evidence.

Что хранить здесь:
- repeated measurement JSON bundles из `cd frontend && npm run measure:ui-validation -- --artifact ../docs/observability/artifacts/ui-validation-runtime/<run-id>.json`;
- repository acceptance summaries для change, который меняет runtime topology или заявляет perf improvement/regression.

Что не считать достаточным evidence:
- один произвольный noisy full run без repeated samples;
- устные claims без отдельной фиксации `vitest` и browser surfaces;
- focused shard rerun без полного browser gate.

Pre-refactor baseline context for `refactor-frontend-validation-runtime-baselines`:
- `cd frontend && npm run test:run` observed `738.50s total`, `470.22s tests`, `359.39s import`
- last stable repo baseline for the same Vitest gate: `337.31s total`, `218.49s tests`
- `cd frontend && npm run test:browser:ui-platform` observed `100 passed` with `461.49s` wall-clock while the full browser contract still lived in one file: `frontend/tests/browser/ui-platform-contract.spec.ts`
- pre-refactor browser monolith size: `6414` lines in `frontend/tests/browser/ui-platform-contract.spec.ts`

Current hotspot context:
- Vitest tail is dominated by the heavy route inventory in `frontend/src/test/runtimePerimeters.ts`, especially `PoolFactualPage`, `PoolRunsPage.*`, `PoolMasterDataPage.*`, `PoolCatalogPage.*`, `PoolTopologyTemplatesPage`, and `DecisionsPage`.
- Browser hotspot before this refactor was the single-file Playwright monolith above; after the split the canonical browser inventory lives in `frontend/src/test/uiPlatformBrowserRuntimePerimeters.js`.

Measurement protocol:
1. Run from `frontend/` on a warm dependency tree and without other heavy CPU-bound workloads on the same machine.
2. Use the repo-owned script and keep the default `3` samples unless the review explicitly documents why fewer samples are acceptable.
3. Capture separate repeated summaries for `npm run test:run` and `npm run test:browser:ui-platform`.
4. If one full run diverges materially from recent baseline, rerun repeated measurement or attach a diagnostic explanation instead of treating the single run as authoritative.

Recommended naming:
- `<change-id>-YYYY-MM-DD.json` for change-scoped acceptance evidence
- `manual-investigation-YYYY-MM-DD.json` for non-landing diagnostic captures
