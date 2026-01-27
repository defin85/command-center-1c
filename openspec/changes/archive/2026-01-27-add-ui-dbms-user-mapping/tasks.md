## 1. UI: DBMS user mapping
- [x] 1.1 Добавить в frontend API слой (queries/hooks) для DBMS mapping эндпоинтов: list/create/update/delete + set/reset password.
- [x] 1.2 Добавить UI для управления DBMS mapping по выбранной базе (actor + service):
  - выбор базы;
  - таблица пользователей/маппингов;
  - создание/редактирование/удаление;
  - поиск/фильтры (минимум: поиск по DB username и по CC user).
- [x] 1.3 Пароль: UI не отображает текущий пароль; предоставляет действия “Set password” и “Reset password” с подтверждением.
- [x] 1.4 Ограничение доступа: UI скрыт/недоступен не-staff пользователям; обработка 403 без падения страницы.

## 2. Тесты и документация
- [x] 2.1 Unit tests (vitest) для формы/валидаций (actor vs service) и базового рендера списка.
- [x] 2.2 E2E smoke (Playwright): создание mapping (без раскрытия пароля), сохранение/обновление и проверка отображения `db_password_configured`.
- [x] 2.3 Обновить `docs/` (короткая заметка), где искать настройку DBMS mappings для offline `ibcmd`.
