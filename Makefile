.PHONY: help dev test build deploy-staging deploy-prod logs stop clean

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

## help: Показать это сообщение помощи
help:
	@echo "$(BLUE)CommandCenter1C - Available commands:$(NC)"
	@echo ""
	@grep -E '^##' Makefile | sed 's/##/  $(GREEN)/' | sed 's/:/$(NC):/'
	@echo ""

## dev: Запустить все сервисы в dev режиме
dev:
	@echo "$(BLUE)Starting development environment...$(NC)"
	docker-compose up --build

## dev-detached: Запустить все сервисы в фоне
dev-detached:
	@echo "$(BLUE)Starting development environment in detached mode...$(NC)"
	docker-compose up -d --build

## test: Запустить все тесты
test: test-go test-python test-frontend

## test-go: Запустить Go тесты
test-go:
	@echo "$(BLUE)Running Go tests...$(NC)"
	cd go-services/api-gateway && go test -v -race -coverprofile=coverage.out ./...
	cd go-services/worker && go test -v -race -coverprofile=coverage.out ./...

## test-python: Запустить Python тесты
test-python:
	@echo "$(BLUE)Running Python tests...$(NC)"
	cd orchestrator && pytest --cov=. --cov-report=html --cov-report=term

## test-frontend: Запустить Frontend тесты
test-frontend:
	@echo "$(BLUE)Running Frontend tests...$(NC)"
	cd frontend && npm test -- --coverage

## lint: Запустить линтеры для всех компонентов
lint: lint-go lint-python lint-frontend

## lint-go: Запустить Go линтер
lint-go:
	@echo "$(BLUE)Linting Go code...$(NC)"
	cd go-services/api-gateway && golangci-lint run
	cd go-services/worker && golangci-lint run

## lint-python: Запустить Python линтеры
lint-python:
	@echo "$(BLUE)Linting Python code...$(NC)"
	cd orchestrator && flake8 .
	cd orchestrator && black --check .
	cd orchestrator && isort --check-only .

## lint-frontend: Запустить Frontend линтер
lint-frontend:
	@echo "$(BLUE)Linting Frontend code...$(NC)"
	cd frontend && npm run lint

## build: Собрать все Docker образы
build:
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker build -t commandcenter1c/api-gateway:latest -f go-services/api-gateway/Dockerfile go-services/api-gateway
	docker build -t commandcenter1c/worker:latest -f go-services/worker/Dockerfile go-services/worker
	docker build -t commandcenter1c/orchestrator:latest -f orchestrator/Dockerfile orchestrator
	docker build -t commandcenter1c/frontend:latest -f frontend/Dockerfile frontend

## logs: Показать логи всех сервисов
logs:
	docker-compose logs -f

## logs-api: Показать логи API Gateway
logs-api:
	docker-compose logs -f api-gateway

## logs-orchestrator: Показать логи Orchestrator
logs-orchestrator:
	docker-compose logs -f orchestrator

## logs-worker: Показать логи Workers
logs-worker:
	docker-compose logs -f worker

## logs-frontend: Показать логи Frontend
logs-frontend:
	docker-compose logs -f frontend

## stop: Остановить все сервисы
stop:
	@echo "$(YELLOW)Stopping all services...$(NC)"
	docker-compose down

## clean: Очистить все данные и контейнеры
clean:
	@echo "$(YELLOW)Cleaning up...$(NC)"
	docker-compose down -v
	rm -rf data/
	rm -rf logs/
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "coverage.out" -delete
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name "htmlcov" -exec rm -r {} +

## setup: Первоначальная настройка проекта
setup:
	@echo "$(BLUE)Setting up project...$(NC)"
	@echo "Installing Go dependencies..."
	cd go-services/api-gateway && go mod download
	cd go-services/worker && go mod download
	@echo "Installing Python dependencies..."
	cd orchestrator && pip install -r requirements.txt
	@echo "Installing Frontend dependencies..."
	cd frontend && npm install
	@echo "$(GREEN)Setup complete!$(NC)"

## migrate: Запустить миграции БД
migrate:
	@echo "$(BLUE)Running database migrations...$(NC)"
	docker-compose exec orchestrator python manage.py migrate

## shell-orchestrator: Открыть shell в Orchestrator
shell-orchestrator:
	docker-compose exec orchestrator python manage.py shell

## shell-db: Открыть psql в PostgreSQL
shell-db:
	docker-compose exec postgres psql -U commandcenter -d commandcenter

## deploy-staging: Деплой на staging
deploy-staging:
	@echo "$(BLUE)Deploying to staging...$(NC)"
	kubectl apply -f infrastructure/k8s/ --namespace=staging

## deploy-prod: Деплой на production
deploy-prod:
	@echo "$(YELLOW)Deploying to production...$(NC)"
	@echo "$(YELLOW)Are you sure? [y/N]$(NC)" && read ans && [ $${ans:-N} = y ]
	kubectl apply -f infrastructure/k8s/ --namespace=production

## format: Форматировать код во всех компонентах
format: format-go format-python format-frontend

## format-go: Форматировать Go код
format-go:
	@echo "$(BLUE)Formatting Go code...$(NC)"
	cd go-services/api-gateway && gofmt -s -w .
	cd go-services/worker && gofmt -s -w .

## format-python: Форматировать Python код
format-python:
	@echo "$(BLUE)Formatting Python code...$(NC)"
	cd orchestrator && black .
	cd orchestrator && isort .

## format-frontend: Форматировать Frontend код
format-frontend:
	@echo "$(BLUE)Formatting Frontend code...$(NC)"
	cd frontend && npm run format

