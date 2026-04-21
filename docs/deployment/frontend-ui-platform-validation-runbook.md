# Frontend UI-platform validation runbook

## Baseline

- `antd`: `5.29.3`
- `@ant-design/pro-components`: `2.8.10`

## Default delivery path

The canonical frontend delivery command is:

```bash
cd frontend && npm run build
```

`npm run build` is the full UI-platform validation gate. It runs the checks in this order:

1. `generate:api`
2. `lint`
3. `test:run`
4. `test:browser:ui-platform`
5. `build:assets`

## Docker path

`frontend/Dockerfile` must stay on `RUN npm run build`. Do not replace it with `build:assets` or `vite build`, because that would bypass the validation gate.

## Manual validation

Use this order when you need to validate the frontend locally:

```bash
cd frontend
npm run build
docker build -t commandcenter1c-frontend .
```

`npm run build` already executes the full validation gate. Run `npm run validate:ui-platform` only when you need an explicit pre-build check without the final artifact step.

If any step fails, stop and fix the issue before shipping the image or artifact.

## Focused browser reruns

The canonical browser gate stays on:

```bash
cd frontend && npm run test:browser:ui-platform
```

For route- or contract-bounded iteration, use the checked-in shard families instead of ad hoc CLI globs:

```bash
cd frontend && npm run test:browser:ui-platform:workspaces
cd frontend && npm run test:browser:ui-platform:runtime-surfaces
cd frontend && npm run test:browser:ui-platform:governance-settings
cd frontend && npm run test:browser:ui-platform:shell-contracts
```

These focused commands do not replace the blocking landing gate.

## Repeated runtime measurement

Use repo-owned repeated measurement when you need perf evidence for the full UI contour:

```bash
cd frontend && npm run measure:ui-validation -- --artifact ../docs/observability/artifacts/ui-validation-runtime/<run-id>.json
```

Protocol:

1. Run from `frontend/` on a warm dependency tree and without parallel heavy workloads on the same machine.
2. Keep the default `3` samples unless the review explicitly documents a narrower bound.
3. Treat the JSON artifact as authoritative only when it contains separate repeated samples for `npm run test:run` and `npm run test:browser:ui-platform`.
4. If one full run diverges sharply from a recent baseline, rerun repeated measurement or attach a diagnostic explanation instead of treating that single run as a final regression verdict.

Canonical checked-in artifact directory: `docs/observability/artifacts/ui-validation-runtime/`.
