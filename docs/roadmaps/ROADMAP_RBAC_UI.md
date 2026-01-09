# Roadmap: RBAC UI (переключатель "Назначения / Роли")

Статус: 2026-01-09 — v0 готов: MVP + production-ready UX, включая 2‑панельный сценарий `Где -> Кто` (см. `frontend/src/pages/RBAC/RBACPage.tsx`).

Текущая реализация (v0):
- Режимы: `Назначения / Роли`.
- `Назначения`:
  - `Доступ к объектам`: два сценария `Кто -> Где` / `Где -> Кто` для clusters/databases/operation templates/workflow templates/artifacts (grant/revoke + reason, bulk для role+clusters/databases).
  - `Роли пользователей`: выдача ролей пользователю (replace/add/remove + reason).
  - `Effective access`: просмотр итогового доступа пользователя.
  - `Audit`: просмотр admin audit log.
  - `Infobase Users`: только staff (вне RBAC-редактора, но в той же странице).
- `Роли`: CRUD ролей + редактирование capabilities (reason обязателен).

Ограничения v0 (оставшиеся долги):
- Страница `RBACPage.tsx` всё ещё крупная: стоит вынести компоненты (`PrincipalPicker`, `ResourcePicker`, `PermissionsTable`, ...).
- 2‑панельный сценарий "Resource -> Assignments" реализован, но пока без дерева clusters→databases (используется список + поиск).
- Нет undo/rollback по audit.

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

## Приоритеты (Next)

Цель: довести v0 до "production-ready" UX на масштабе 700+ ИБ.

- [x] Reference pickers: server-side search + pagination (databases/templates/workflows/artifacts) без загрузки 1000/2000 options за раз.
- [x] Debounce для поиска (users/audit/permissions).
- [x] Confirm для bulk операций + summary (что изменится) перед применением.
- [x] Feature-flag для старых вкладок: `VITE_RBAC_LEGACY_TABS` (по умолчанию выключен).
- [ ] Упрощение `RBACPage.tsx` (выделить общие компоненты и уменьшить дубль кода).
- [x] "Где используется роль" + "клонировать роль" (ускорить админские сценарии).

---

## TODO

### Milestone 0 — Инвентаризация и UX-спека (1-2 дня)

- [x] Зафиксировать список поддерживаемых resource types для RBAC UI v2:
  - [x] ресурсы: clusters, databases, operation templates, workflow templates, artifacts;
  - [x] principals: user и role (group);
  - [x] bulk: только role+clusters/databases (MVP).
- [x] Описать UX сценарии (поддерживаются текущим UI):
  - [x] "выдать доступ бухгалтеру на ИБ X" → `Назначения / Доступ к объектам` (principal=user, resource=database).
  - [x] "дать группе доступ на набор ИБ" → `Назначения / Доступ к объектам` (principal=role, bulk databases).
  - [x] "посмотреть эффективные права пользователя на ИБ" → `Назначения / Effective access` (включить databases, выбрать user).
  - [x] "создать роль и раздать её" → `Роли` (create) + `Назначения / Роли пользователей` (assign roles).
- [x] Определить первичный фокус внутри режима `Назначения`:
  - [x] MVP: единый экран "filters → table" (principal+resource+level+search) вместо раздельных вкладок по типам.
  - [ ] (опция) перейти на 2-панельный сценарий "Resource → Assignments" (см. Milestone 3).
- [x] Зафиксировать DoD по производительности (минимум для масштаба 700+ ИБ):
  - [x] Reference списки (clusters/databases/…) должны поддерживать server-side search + pagination (без загрузки 2000+ options в Select).
  - [x] Поиск должен быть debounced (250-400ms) и не делать запрос на каждый символ.
  - [x] Таблица назначений: backend pagination (limit/offset), pageSize по умолчанию 50, время ответа <= 1с в типовых условиях.

---

### Milestone 1 — Backend/API: сверка и точечные улучшения (0-2 дня)

План: максимум переиспользования существующих endpoints `api/v2/rbac/*`.

- [x] Проверить, что фронту достаточно текущих API (без добавления новых) — текущая реализация использует существующие endpoints:
  - [x] refs: `rbac/ref-clusters`, `rbac/ref-databases`, `rbac/ref-operation-templates`, `rbac/ref-workflow-templates`, `rbac/ref-artifacts`;
  - [x] permissions list/grant/revoke для user/group на нужные resource types;
  - [x] roles CRUD + capabilities;
  - [x] audit: `rbac/list-admin-audit`;
  - [x] effective access: `rbac/get-effective-access`.
