# Data fetching / waterfalls: инвентаризация (access checks vs lazy imports)

## Найденные места
1) `frontend/src/App.tsx`
   - `StaffRoute` (`/users`, `/dlq`, `/settings/*`): ожидание `useMe()` блокирует рендер (и, соответственно, lazy‑импорт) страницы.
   - `RbacRoute` (`/rbac`): ожидание `useCanManageRbac()` блокирует lazy‑импорт страницы.
   - `DriverCatalogsRoute` (`/settings/driver-catalogs`, `/settings/command-schemas`): ожидание `useCanManageDriverCatalogs()` блокирует lazy‑импорт страницы/редирект.

Характерная последовательность (cold path):
`route match` → `access check query` → `lazy import` → `render`.

## Минимальная правка для параллелизации
Запускать загрузку чанка страницы параллельно проверке доступа: при маунте route‑guard вызывать `import()` соответствующего модуля (prefetch/preload), пока идёт запрос прав.

Это:
- не меняет семантику доступа (при отсутствии прав всё равно редирект на `/forbidden`);
- убирает искусственный waterfall “access check → только потом import()”.

Реализация сделана через `preload`‑проп в `StaffRoute`/`RbacRoute`/`DriverCatalogsRoute` + `useEffect`, который вызывает `preload()` при наличии `authToken`.