## docs: Сгенерировать документацию
docs:
	@echo "$(BLUE)Generating documentation...$(NC)"
	cd orchestrator && python manage.py spectacular --file docs/api/openapi.yaml
	@echo "$(GREEN)Documentation generated at docs/api/openapi.yaml$(NC)"

## ps: Показать статус всех сервисов
ps:
	docker-compose ps

## restart: Перезапустить все сервисы
restart: stop dev-detached

## health: Проверить здоровье всех сервисов
health:
	@echo "$(BLUE)Checking service health...$(NC)"
	@curl -f http://localhost:8080/health || echo "API Gateway: $(YELLOW)DOWN$(NC)"
	@curl -f http://localhost:8000/health || echo "Orchestrator: $(YELLOW)DOWN$(NC)"
	@curl -f http://localhost:5173 || echo "Frontend: $(YELLOW)DOWN$(NC)"

##############################################################################
# Go Services Build System
##############################################################################

# Directories
BIN_DIR := bin
GO_SERVICES_DIR := go-services

# Build metadata
GOOS ?= $(shell go env GOOS)
GOARCH ?= $(shell go env GOARCH)
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_TIME := $(shell date -u '+%Y-%m-%d_%H:%M:%S')

# Build flags for version injection
LDFLAGS := -ldflags "\
	-X main.Version=$(VERSION) \
	-X main.Commit=$(COMMIT) \
	-X main.BuildTime=$(BUILD_TIME)"


# Cluster Service uses its own version package
LDFLAGS_CLUSTER := -ldflags "\
	-X github.com/command-center-1c/cluster-service/internal/version.Version=$(VERSION) \
	-X github.com/command-center-1c/cluster-service/internal/version.Commit=$(COMMIT) \
	-X github.com/command-center-1c/cluster-service/internal/version.BuildTime=$(BUILD_TIME)"

# Platform-specific binary extension
ifeq ($(GOOS),windows)
	BIN_EXT := .exe
else
	BIN_EXT :=
endif

# Binary names
API_GATEWAY_BIN := cc1c-api-gateway$(BIN_EXT)
WORKER_BIN := cc1c-worker$(BIN_EXT)
CLUSTER_SERVICE_BIN := cc1c-cluster-service$(BIN_EXT)
BATCH_SERVICE_BIN := cc1c-batch-service$(BIN_EXT)

##############################################################################
# Build Targets
##############################################################################

.PHONY: build-go-all build-api-gateway build-worker build-cluster-service build-batch-service
.PHONY: clean-binaries build-linux build-windows

## build-go-all: Собрать все Go сервисы
build-go-all: build-api-gateway build-worker build-cluster-service build-batch-service
	@echo "$(GREEN)✓ All Go binaries built successfully$(NC)"
	@echo ""
	@echo "Binaries:"
	@ls -lh $(BIN_DIR)/cc1c-* 2>/dev/null || true

## build-api-gateway: Собрать cc1c-api-gateway
build-api-gateway:
	@echo "$(BLUE)[1/4] Building API Gateway...$(NC)"
	@mkdir -p $(BIN_DIR)
	@cd $(GO_SERVICES_DIR)/api-gateway && \
		go build $(LDFLAGS) -o ../../$(BIN_DIR)/$(API_GATEWAY_BIN) cmd/main.go
	@echo "$(GREEN)✓ $(API_GATEWAY_BIN) built$(NC)"

## build-worker: Собрать cc1c-worker
build-worker:
	@echo "$(BLUE)[2/4] Building Worker...$(NC)"
	@mkdir -p $(BIN_DIR)
	@cd $(GO_SERVICES_DIR)/worker && \
		go build $(LDFLAGS) -o ../../$(BIN_DIR)/$(WORKER_BIN) cmd/main.go
	@echo "$(GREEN)✓ $(WORKER_BIN) built$(NC)"

## build-cluster-service: Собрать cc1c-cluster-service
build-cluster-service:
	@echo "$(BLUE)[3/4] Building Cluster Service...$(NC)"
	@mkdir -p $(BIN_DIR)
	@cd $(GO_SERVICES_DIR)/cluster-service && \
		go build $(LDFLAGS_CLUSTER) -o ../../$(BIN_DIR)/$(CLUSTER_SERVICE_BIN) cmd/main.go
	@echo "$(GREEN)✓ $(CLUSTER_SERVICE_BIN) built$(NC)"

## build-batch-service: Собрать cc1c-batch-service
build-batch-service:
	@echo "$(BLUE)[4/4] Building Batch Service...$(NC)"
	@mkdir -p $(BIN_DIR)
	@cd $(GO_SERVICES_DIR)/batch-service && \
		go build $(LDFLAGS) -o ../../$(BIN_DIR)/$(BATCH_SERVICE_BIN) cmd/main.go
	@echo "$(GREEN)✓ $(BATCH_SERVICE_BIN) built$(NC)"

## clean-binaries: Удалить все собранные бинарники
clean-binaries:
	@echo "$(YELLOW)Cleaning binaries...$(NC)"
	@rm -rf $(BIN_DIR)
	@echo "$(GREEN)✓ Binaries cleaned$(NC)"

## build-linux: Cross-compile для Linux (amd64)
build-linux:
	@echo "$(BLUE)Building for Linux (amd64)...$(NC)"
	@GOOS=linux GOARCH=amd64 $(MAKE) build-go-all

## build-windows: Cross-compile для Windows (amd64)
build-windows:
	@echo "$(BLUE)Building for Windows (amd64)...$(NC)"
	@GOOS=windows GOARCH=amd64 $(MAKE) build-go-all

##############################################################################
# End of Go Services Build System
##############################################################################
