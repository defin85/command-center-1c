# Makefile для Integration Tests

.PHONY: help setup test test-verbose test-single cleanup down clean all

# Default target
help:
	@echo "Integration Tests - Available Commands:"
	@echo ""
	@echo "  make setup         - Start test environment (Redis + PostgreSQL)"
	@echo "  make test          - Run all integration tests"
	@echo "  make test-verbose  - Run tests with verbose output"
	@echo "  make test-single   - Run single test (specify TEST=TestName)"
	@echo "  make cleanup       - Stop test environment"
	@echo "  make clean         - Stop and remove volumes (clean slate)"
	@echo "  make all           - Setup + Test + Cleanup (full cycle)"
	@echo ""
	@echo "Examples:"
	@echo "  make setup"
	@echo "  make test"
	@echo "  make test-single TEST=TestLockWorkflow_EndToEnd"
	@echo "  make cleanup"

# Start test environment
setup:
	@echo "Starting test environment (Redis + PostgreSQL)..."
	docker-compose -f docker-compose.test.yml up -d
	@echo "Waiting for services to be healthy..."
	@sleep 3
	@docker-compose -f docker-compose.test.yml ps
	@echo ""
	@echo "✅ Test environment ready!"
	@echo "   Redis:      localhost:6380"
	@echo "   PostgreSQL: localhost:5433"

# Run all integration tests
test: setup
	@echo "Running integration tests..."
	go test -v ./...
	@echo ""
	@echo "✅ Tests completed"

# Run tests with verbose output + save log
test-verbose: setup
	@echo "Running integration tests (verbose)..."
	go test -v ./... 2>&1 | tee test-results.log
	@echo ""
	@echo "✅ Test results saved to test-results.log"

# Run single test
test-single: setup
ifndef TEST
	$(error TEST is not set. Usage: make test-single TEST=TestLockWorkflow_EndToEnd)
endif
	@echo "Running single test: $(TEST)"
	go test -v -run $(TEST)

# Stop test environment (keep volumes)
cleanup:
	@echo "Stopping test environment..."
	docker-compose -f docker-compose.test.yml down
	@echo "✅ Test environment stopped"

# Stop and remove volumes (clean slate)
clean:
	@echo "Cleaning test environment (removing volumes)..."
	docker-compose -f docker-compose.test.yml down -v
	@echo "✅ Test environment cleaned"

# Full cycle: setup + test + cleanup
all: setup test cleanup
	@echo ""
	@echo "✅ Full test cycle completed successfully!"

# Quick test (assumes environment already running)
quick:
	@echo "Running quick test (assuming environment is running)..."
	go test -v ./...

# Debug: show test environment status
status:
	@echo "Test environment status:"
	@docker-compose -f docker-compose.test.yml ps
	@echo ""
	@echo "Redis connection:"
	@docker exec cc1c-redis-test redis-cli ping || echo "❌ Redis not available"
	@echo ""
	@echo "PostgreSQL connection:"
	@docker exec cc1c-postgres-test pg_isready -U test || echo "❌ PostgreSQL not available"

# Watch logs
logs:
	@echo "Watching test environment logs (Ctrl+C to exit)..."
	docker-compose -f docker-compose.test.yml logs -f

# Redis CLI (для debugging)
redis-cli:
	@echo "Connecting to test Redis..."
	docker exec -it cc1c-redis-test redis-cli

# PostgreSQL CLI (для debugging)
psql:
	@echo "Connecting to test PostgreSQL..."
	docker exec -it cc1c-postgres-test psql -U test -d commandcenter_test
