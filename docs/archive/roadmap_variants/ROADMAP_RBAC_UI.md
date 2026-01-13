# Roadmap: RBAC UI (переключатель "Назначения / Роли")

Статус: 2026-01-10 — v0.1: закрыты основные долги v0 (дерево clusters→databases; effective access с фильтрами и источниками). Закрыт Milestone 1 (декомпозиция `RBACPage.tsx`), выполнен Milestone 4 (пустые состояния/подсказки, унификация loading/error, дока для операторов). Дальше: тесты/регрессии. Undo (optional) реализован.

Цель: заменить текущую модель "отдельная вкладка на каждый тип объекта" на человеко-ориентированный RBAC-интерфейс с единым UX, где:
- "Назначения" отвечает на вопрос **кто где имеет доступ** (users/groups -> clusters/infobases/другие ресурсы).
- "Роли" отвечает на вопрос **что именно означает роль** (capabilities/права).

Ограничения:
- Чистый RBAC (без условий/ABAC).
- Доступ нужен и "полный", и точечный (например, бухгалтеры только на конкретные ИБ).
- Масштаб: 700+ ИБ, поэтому обязательно: поиск, lazy-load, пагинация, аккуратные массовые действия.

Принципы:
- Единые компоненты и один layout вместо копипасты вкладок.
- Любые изменения прав/ролей требуют `reason` и пишутся в admin audit log (как уже принято в API v2).
- По возможности переиспользовать существующие endpoints; новые API добавлять только при реальной необходимости (и тогда фиксировать в `contracts/**`).

---

## Текущая реализация (v0.1)

Режимы: `Назначения / Роли` (страница: `frontend/src/pages/RBAC/RBACPage.tsx`).

- `Назначения`:
  - `Доступ к объектам`: два сценария `Кто -> Где` / `Где -> Кто` для clusters/databases/operation templates/workflow templates/artifacts (grant/revoke + reason, bulk для групп на clusters/databases; clusters/databases выбираются через дерево clusters→databases, кластеры кликабельны).
  - `Роли пользователей`: выдача ролей пользователю (replace/add/remove + reason).
  - `Effective access`: итоговый доступ пользователя по выбранному типу ресурса + фильтр по конкретному ресурсу + раскрытие (expand) “источников” (direct/group/cluster/database/...).
  - `Audit`: просмотр admin audit log.
  - `Infobase Users`: только staff (вне RBAC-редактора, но в той же странице).
- `Роли`: CRUD ролей + редактирование capabilities (reason обязателен).

Поддерживаемый scope (v0.1):
- ресурсы: clusters, databases, operation templates, workflow templates, artifacts;
- principals: user и group;
- bulk: только group+clusters/databases.

---

## Долги v0 (что осталось)

- Страница `RBACPage.tsx` всё ещё крупная: нужно вынести оставшиеся общие компоненты/хуки (`PermissionsTable` с toolbar/bulk, `ReasonModal`, `AuditPanel`, `EffectiveAccessPanel`, ...). Уже вынесены: `RbacPrincipalPicker`, `RbacResourcePicker`, `RbacPermissionsTable` (рендер таблицы), `useConfirmReason`, общий хук для paginated ref Select.
- Полировка: пустые состояния, подсказки “как выдать доступ на конкретную ИБ”, устойчивые loading/error.
- Тесты/регрессии: минимум smoke/e2e на ключевые сценарии RBAC UI.

---

## Термины (для UI)

- **Principal**: пользователь или группа.
- **Role**: роль (набор прав/capabilities).
- **Binding / Assignment**: назначение роли principal'у на конкретный scope/объект.
- **Scope/Resource**: ресурс, на который назначается доступ (кластер, ИБ, шаблон операции/workflow, артефакт и т.д.).
- **Effective access**: итоговые права с учетом всех назначений (и их уровня/наследования, если применимо).

---

## MVP (Definition of Done)

- [x] На `/rbac` есть переключатель режимов: `Назначения` / `Роли`.
- [x] В `Назначения` можно управлять доступом пользователей и групп минимум к кластерам и ИБ:
  - [x] поиск + фильтры + пагинация;
  - [x] lazy-load для больших reference списков (server-side search + pagination в Select; virtualization для таблиц не требуется из-за pagination);
  - [x] grant/revoke + bulk операции (bulk: группы на clusters/databases);
  - [x] обязательный `reason` на изменения;
  - [x] просмотр effective access.
- [x] В `Роли` можно управлять ролями:
  - [x] list/create/update/delete роли;
  - [x] редактирование capabilities/прав роли;
  - [x] обязательный `reason` на изменения;
  - [x] аудит действий (вкладка `Audit` доступна в обоих режимах).
- [x] Существующие "старые" вкладки скрыты через режимы (`Назначения / Роли`).
- [x] Скрытие старых вкладок переведено на feature-flag `VITE_RBAC_LEGACY_TABS` (legacy вкладки выключены по умолчанию).

---

## Definition of Done по производительности (минимум для масштаба 700+ ИБ)

- [x] Reference списки (databases/operation templates/workflow templates/artifacts) поддерживают server-side search + pagination (без загрузки 2000+ options в Select). Clusters загружаются списком (limit=1000) и фильтруются на клиенте.
- [x] Поиск debounced (250-400ms) и не делает запрос на каждый символ.
- [x] Таблицы назначений используют backend pagination (limit/offset), pageSize по умолчанию 50, время ответа <= 1с в типовых условиях.

---

## API (v2): что переиспользуем

План: максимум переиспользования существующих endpoints `api/v2/rbac/*`.

