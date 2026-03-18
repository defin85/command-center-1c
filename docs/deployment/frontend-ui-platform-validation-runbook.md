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
