# Change: UI для DBMS user mapping (CC user ↔ DBMS creds)

## Why
Сейчас DBMS credential mapping для offline-подключения `ibcmd` существует на backend (модель/эндпоинты), но в UI отсутствует сценарий управления этими данными. Это вынуждает администраторов работать через API/БД и усложняет эксплуатацию.

## What Changes
- В UI добавляется экран (или секция существующего экрана RBAC) для управления DBMS user mapping по конкретной базе:
  - список DBMS mapping записей (actor + service);
  - создание/редактирование/удаление;
  - установка/сброс пароля отдельными действиями;
  - поиск/фильтры.
- Доступ к управлению DBMS mapping предоставляется только staff/admin пользователям (в терминах текущей системы авторизации).

## Non-Goals
- Не добавляем ввод DBMS creds в `DriverCommandBuilder` или shortcuts (они должны оставаться "resolved at runtime").
- Не добавляем bulk-маппинг сразу для нескольких баз (будет отдельным change при необходимости).
- Не меняем схему хранения секретов (пароли остаются encrypted-at-rest на backend; UI не отображает пароль).

## Impact
- Specs: `dbms-credentials-mapping`
- Frontend: добавление UI для DBMS mappings (вероятно: `frontend/src/pages/RBAC/RBACPage.tsx` + queries/hooks)
- Tests: frontend unit + e2e (smoke)

## Open Questions
- Место размещения UI: предлагается добавить вкладку/секцию на `RBAC` экране рядом с Infobase users. Альтернатива: карточка базы (Database details).
- Ролевой доступ: предлагается “только staff/admin” (как в backend API). Если нужен более тонкий RBAC, это отдельная задача.
