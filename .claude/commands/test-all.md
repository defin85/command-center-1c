---
description: Run all tests for all components (Python, Go, TypeScript)
---

Запустить все тесты для всех компонентов проекта.

## Действия

1. **Убедиться что сервисы запущены**
   ```bash
   docker-compose ps
   # Если не запущены, запустить: docker-compose up -d
   ```

2. **Запустить Python тесты (Orchestrator)**
   ```bash
   cd /c/1CProject/command-center-1c/orchestrator
   python -m pytest -v --cov --cov-report=html
   ```

3. **Запустить Go тесты (API Gateway, Workers)**
   ```bash
   cd /c/1CProject/command-center-1c/go-services
   go test -v -race -coverprofile=coverage.out ./...
   go tool cover -html=coverage.out
   ```

4. **Запустить TypeScript тесты (Frontend)**
   ```bash
   cd /c/1CProject/command-center-1c/frontend
   npm test -- --coverage
   ```

5. **Просмотреть результаты**
   - Python: `orchestrator/htmlcov/index.html`
   - Go: `go-services/coverage.html`
   - TypeScript: `frontend/coverage/index.html`

## Параметры (если есть)

- `--fast` - запустить только quick tests (без integration tests)
- `--no-coverage` - без сбора coverage информации
- `--fail-on-warning` - fail если есть warnings

## Примеры

```bash
# Полный набор тестов с coverage
make test-all

# Только быстрые unit tests
make test-all --fast

# Конкретный компонент
cd orchestrator && pytest -v

# С проверкой на race conditions (Go)
go test -race ./...

# Watch mode (для разработки)
cd frontend && npm test -- --watch
```

## Expectations

**Coverage requirements:**
- Python: >= 70% overall, >= 90% for services.py
- Go: >= 70% overall, >= 80% for critical packages
- TypeScript: >= 70% overall

**Все тесты должны проходить** перед commit в master

## Troubleshooting

**Test timeout:**
```bash
# Увеличить timeout
go test -timeout 5m ./...
pytest --timeout=30 orchestrator/
```

**Database connection error:**
```bash
# Убедиться что PostgreSQL запущен
docker-compose logs postgres

# Пересоздать
docker-compose down postgres
docker-compose up -d postgres
```

**Module not found:**
```bash
# Python
pip install -r orchestrator/requirements.txt

# Go
go mod download

# TypeScript
cd frontend && npm install
```

## Связанные Commands

- `dev-start` - запустить сервисы для тестирования
- `check-health` - проверить здоровье сервисов после тестов
- `build-docker` - собрать Docker образы для production tests
