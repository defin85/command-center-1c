# Design: Единая точка ответственности за tenant context

## Термины
- **Tenant context**: выбранный tenant, в рамках которого исполняется запрос (изоляция данных/конфигураций).
- **Resolver**: функция, выбирающая tenant по входам запроса и данным пользователя.

## Текущее состояние (проблема)
В проекте существует более одного “пути” выставления tenant context:
- аутентификация tenant-aware,
- permission/guard для подстраховки тестов,
- локальные проверки в отдельных view.

Это усложняет reasoning и увеличивает риск несогласованности.

## Целевое состояние
1) **Одна точка ответственности** за установку tenant context на запрос:
   - единый entrypoint (один слой), единый resolver.
2) Все tenant-scoped места получают tenant context одинаково:
   - `request.tenant_id` (и при необходимости thread-local для ORM фильтрации).
3) Тесты верифицируют реальный pipeline, а не “обходные” режимы.

## Варианты реализации (для выбора)

### Вариант A (предпочтительный): tenant context только через DRF authentication
- TenantContextAuthentication:
  - парсит `X-CC1C-Tenant-ID`,
  - проверяет membership,
  - выставляет `request.tenant_id` и thread-local.
- Удаляем/не используем отдельные permission-guards для tenant context.
- Тесты переводим на реальную авторизацию (JWT/session), не используя `force_authenticate`.

**Плюсы:** один механизм для runtime, меньше скрытой магии.  
**Минусы:** нужно перелопатить тесты, которые использовали `force_authenticate`.

### Вариант B: отдельный middleware после auth
В Django middleware tenant context можно выставить после `AuthenticationMiddleware`.

**Риск:** JWT/service auth для API сейчас живёт в DRF authentication, а не в Django auth middleware → middleware придётся повторять логику JWT, что нарушает SRP.

## Контракт ошибок (ожидаемо)
- Невалидный tenant header → 400 (валидационная ошибка).
- Tenant не найден → 403 (или 404 по продуктовой политике; сейчас 403 в resolver).
- Нет membership → 403.

