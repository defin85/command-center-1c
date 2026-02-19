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

#### Когда нужно обновить orchestrator API спецификацию:

1. **Отредактировать modular source**
   ```bash
   # Source of truth:
   contracts/orchestrator/src/openapi.yaml
   contracts/orchestrator/src/paths/*.yaml
   contracts/orchestrator/src/components/schemas/*.yaml
   ```

2. **Пересобрать и проверить bundle**
   ```bash
   ./contracts/scripts/build-orchestrator-openapi.sh build
   ./contracts/scripts/build-orchestrator-openapi.sh check
   ```

3. **Валидировать изменения** (обязательно ПЕРЕД коммитом)
   ```bash
   ./contracts/scripts/validate-specs.sh
   ```
   Должно быть: `All specifications are valid`

4. **Сгенерировать маршруты/клиенты**
   ```bash
   ./contracts/scripts/generate-all.sh
   ```
   Будут обновлены:
   - `go-services/api-gateway/internal/routes/generated/`
   - `frontend/src/api/generated/`

5. **Коммитить**
   ```bash
   git add contracts/orchestrator/src/
   git add contracts/orchestrator/openapi.yaml
   git add go-services/api-gateway/internal/routes/generated/
   git add frontend/src/api/generated/
   git commit -m "refactor(openapi): update orchestrator modular contract"
   ```

   **Важно:** Git hook автоматически:
   - Проверяет актуальность orchestrator bundle;
   - Валидирует спецификации;
   - Проверяет breaking changes;
   - Регенерирует клиентов;
   - Добавляет сгенерированные файлы в коммит.

---

## Общие команды

### Сборка/check orchestrator bundle

```bash
# Сборка bundle из src/**
./contracts/scripts/build-orchestrator-openapi.sh build

# Проверка, что bundle не устарел
./contracts/scripts/build-orchestrator-openapi.sh check
```

### Валидировать спецификацию

```bash
./contracts/scripts/validate-specs.sh
```

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

- **Orchestrator source:** `contracts/orchestrator/src/**`
- **Orchestrator bundle:** `contracts/orchestrator/openapi.yaml`
- **API Gateway (Go routes):** `go-services/api-gateway/internal/routes/generated/`
- **Frontend (TypeScript):** `frontend/src/api/generated/`
