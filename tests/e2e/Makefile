.PHONY: help setup teardown test test-verbose test-short health clean

# Default target
help:
	@echo "E2E Tests Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  setup          - Start Docker Compose E2E environment"
	@echo "  teardown       - Stop Docker Compose E2E environment"
	@echo "  test           - Run all E2E tests"
	@echo "  test-verbose   - Run E2E tests with verbose output"
	@echo "  test-short     - Skip E2E tests (short mode)"
	@echo "  test-happy     - Run only Happy Path test"
	@echo "  test-lock      - Run only Lock Failure test"
	@echo "  test-compensate - Run only Compensation test"
	@echo "  test-concurrent - Run only Concurrent test"
	@echo "  health         - Check health of all E2E services"
	@echo "  clean          - Clean up everything (teardown + prune)"
	@echo ""

# Start Docker Compose E2E environment
setup:
	@echo "Starting E2E environment..."
	docker-compose -f docker-compose.e2e.yml up -d
	@echo "Waiting for services to be ready..."
	sleep 5
	@echo "E2E environment started"

# Stop Docker Compose E2E environment
teardown:
	@echo "Stopping E2E environment..."
	docker-compose -f docker-compose.e2e.yml down -v
	@echo "E2E environment stopped"

# Run all E2E tests
test: setup
	@echo "Running E2E tests..."
	go test -v ./... -timeout 300s
	@$(MAKE) teardown

# Run E2E tests with verbose output
test-verbose: setup
	@echo "Running E2E tests (verbose)..."
	go test -v ./... -timeout 300s -count=1
	@$(MAKE) teardown

# Skip E2E tests (short mode)
test-short:
	@echo "Running tests in short mode (E2E skipped)..."
	go test -v -short ./...

# Run only Happy Path test
test-happy: setup
	@echo "Running Happy Path E2E test..."
	go test -v -run TestE2E_ExtensionInstall_HappyPath -timeout 120s
	@$(MAKE) teardown

# Run only Lock Failure test
test-lock: setup
	@echo "Running Lock Failure E2E test..."
	go test -v -run TestE2E_ExtensionInstall_LockFailure -timeout 60s
	@$(MAKE) teardown

# Run only Install Failure + Compensation test
test-compensate: setup
	@echo "Running Install Failure + Compensation E2E test..."
	go test -v -run TestE2E_ExtensionInstall_InstallFailureWithCompensation -timeout 120s
	@$(MAKE) teardown

# Run only Concurrent operations test
test-concurrent: setup
	@echo "Running Concurrent Operations E2E test..."
	go test -v -run TestE2E_MultipleOperations_Concurrent -timeout 180s
	@$(MAKE) teardown

# Check health of all E2E services
health:
	@echo "Checking E2E services health..."
	@echo ""
	@echo "Redis E2E (6380):"
	@curl -s http://localhost:6380/ || echo "NOT READY"
	@echo ""
	@echo "PostgreSQL E2E (5433):"
	@docker exec -it cc1c-postgres-e2e pg_isready || echo "NOT READY"
	@echo ""
	@echo "Mock RAS (8082):"
	@curl -s http://localhost:8082/health | jq . || echo "NOT READY"
	@echo ""

# Clean up everything
clean: teardown
	@echo "Cleaning up Docker resources..."
	docker system prune -f
	@echo "Cleanup complete"