- [ ] Если фронту нужно унифицировать множество похожих вызовов:
  - [ ] (опционально) добавить общий endpoint вида `rbac/list-resource-permissions?resource_type=...` и аналогичные grant/revoke,
  - [ ] при этом обновить контракты в `contracts/**` и оставить старые endpoints на период миграции.

---

### Milestone 2 — Frontend: каркас страницы и выделение общих компонентов (2-4 дня)

- [x] Вынести новый layout `/rbac` с переключателем режимов (`Назначения` / `Роли`) (реализовано в существующей странице, без выделения компонентов).
- [ ] Выделить общие компоненты (переиспользуемые во всех resource types):
  - [ ] `PrincipalPicker` (user/group) с поиском;
  - [ ] `ResourcePicker` / `ResourceTree` (включая lazy-load);
    - [x] MVP: `RbacResourceBrowser` (левый список ресурсов для 2‑панельного сценария).
    - [ ] Tree (clusters→databases) и переиспользование во всех resource types.
  - [ ] `PermissionsTable` (единая таблица назначений + bulk actions);
  - [ ] `ReasonModal` (обязательный ввод reason на мутации);
  - [ ] `AuditDrawer` (просмотр admin audit log).
- [ ] Перевести текущие табы на новые компоненты по одному (инкрементально), начиная с clusters/databases.
- [x] Временно сохранить старые вкладки под feature-flag `VITE_RBAC_LEGACY_TABS` (для отката UI без отката API).

---

### Milestone 3 — Режим "Назначения" (MVP) (3-6 дней)

- [x] Реализовать единый экран "Доступ к объектам" (principal+resource фильтры → таблица назначений) для clusters/databases/templates/workflows/artifacts.
- [x] Реализовать 2-панельный сценарий "Resource -> Assignments":
  - [x] слева: выбор resource type + список объектов с поиском;
  - [x] справа: таблица назначений для выбранного объекта (users/groups -> roles/permissions).
- [x] Поддержать user и group назначения (grant/revoke; bulk пока только для групп на clusters/databases).
- [x] Добавить панель "Effective access" для выбранного principal (вкладка `Effective access`):
  - [ ] с фильтром по ресурсу/типу;
  - [ ] с понятным объяснением источников (если применимо).
- [ ] UX-предохранители:
  - [x] подтверждение массовых операций;
  - [x] блокировка кнопок при отсутствии `reason` (reason обязателен на формах).
- [ ] Производительность:
  - [x] пагинация на таблицах (limit/offset);
  - [ ] виртуализация таблиц (если нужно);
  - [x] debounce поиска.

---

### Milestone 4 — Режим "Роли" (MVP) (3-6 дней)

- [x] Экран списка ролей:
  - [x] поиск/фильтры;
  - [x] create/rename/delete с `reason`;
  - [x] "клонировать роль".
- [x] Экран редактирования роли:
  - [x] редактирование capabilities/прав роли в едином UI (без вкладок по типам);
  - [x] поиск по capabilities;
  - [x] сохранение с `reason`.
- [x] "Где используется роль" (usage):
  - [x] показать назначения роли (counts по ресурсам + переход в `Назначения` с фильтром по роли).

---

### Milestone 5 — Аудит и откат (optional, но желательно) (2-4 дня)

- [x] Встроить просмотр `rbac/list-admin-audit` прямо в `/rbac` (поиск + пагинация; фильтры по action/target/actor пока не выделены отдельно).
- [ ] (опционально) Реализовать "быстрый откат" для последних изменений:
  - [ ] на уровне UI: кнопка "отменить" рядом с записью аудита;
  - [ ] на уровне API: если нужно, добавить безопасный endpoint "replay/undo" (или выполнять инверсию через существующие grant/revoke),
  - [ ] обязательный `reason` на undo.

---

### Milestone 6 — Полировка и эксплуатация (1-3 дня)

- [ ] Улучшить discoverability:
  - [ ] пустые состояния (что делать дальше);
  - [ ] подсказки "как выдать доступ на конкретную ИБ".
- [ ] Добавить метрики/события (если у вас принято) по действиям RBAC UI: grant/revoke, role save, errors.
- [ ] Обновить документацию для операторов: "как выдавать доступ на ИБ", "как смотреть эффективные права".

---

### Milestone 7 — Тесты и контроль регрессий (параллельно)

- [ ] Backend: дописать тесты только если меняем API (иначе — достаточно текущих).
- [ ] Frontend: минимум smoke/e2e на:
  - [ ] загрузку списков;
  - [ ] grant/revoke с reason;
  - [ ] create/update role с reason;
  - [ ] просмотр effective access.
