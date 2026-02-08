## 1. Spec Alignment
- [ ] 1.1 Обновить `operation-definitions-catalog`: зафиксировать server-driven unified list contract для exposures.
- [ ] 1.2 Обновить `operation-templates`: зафиксировать использование нового list contract в `/templates`.

## 2. Backend API (`operation-catalog/exposures`)
- [ ] 2.1 Добавить/зафиксировать `surface=all` для staff в list endpoint.
- [ ] 2.2 Добавить server-side `search`/`filters`/`sort` по unified list полям.
- [ ] 2.3 Добавить include-механизм для definition данных в ответе list endpoint.
- [ ] 2.4 Сохранить backward compatibility текущих query-параметров и shape ответа.
- [ ] 2.5 Сохранить RBAC: non-staff видит только разрешённые `template` exposures; `action_catalog` и `all` остаются staff-only.

## 3. Frontend Data Layer Adoption
- [ ] 3.1 Перевести `/templates` list-запрос на новый server-driven contract без client-side full merge.
- [ ] 3.2 Убрать лишний definitions round-trip в list screen при включённом include-механизме.
- [ ] 3.3 Сохранить текущий URL-state (`surface`, search, filters, sort, pagination) и поведение deep-link.

## 4. Tests
- [ ] 4.1 Добавить/обновить backend тесты для `surface=all`, server filters/sort/search, include definitions, RBAC.
- [ ] 4.2 Обновить frontend/browser тесты unified list под новый data-fetch path.
- [ ] 4.3 Добавить regression тест на backward compatibility старого контракта list endpoint.

## 5. Validation
- [ ] 5.1 `openspec validate update-step-2-operation-catalog-exposures-list-api --strict --no-interactive`
- [ ] 5.2 Прогнать релевантные backend/frontend тесты для `/templates` unified list.
