## 1. UI `/databases`: IBCMD connection profile modal
- [x] 1.1 Убрать дефолтные offline‑строки (`config/data`) при открытии модалки: `offline_entries` пустой, если профиль пустой.
- [x] 1.2 Добавить “Добавить из схемы” для offline‑флагов:
  - загрузка `driver_schema` через `GET /api/v2/operations/driver-commands/?driver=ibcmd`,
  - извлечение ключей из `driver_schema.connection.offline`,
  - добавление выбранного ключа в список строк key/value.
- [x] 1.3 Добавить валидацию key: запрет ключей с префиксом `--`/`-` и понятная ошибка (без автонормализации).

## 2. Тесты и quality gates
- [x] 2.1 Обновить/добавить unit‑тесты модалки профиля (`frontend/...DatabaseIbcmdConnectionProfileModal...`) под новый UX (без дефолтов).
- [x] 2.2 Обновить/добавить unit‑тест на добавление offline‑ключа из schema (mock ответа driver‑catalog).
- [x] 2.3 Прогнать `./scripts/dev/lint.sh` и `cd frontend && npm run test:run`.
