# Design: Guided params editor в Action Catalog

## UX
### Layout driver/command_id
Текущее поведение: Select для `driver`/`command_id` может схлопываться до ~100px ширины.
Цель: стабильная ширина и пропорции (например 1/3 + 2/3) вне зависимости от содержимого.
Решение: использовать flex‑layout (не `Space`), задать `flex` и `width: 100%` для Select.

### Guided / Raw JSON
В секции `params`:
- Переключатель (Tabs/Segmented): **Guided** (default) и **Raw JSON**.
- В Guided:
  - интерактивные поля для schema‑params.
  - опционально: показывать “Unknown keys: N” (ключи, отсутствующие в schema), чтобы пользователь понимал, что они будут сохранены.
- В Raw JSON:
  - textarea редактор, как сейчас.
  - ошибка/подсветка, если JSON невалиден (и Guided не может отобразиться).

## Данные и синхронизация
### Источник schema
Driver catalog v2: `GET /api/v2/operations/driver-commands/?driver=...` → `commands_by_id[command_id].params_by_name`.

### Модель состояния
В модалке держим:
- `paramsObject` (Record<string, unknown>) — каноническое представление.
- `paramsJson` (string) — отображаемое Raw JSON.

Синхронизация:
- При изменении Guided‑поля: обновить `paramsObject` (merge) → пересчитать `paramsJson = JSON.stringify(paramsObject, null, 2)`.
- При редактировании Raw JSON:
  - если JSON валиден и object: обновить `paramsObject`;
  - если невалиден: оставить `paramsObject` прежним и показать ошибку; при попытке перейти в Guided — блокировать/показывать сообщение.

### Preserve unknown keys
Guided‑редактор изменяет только schema‑ключи, не удаляя остальные:
- `next = { ...currentParamsObject, [schemaKey]: newValue }` (+ удаление ключа только по явному действию пользователя, если поддерживаем).

## Переиспользование компонентов
Рекомендация: переиспользовать существующий рендеринг параметров из `DriverCommandBuilder` (например ParamField) для единообразия типов/контролов.

