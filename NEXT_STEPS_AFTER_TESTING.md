# Следующие шаги после тестирования OpenAPI Contract-First

**Дата:** 2025-11-24
**Статус:** Готово к использованию

---

## Для каждого разработчика

### 1. Первая настройка (одноразово)

```bash
# Активировать git hooks
git config core.hooksPath .githooks

# Проверить установку
git config core.hooksPath
# Должно вывести: .githooks
```

### 2. Ознакомление с документацией

Прочитайте в этом порядке:
1. `TESTING_RESULTS.md` - быстрый обзор
2. `docs/OPENAPI_CONTRACT_CHECKLIST.md` - справка для работы
3. `contracts/README.md` - архитектура
4. `contracts/ras-adapter/EXAMPLE_USAGE.md` - примеры кода

### 3. Первая работа с API

```bash
# Обновить OpenAPI спецификацию
vim contracts/ras-adapter/openapi.yaml

# Валидировать изменения
./contracts/scripts/validate-specs.sh

# Сгенерировать новые типы
./contracts/scripts/generate-all.sh

# Обновить код в ras-adapter (Go)
# Обновить код в orchestrator (Python)

# Коммитить
git add contracts/ras-adapter/openapi.yaml
git add go-services/ras-adapter/internal/api/generated/
git add orchestrator/apps/databases/clients/generated/
git commit -m "feat: Add new endpoint to ras-adapter API"
```

---

## Для Team Lead / Architecture

### 1. Проверка внедрения

- ✅ Все 13 тестов пройдены
- ✅ Git hooks активированы на сервере
- ✅ CI/CD pipeline включает Phase 1.5

### 2. Расширение на новые сервисы

Когда будет нужно добавить контракт для `api-gateway` или `worker`:

```bash
# Создать структуру
mkdir -p contracts/api-gateway
touch contracts/api-gateway/openapi.yaml

# Скопировать и адаптировать спецификацию
cp contracts/ras-adapter/openapi.yaml contracts/api-gateway/

# Обновить generate-all.sh (строка ~50)
# Раскомментировать/включить api-gateway

# Валидировать и генерировать
./contracts/scripts/validate-specs.sh
./contracts/scripts/generate-all.sh
```

### 3. Мониторинг качества

Следить за метриками:
- Coverage сгенерированного кода > 80%
- Время генерации < 500ms
- Нет breaking changes без версионирования

---

## Для DevOps / Infrastructure

### 1. CI/CD интеграция

Убедитесь что в CI/CD pipeline:

```yaml
# .github/workflows/build.yml (или похожий)
- name: Validate OpenAPI specs
  run: ./contracts/scripts/validate-specs.sh

- name: Generate API clients
  run: ./contracts/scripts/generate-all.sh

- name: Compile Go services
  run: |
    cd go-services/ras-adapter
    go build ./cmd
```

### 2. Docker builds

Phase 1.5 интегрирована в `scripts/dev/start-all.sh`, убедитесь что:

```bash
# При запуске start-all.sh:
# 1. Go компилируется
# 2. Генерируются клиенты
# 3. Docker контейнеры запускаются
```

### 3. Git hooks на сервере

На сервере (pre-push hook):

```bash
git config core.hooksPath .githooks
# Это уже сделано - просто убедитесь при клонировании
```

---

## Расширение функциональности

### Сценарий 1: Добавить новый endpoint в ras-adapter

1. Обновить спецификацию:
   ```yaml
   /api/v1/new-endpoint:
     get:
       operationId: getNewEndpoint
       # ... полная спецификация
   ```

2. Валидировать и генерировать:
   ```bash
   ./contracts/scripts/validate-specs.sh
   ./contracts/scripts/generate-all.sh
   ```

3. Реализовать в Go:
   ```go
   // go-services/ras-adapter/internal/api/handlers/new_endpoint.go
   func GetNewEndpoint(c *gin.Context) {
       // Типы автоматически доступны из generated
   }
   ```

