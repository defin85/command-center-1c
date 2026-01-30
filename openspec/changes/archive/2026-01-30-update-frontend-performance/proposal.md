# Change: Оптимизация производительности фронтенда (bundle/code-splitting, re-render, data fetching)

## Why
Фронтенд — критичный UX‑контур для мониторинга/оркестрации. Сейчас есть несколько “дорогих” паттернов, которые:
- увеличивают initial JS и ухудшают code‑splitting (особенно для публичных маршрутов вроде `/login`);
- провоцируют лишние ререндеры на уровне корня приложения при входящих WebSocket‑метриках;
- создают лишние waterfall‑задержки при проверках доступа и загрузке модулей.

Наблюдения по текущему состоянию (as-is):
- `frontend/src/hooks/useRealtimeInvalidation.ts:18-49` получает `lastInvalidation` через `useServiceMesh()`, а `useServiceMesh()` подписывается на **всё** состояние service mesh (`frontend/src/hooks/useServiceMesh.ts:26-70`). Это означает, что любые `metrics_update` по WS (`frontend/src/stores/serviceMeshManager.ts:323-349`) триггерят `setState` и **перерендер компонента `App`**, т.к. хук вызывается в `App.tsx`.
- `useRealtimeInvalidation` и `databaseStreamManager` импортируют `queryKeys` из barrel `frontend/src/api/queries/index.ts` (см. `frontend/src/hooks/useRealtimeInvalidation.ts:19`). Такой импорт в “рантайм‑коде” (который попадает в initial chunk) ломает преимущества code‑splitting: Rollup/Vite вынуждены подтягивать граф реэкспортов и часть модулей, которые логически относятся к lazy‑страницам.
- Базовые размеры сборки на текущей конфигурации `cd frontend && npm run build`:
  - крупные shared‑чанки: `antd-core` ~483 kB (gzip ~131 kB), `vendor` ~448 kB (gzip ~150 kB), `rc` ~442 kB (gzip ~148 kB), `charts` ~305 kB (gzip ~87 kB).
  - присутствуют тяжёлые “feature” ассеты (например monaco workers ~252/384 kB), которые должны быть строго on‑demand.

## What Changes
Приоритеты изменений (по Vercel React Best Practices):

1) **Re-render (CRITICAL)**
- Убрать подписку `App` на полное состояние service mesh ради одного поля `lastInvalidation`.
- Перевести invalidation на event‑driven подписку (listener) без хранения “лишнего” состояния в React дереве.

2) **Bundle / code-splitting (CRITICAL)**
- Убрать “barrel imports” (`frontend/src/api/queries/index.ts`) из модулей, которые участвуют в initial graph (hooks/stores/layout/root).
- Зафиксировать правило: в рантайм‑коде использовать прямые импорты из конкретных модулей (`../api/queries/queryKeys`, `../api/queries/me`, и т.п.), чтобы lazy‑страницы не “утекали” в общий chunk.

3) **Data fetching / waterfalls (MEDIUM-HIGH)**
- Где возможно, запускать проверки доступа и загрузку UI‑модулей параллельно (не блокировать lazy‑импорт страниц на проверках, если данные уже доступны в кэше).
- Уточнить и “успокоить” refetch‑политику для редко меняющихся справочников/прав (СОГЛАСОВАНО: можно менять семантику обновления данных ради снижения фоновых запросов/ререндеров).

### Приоритет UX
Основной приоритет оптимизации — **первый авторизованный заход на `/` (dashboard)**, т.к. это основной рабочий экран и самый частый “cold path” после логина/обновления.
При этом изменения по code‑splitting и barrel imports также улучшают и `/login` (в частности, уменьшая риск подтягивания лишних модулей в initial graph).

4) **Инструменты измерения (MEDIUM)**
- Добавить воспроизводимый способ анализировать состав и размер бандла (команда/отчёт) для регресс‑контроля.

## Non-Goals
- Не меняем API/контракты и доменную логику.
- Не переписываем архитектуру роутинга целиком (допустимы локальные правки для устранения waterfall’ов).
- Не вводим новый state‑manager вместо текущих managers/React Query.

## Impact
- Затронуты: `frontend/src/hooks/*`, `frontend/src/stores/*`, импорты `frontend/src/api/queries/*`, возможно `frontend/vite.config.ts` (только для измерений/анализатора).
- Основной риск — регресс в live‑invalidation (нужно покрыть тестом/проверкой).
