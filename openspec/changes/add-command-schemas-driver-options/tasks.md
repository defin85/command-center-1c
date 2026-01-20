## 1. Proposal (Спека/дизайн)
- [x] 1.1 Зафиксировать формат driver-level schema (где хранится, как мерджится base/overrides/effective)
- [x] 1.2 Определить правила приоритета и конфликтов (connection vs additional_args vs params)
- [x] 1.3 Определить область драйверов (MVP: `ibcmd`)

## 2. Implementation (Реализация)
- [x] 2.1 Backend: расширить формат каталога и overrides для driver-level schema (без breaking)
- [x] 2.2 Backend: обновить валидацию и preview (command schemas) с учётом driver-level schema
- [x] 2.3 Backend: обновить выполнение schema-driven команд (минимум `execute-ibcmd-cli`) — connection options отдельно от `params_by_name`
- [x] 2.4 Frontend: обновить `Command Schemas` UI — отдельная секция для driver-level schema + Raw JSON
- [x] 2.5 Тесты: backend (валидация/preview/execute), frontend (рендер/редактирование/валидация на моках)
- [x] 2.6 Контракты: обновить `contracts/orchestrator/openapi.yaml`, прогнать `./contracts/scripts/validate-specs.sh`, регенерировать клиентов
- [x] 2.7 Docs: описать концепцию driver schema + command schema и правила конфликтов
