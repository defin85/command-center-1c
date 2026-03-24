# Frontend Guidance

- Scope: `frontend/` contains the React/Vite application and platform-owned page composition layer.
- First read:
  - `docs/agent/VERIFY.md`
  - `docs/agent/RUNBOOK.md`
  - `frontend/package.json`
- Entry points:
  - `frontend/src/main.tsx`
  - `frontend/src/components/platform/`
  - `frontend/src/pages/`
- Local constraints:
  - follow the root UI Platform Contract in `AGENTS.md`
  - generated API client lives in `frontend/src/api/generated/**`
  - prefer page composition through platform primitives, not raw page-level `antd` shells
- Canonical validation commands:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run test:run -- <path>`
  - `cd frontend && npm run test:browser:ui-platform`
  - `cd frontend && npm run validate:ui-platform`

