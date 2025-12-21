# OpenAPI Contract-First Чек-лист

Быстрая справка для работы с OpenAPI контрактами в проекте CommandCenter1C.

---

## Быстрый старт

### 1. Установка git hooks (первый раз)

```bash
git config core.hooksPath .githooks
```

**Проверка установки:**
```bash
git config core.hooksPath
# Должно вывести: .githooks
```

---

### 2. Workflow разработки

#### Когда нужно обновить API спецификацию:

1. **Отредактировать спецификацию**
   ```bash
   # Отредактировать файл:
   contracts/orchestrator/openapi.yaml
   ```

2. **Валидировать изменения** (обязательно ПЕРЕД коммитом)
   ```bash
   ./contracts/scripts/validate-specs.sh
   ```
   Должно быть: `✓ All specifications are valid`

3. **Сгенерировать новые типы**
   ```bash
   ./contracts/scripts/generate-all.sh
   ```
   Будут обновлены:
   - `go-services/api-gateway/internal/routes/generated/`
   - `frontend/src/api/generated/`

4. **Коммитить**
   ```bash
   git add contracts/orchestrator/openapi.yaml
   git add go-services/api-gateway/internal/routes/generated/
   git add frontend/src/api/generated/
   git commit -m "fix: Update orchestrator API spec - add new field"
   ```

   **Важно:** Git hook автоматически:
   - Валидирует спецификацию
   - Проверяет breaking changes
   - Регенерирует клиентов
   - Добавляет сгенерированные файлы в коммит

---

## Общие команды

### Валидировать спецификацию

```bash
./contracts/scripts/validate-specs.sh
```

**Результаты:**
- ✓ Valid → OK
- ✗ Invalid → ошибка синтаксиса YAML или OpenAPI

### Сгенерировать клиентов

```bash
# Нормальная генерация (пропускает неизмененные)
./contracts/scripts/generate-all.sh

# Принудительная регенерация
./contracts/scripts/generate-all.sh --force
```

### Проверить breaking changes

```bash
./contracts/scripts/check-breaking-changes.sh
```

---

## Артефакты генерации

- **API Gateway (Go):** `go-services/api-gateway/internal/routes/generated/`
- **Frontend (TypeScript):** `frontend/src/api/generated/`
