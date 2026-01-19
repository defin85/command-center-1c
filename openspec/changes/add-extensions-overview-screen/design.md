## Context (Контекст)
У нас уже есть:
- `ui.action_catalog` (RuntimeSetting) и UI для запуска действий расширений из `/databases`.
- Snapshot расширений в Postgres (`DatabaseExtensionsSnapshot`) и endpoint `GET /api/v2/databases/get-extensions-snapshot/`.

Сейчас snapshot хранит payload результата операции в свободном JSON и UI показывает его как raw JSON.
Для обзорного экрана нужен структурированный список расширений и агрегирование по всем базам.

## Goals / Non-Goals (Цели / Не цели)
- Goals (Цели):
  - Дать обзор: какие расширения установлены на каких базах (агрегация по всему парку).
  - Давать фильтрацию по имени/версии/статусу (enabled/disabled/unknown) и freshness snapshot'а.
  - Поддержать drill-down: показать список баз для выбранного расширения/версии/статуса.
  - Соблюдать RBAC: пользователь видит только базы, к которым имеет доступ.
- Non-Goals (Не цели):
  - Выполнять “живой” обход всех баз на открытии страницы (используем сохранённые snapshot'ы).
  - Внедрять новый engine выполнения; используем существующие operations/workflows.

## Data Model (Данные)
### Нормализованный snapshot расширений
Текущий `DatabaseExtensionsSnapshot.snapshot` содержит произвольный dict результата операции (обычно `stdout/stderr/...`).
Нужно договориться о нормализованной структуре для UI:
- `snapshot.extensions`: массив объектов расширений.
- `snapshot.raw`: опционально исходные поля результата (чтобы не потерять диагностику).
- `snapshot.parse_error`: опционально текст ошибки парсинга.

Минимальный shape для `snapshot.extensions[*]`:
- `name` (string, required): имя расширения (ключ агрегации по умолчанию).
- `version` (string, optional): версия/релиз, если доступно.
- `is_active` (bool, optional): включено ли расширение в базе.

Примечание: поля зависят от того, что возвращает configured list/sync action. Если формат не позволяет достоверно
извлечь поля, сохраняем `parse_error` и UI показывает raw.

## Parsing Strategy (Парсинг)
Цель: получить `snapshot.extensions` из результата list/sync.
Предпочтительный порядок:
1) Если worker/operation result уже содержит структурированный список (например `data.extensions`), используем его как источник истины.
2) Иначе пробуем распарсить `stdout` известного формата (best-effort).
3) Если парсинг невозможен, сохраняем `parse_error` и raw.

## API Design (API)
Добавить ресурсные endpoints (v2), работающие поверх snapshot'ов.

### 1) Aggregated overview
`GET /api/v2/extensions/overview/`
Возвращает агрегированный список расширений по доступным базам.

Пример ответа:
```json
{
  "extensions": [
    {
      "name": "ExtA",
      "installed_count": 120,
      "active_count": 118,
      "inactive_count": 2,
      "missing_count": 580,
      "unknown_count": 0,
      "versions": [
        { "version": "1.2.3", "count": 100 },
        { "version": "1.2.4", "count": 20 }
      ],
      "latest_snapshot_at": "2026-01-01T00:00:00Z"
    }
  ],
  "count": 50,
  "total": 200
}
```

Фильтры (первый MVP):
- `search` по имени расширения
- `status` (active/inactive/missing/unknown)
- `version` (точное совпадение)
- `cluster_id` (если у баз есть кластер)

### 2) Drill-down (databases for extension)
`GET /api/v2/extensions/overview/databases/?name=ExtA&version=1.2.3&status=active`
Возвращает список баз (только доступных пользователю) и статус расширения в каждой базе.

## Authorization (Безопасность)
- Требование: пользователь должен быть аутентифицирован.
- Данные должны быть отфильтрованы по доступным базам (аналогично `/databases`): пользователь видит только базы,
  для которых у него есть `view_database` (или эквивалент).

## Performance (Производительность)
Данные парка: 700+ баз. Агрегация на каждый запрос потенциально дорога, поэтому MVP:
- Использовать нормализованные snapshot'ы, чтобы не парсить `stdout` на лету.
- Возможна короткая серверная кешировка результата (TTL 10–30s) при необходимости.

## Open Questions (Открытые вопросы)
- Ключ агрегации: группировать только по `name` или по `name+version` с отдельными строками?
- Нужны ли дополнительные поля в таблице (например “обновлено N часов назад”, “источник операции”)?

