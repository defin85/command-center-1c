## 0. Подготовка
- [ ] 0.1 Зафиксировать список frontend файлов >700 строк (по правилам из `add-file-size-guideline-700`).
- [ ] 0.2 Выбрать стратегию: выносить подмодули рядом (`pages/X/components|hooks|utils`) и/или в общие `components/`.

## 1. Разнос крупных страниц
- [ ] 1.1 `RBACPage`: вынести вкладки/секции (IB users, DBMS users, audit, roles, effective access и т.п.) в отдельные компоненты, вынести колонки таблиц/handlers/формы в подмодули.
- [ ] 1.2 `CommandSchemasPage`: вынести редактор, список, модалки/дифф/валидацию, хелперы сборки запросов в подмодули.
- [ ] 1.3 `ActionCatalogPage`: вынести таблицы/формы/модалки/вью-модели в подмодули.
- [ ] 1.4 `ArtifactsPage`: вынести таблицу, панели, диалоги purge/restore, запросы/хуки в подмодули.
- [ ] 1.5 `Databases.tsx`: вынести крупные подкомпоненты (таблицы/дроверы/фильтры/панели) в подмодули.

## 2. Разнос крупных компонентов и API слоя
- [ ] 2.1 `DriverCommandBuilder`: выделить секции (auth/connection/options/preview/validation) в отдельные компоненты и хуки.
- [ ] 2.2 `rbac.ts` (queries): разнести по доменам (`permissions`, `roles`, `refs`, `audit`), оставив совместимый re-export.
- [ ] 2.3 `TablePreferencesModal`: выделить подкомпоненты и утилиты (state/serialization/render sections).

## 3. Тесты
- [ ] 3.1 Актуализировать unit tests (vitest) после перемещения модулей.
- [ ] 3.2 Актуализировать Playwright e2e (если затронуты селекторы/тестовые id).
- [ ] 3.3 При необходимости разнести слишком большие тестовые файлы на несколько `*.test.tsx`/`*.spec.ts`.

## 4. Валидация
- [ ] 4.1 `npm -C frontend run lint`
- [ ] 4.2 `npm -C frontend run test:run`
- [ ] 4.3 `npm -C frontend run test:browser` (smoke/целевые спеки)
- [ ] 4.4 `npm -C frontend run build`
- [ ] 4.5 `openspec validate refactor-frontend-files-under-700 --strict --no-interactive`