4. Реализовать в Python:
   ```python
   # orchestrator/apps/databases/services/ras_client.py
   from apps.databases.clients.generated.ras_adapter_api_client.api import get_new_endpoint

   result = await get_new_endpoint(client=client)
   ```

### Сценарий 2: Breaking changes

Если нужно сделать несовместимый изменение:

1. Обновить версию:
   ```yaml
   info:
     version: 2.0.0  # было 1.0.0
   ```

2. Создать новый путь:
   ```yaml
   /api/v2/infobases:  # новый путь
     # новая спецификация

   /api/v1/infobases:  # старый путь (deprecated)
     # старая спецификация
   ```

3. Создать migration guide:
   ```markdown
   # Migration Guide v1 → v2

   ## Изменения:
   - Parameter `cluster` → `cluster_id`
   - Response format changed

   ## Как обновить:
   - Обновить вызовы в коде
   - Перегенерировать клиентов
   ```

4. Коммитить с правильным сообщением:
   ```bash
   git commit -m "feat!: Upgrade ras-adapter API to v2.0

   BREAKING CHANGES: cluster parameter renamed to cluster_id
   See migration guide: docs/migration/v1-to-v2.md"
   ```

---

## Когда что-то пошло не так

### Ошибка валидации при коммите

```bash
# Git hook заблокировал коммит
# Смотри сообщение об ошибке

./contracts/scripts/validate-specs.sh
# Исправи ошибку в YAML

git add contracts/ras-adapter/openapi.yaml
git commit -m "fix: Correct OpenAPI spec syntax"
```

### Сгенерированный код не компилируется

```bash
# Обычно это значит, что спецификация изменилась
# но генератор был вызван с неправильными параметрами

./contracts/scripts/generate-all.sh --force
cd go-services/ras-adapter && go build ./cmd
```

### Python клиент не импортируется

```bash
# Проверить что генерация прошла
ls orchestrator/apps/databases/clients/generated/

# Принудительная регенерация
./contracts/scripts/generate-all.sh --force

# Проверить __init__.py файлы
cat orchestrator/apps/databases/clients/generated/__init__.py
```

---

## Полезные команды

```bash
# Валидировать спецификацию
./contracts/scripts/validate-specs.sh

# Генерировать клиентов (пропускает неизмененные)
./contracts/scripts/generate-all.sh

# Принудительная регенерация всего
./contracts/scripts/generate-all.sh --force

# Проверить breaking changes
./contracts/scripts/check-breaking-changes.sh

# Запустить весь workflow (включая генерацию)
./scripts/dev/start-all.sh

# Просмотреть сгенерированный Go код
head -100 go-services/ras-adapter/internal/api/generated/server.go

# Проверить структуру Python клиента
ls -la orchestrator/apps/databases/clients/generated/ras_adapter_api_client/
```

---

## Чек-лист для новой версии

Когда выпускаете новую версию API:

- [ ] Обновлена OpenAPI спецификация в `contracts/ras-adapter/openapi.yaml`
- [ ] Валидация пройдена: `./contracts/scripts/validate-specs.sh`
- [ ] Клиенты сгенерированы: `./contracts/scripts/generate-all.sh`
- [ ] Go код скомпилирован: `cd go-services/ras-adapter && go build ./cmd`
- [ ] Python клиент импортируется
- [ ] Тесты пройдены: `./scripts/dev/test-all.sh`
- [ ] Обновлена документация (если breaking changes)
- [ ] Сгенерированные файлы добавлены в коммит
- [ ] Версия API обновлена в `info.version`

---

## Поддержка и вопросы

**Быстрая справка:**
- `docs/OPENAPI_CONTRACT_CHECKLIST.md`

**Полная документация:**
- `contracts/README.md`
- `contracts/ras-adapter/EXAMPLE_USAGE.md`

**Тестовый отчет:**
- `OPENAPI_CONTRACT_TESTING_REPORT.md`

**Проектный контекст:**
- `CLAUDE.md` (секция OPENAPI CONTRACTS)

---

**Дата последнего обновления:** 2025-11-24
**Статус:** Актуально
**Версия документа:** 1.0
