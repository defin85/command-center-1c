# Design: Frontend performance (bundle/code-splitting, re-render, data fetching)

## Цели
1) Снизить стоимость initial загрузки за счёт корректного code‑splitting.
2) Устранить лишние ререндеры корня приложения, вызванные WS‑метриками.
3) Уменьшить waterfall‑задержки при проверках доступа и загрузке UI‑модулей (без ломки поведения).

## Ключевой инвариант (Re-render)
Получение `metrics_update` по service mesh WebSocket **НЕ ДОЛЖНО** вызывать ререндер `App`/верхнего дерева роутера.

### Текущее поведение (as-is)
- `useRealtimeInvalidation` вызывается в `App` и читает `lastInvalidation` через `useServiceMesh()`:
  - `frontend/src/hooks/useRealtimeInvalidation.ts:18-49`
  - `frontend/src/hooks/useServiceMesh.ts:26-70`
- `useServiceMesh()` подписывается на `serviceMeshManager.subscribe(setState)` и тем самым доставляет `metrics_update` в React state:
  - `frontend/src/stores/serviceMeshManager.ts:323-349`

Итог: каждое обновление метрик может триггерить ререндер `App`, хотя `App` не отображает метрики.

### Предлагаемое решение
Сделать invalidation “вне React state”:
- В `serviceMeshManager` добавить отдельные listeners для `dashboard_invalidate` (event channel).
- `useRealtimeInvalidation` в `useEffect` подписывается на этот канал и вызывает `queryClient.invalidateQueries(...)` напрямую.
- Метрики (`metrics_update`) продолжают обновлять `ServiceMeshState` для UI‑страниц, но `App` больше не зависит от этого state.

Компромиссы:
- Нужно аккуратно отписываться, чтобы не получить утечки (особенно при смене токена/разлогине).

## Инвариант (Bundle/code-splitting)
Shared/initial graph не должен “засасывать” код lazy‑страниц из-за реэкспортов/баррелей.

### Текущее поведение (as-is)
`frontend/src/api/queries/index.ts` реэкспортит множество хуков. Импорт `queryKeys`/хуков из этого файла в рантайм‑модулях (hooks/stores/layout) делает barrel частью initial graph и ухудшает code‑splitting.

### Предлагаемое решение
- Для рантайм‑кода: запретить использование `frontend/src/api/queries/index.ts` как точки импорта.
- Использовать прямые импорты (например `../api/queries/queryKeys`, `../api/queries/me`, `../api/queries/rbac/...`).
- Оставить `index.ts` только как “DX convenience” для тестов/локального использования, либо постепенно сузить его область применения.

## Data fetching / waterfalls
Цель — минимизировать искусственные последовательности вида:
“проверка доступа → только потом загрузка модуля страницы → только потом загрузка данных”.

Подход:
- Начинать (где безопасно) загрузку UI‑модуля параллельно проверкам доступа.
- Максимально переиспользовать кэш React Query для проверок прав и `me`, не делая лишних запросов при навигации.

### Изменение семантики обновления данных (СОГЛАСОВАНО)
Для RBAC/справочников (редко меняющиеся данные) допускается снижение “реактивности” ради производительности:
- отключение `refetchOnWindowFocus` для соответствующих query;
- увеличение `staleTime`;
- определение окна консистентности (например обновление по ручному refresh / перезагрузке страницы / редкому `refetchInterval`).

Это снижает фоновые запросы и каскадные ререндеры при частом фокусировании окна, сохраняя предсказуемое обновление.

Принятое решение для этого change:
- `refetchOnWindowFocus: false` для `me`, RBAC и RBAC refs;
- `staleTime: 5 минут`;
- окно консистентности: обновление по перезагрузке страницы/явному refresh (плюс invalidation события для dashboard/операций, если приходят).

## Инструменты измерения
Чтобы изменения были воспроизводимыми и проверяемыми:
- добавить команду анализа бандла (отчёт по составу/размерам);
- фиксировать baseline/after в рамках change.
