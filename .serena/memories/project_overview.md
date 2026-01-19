# CommandCenter1C — overview

- Цель: массовое управление 700+ базами 1С.
- Поток: Frontend (5173) → API Gateway (8180, `/api/v2/*`) → Orchestrator (8200) → PostgreSQL; также Redis + Go Worker; интеграции OData/RAS.
- Статус: Phase 2; ориентир — `docs/ROADMAP.md`.
- Лимиты 1С: транзакции <15s; 3–5 соединений/БД; OData batch 100–500; rate limit 100 req/min/user.
- Точки входа: `docs/START_HERE.md`, `openspec/AGENTS.md`.
