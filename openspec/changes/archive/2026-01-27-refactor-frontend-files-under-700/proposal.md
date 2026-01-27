# Change: Рефакторинг frontend исходников до целевого размера (700 строк)

## Why
В frontend есть несколько очень крупных файлов (1000–6000+ строк), что делает правки и навигацию сложными, а также ухудшает работу LLM/агентов с контекстом.

## What Changes
Рефакторим frontend (включая тесты) так, чтобы каждый файл TypeScript/TSX:
- был декомпозирован по модулям (компоненты/хуки/утилиты/секции страниц);
- не превышал ~700 строк (цель);
- не менял поведение UI и контракты API.

Актуальные крупнейшие файлы (примерный срез):
- `frontend/src/pages/RBAC/RBACPage.tsx` (~6100)
- `frontend/src/pages/CommandSchemas/CommandSchemasPage.tsx` (~2340)
- `frontend/src/components/driverCommands/DriverCommandBuilder.tsx` (~2280)
- `frontend/src/pages/Settings/ActionCatalogPage.tsx` (~1668)
- `frontend/src/pages/Artifacts/ArtifactsPage.tsx` (~1668)
- `frontend/src/pages/Databases/Databases.tsx` (~1090)
- `frontend/src/api/queries/rbac.ts` (~1000)
- `frontend/src/components/table/TablePreferencesModal.tsx` (~964)

## Non-Goals
- Не меняем поведение UI/эндпоинтов, не делаем новых фич.
- Не трогаем сгенерированный код (`frontend/src/api/generated/**`).
- Не вводим жёсткий CI gate (это отдельный change при необходимости).

## Impact
- Существенные внутренние перестановки файлов/директорий внутри frontend.
- Потребуются обновления импортов и точечные правки тестов.

