## 1. Baseline & Measurement
- [ ] Зафиксировать baseline сборки: `cd frontend && npm run build` (сохранить лог с размерами чанков в change).
- [ ] Добавить режим анализатора бандла (например `npm run analyze`) без влияния на обычную сборку.

## 2. Re-render: убрать перерендер `App` от service mesh метрик
- [ ] Добавить в `serviceMeshManager` отдельный канал подписки для `dashboard_invalidate` (без `setState` полного `ServiceMeshState` для слушателя invalidation).
- [ ] Переписать `useRealtimeInvalidation` так, чтобы он не использовал `useServiceMesh()` и не держал React‑state ради invalidation; invalidation выполнять в effect/listener.
- [ ] Проверить, что `ServiceMeshPage` и остальные потребители `useServiceMesh` продолжают получать метрики как раньше.

## 3. Bundle/code-splitting: убрать “barrel imports” из initial graph
- [ ] Заменить импорты `queryKeys` с `../api/queries` на прямой `../api/queries/queryKeys` в рантайм‑модулях (минимум: `useRealtimeInvalidation`, `databaseStreamManager`).
- [ ] Убрать импорты хуков из `frontend/src/api/queries/index.ts` в shared‑модулях (layout/root/hooks/stores) — перейти на прямые импорты из конкретных файлов.
- [ ] Повторно собрать `cd frontend && npm run build` и сравнить размеры: ожидание — уменьшение initial/shared chunk’ов и отсутствие подтягивания “lazy‑фич” в общий бандл.

## 4. Data fetching / waterfalls (опционально, требует согласования)
- [ ] Инвентаризировать места, где проверки доступа блокируют загрузку страницы/модуля; предложить минимальные правки для параллелизации.
- [ ] Изменить `refetchOnWindowFocus`/`staleTime` для RBAC/справочников, чтобы снизить фоновую сетевую активность и ререндеры (СОГЛАСОВАНО).
- [ ] Определить “окно консистентности” для прав/справочников: обновление либо по явной перезагрузке/ручному refresh, либо по `refetchInterval` (например 5–10 минут), либо по invalidation‑событию (если оно появится).

## 5. Tests & Validation
- [ ] Тест (vitest): при `metrics_update` от service mesh invalidation‑слушатель не вызывает перерендер `App` (минимально: не подписывается на `serviceMeshManager.subscribe`).
- [ ] Тест (vitest): при `dashboard_invalidate` соответствующие `queryClient.invalidateQueries` вызываются с ожидаемыми ключами.
- [ ] Тест (vitest): RBAC/справочники не инициируют `refetch` на window focus при активной сессии (либо проверка опций query).
- [ ] `./scripts/dev/lint.sh`
- [ ] `cd frontend && npm run test:run`