- refs: `rbac/ref-clusters`, `rbac/ref-databases`, `rbac/ref-operation-templates`, `rbac/ref-workflow-templates`, `rbac/ref-artifacts`;
- permissions list/grant/revoke для user/group на нужные resource types;
- roles CRUD + capabilities;
- audit: `rbac/list-admin-audit`;
- effective access: `rbac/get-effective-access` (включая `sources[]` для отображения источников).

Опционально (если фронту нужно унифицировать множество похожих вызовов):
- [ ] добавить общий endpoint вида `rbac/list-resource-permissions?resource_type=...` и аналогичные grant/revoke,
- [ ] при этом обновить контракты в `contracts/**` и оставить старые endpoints на период миграции.

---

## План v0.1 — закрытие долгов v0 (без undo)

### Milestone 0 — Инвентаризация (0.5 дня)

- [x] Разметить/зафиксировать границы будущих компонентов и общих хуков внутри `RBACPage.tsx` (часть вынесена в `components/` и `hooks/`).
- [x] Проверить и обеспечить, что `rbac/get-effective-access` содержит данные для “источников” (добавлены `sources[]` + обновлены контракты и тесты).

---

### Milestone 1 — Frontend: декомпозиция `RBACPage.tsx` и общие компоненты (2-4 дня)

- [x] Layout `/rbac` с переключателем режимов (`Назначения` / `Роли`) реализован.
- [x] Legacy вкладки спрятаны под feature-flag `VITE_RBAC_LEGACY_TABS` (по умолчанию выключен).
- [x] MVP: `RbacResourceBrowser` (левый список ресурсов для 2‑панельного сценария).
- [x] Выделить общие компоненты (переиспользуемые во всех resource types):
  - [x] `RbacPrincipalPicker` (user/group) с поиском;
  - [x] `RbacResourcePicker` (единый интерфейс выбора ресурса для `Кто -> Где`);
  - [x] `PermissionsTable` (единая таблица назначений + bulk actions);
    - [x] `RbacPermissionsTable` (общий рендер таблицы + pagination + error);
  - [x] `ReasonModal` (обязательный ввод reason на мутации);
    - [x] `useConfirmReason` (reason prompt для revoke);
  - [x] `AuditPanel` / `AuditDrawer` (просмотр admin audit log).
- [x] Вынести общий хук(и) для reference pickers: server-side search + pagination + merge options.
- [x] Перевести текущие табы на новые компоненты по одному (инкрементально), начиная с clusters/databases.

---

### Milestone 2 — `ResourceTree` clusters→databases (2-4 дня)

- [x] Реализовать дерево clusters→databases с lazy-load и pagination:
  - [x] кластеры кликабельны (можно выбрать кластер как ресурс);
  - [x] базы подгружаются при раскрытии кластера (server-side, без “все базы сразу”);
  - [x] поиск debounced; не делает запрос на каждый символ;
  - [x] кешировать загруженные узлы (чтобы не перезагружать при каждом раскрытии).
- [x] Интегрировать дерево в 2‑панельный сценарий `Где -> Кто` (Resource → Assignments) для clusters/databases.
- [x] Интегрировать дерево в фильтры сценария `Кто -> Где` (выбор resource для clusters/databases).

---

### Milestone 3 — `Effective access`: фильтры + источники (1-3 дня)

- [x] Панель `Effective access` (базовый просмотр итогового доступа) реализована.
- [x] Добавить фильтры по `resource_type` и конкретному ресурсу:
  - [x] для clusters/databases — выбор через `ResourceTree` (см. Milestone 2);
  - [x] для templates/workflows/artifacts — через ref pickers.
- [x] UI: таблица “итог по ресурсу” + раскрытие (expand) “все источники”:
  - [x] строка = итог по ресурсу (что разрешено и на каком уровне);
  - [x] раскрытие = subtable источников (direct/group/cluster/database и т.д., как возвращает API).
- [x] Расширить `rbac/get-effective-access` и обновить контракты в `contracts/**` (добавлены `sources[]`).

---

### Milestone 4 — Полировка и эксплуатация (1-2 дня)

- [x] Улучшить discoverability:
  - [x] пустые состояния (что делать дальше);
  - [x] подсказки “как выдать доступ на конкретную ИБ”.
- [x] Улучшить устойчивость UX:
  - [x] единообразные loading/error состояния;
  - [x] защита от случайных массовых операций (confirm + summary уже есть; довести до консистентности во всех местах).
- [x] Обновить документацию для операторов: “как выдавать доступ на ИБ”, “как смотреть эффективные права”.

---

### Milestone 5 — Тесты и контроль регрессий (параллельно)

- [x] Frontend (Vitest): тесты на новые общие хуки/трансформы (select pagination, tree data model, effective access sources).
- [x] Frontend (Playwright smoke/e2e):
  - [x] загрузка списков/дерева;
  - [x] grant/revoke с reason;
  - [x] create/update role с reason;
  - [x] `Effective access`: фильтрация + раскрытие источников.

---

## Backlog (optional)

### Undo/rollback по audit (optional, после v0.1) (2-4 дня)

- [x] Просмотр `rbac/list-admin-audit` встроен в `/rbac` (поиск + пагинация).
- [x] Реализовать “быстрый откат” для последних изменений:
  - [x] на уровне UI: кнопка “отменить” рядом с записью аудита;
  - [x] на уровне API: выполнять инверсию через существующие grant/revoke/set endpoints (без отдельного replay/undo);
  - [x] обязательный `reason` на undo.
