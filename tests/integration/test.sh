#!/bin/bash
# Integration Tests Runner (вместо Makefile для Windows)

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function show_help() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Integration Tests Runner - CommandCenter1C"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "SETUP:"
    echo "  ./test.sh setup         - Start test environment (Redis + PostgreSQL)"
    echo "  ./test.sh cleanup       - Stop test environment"
    echo "  ./test.sh clean         - Stop and remove volumes (clean slate)"
    echo "  ./test.sh status        - Show test environment status"
    echo ""
    echo "BASIC TESTS (Event Flow):"
    echo "  ./test.sh test-basic    - Run basic event flow tests (4 tests)"
    echo "  ./test.sh test-single   - Run single test (e.g., TestEventFlow_PublishSubscribe)"
    echo ""
    echo "WORKER STATE MACHINE TESTS:"
    echo "  ./test.sh test-worker   - Run Worker State Machine tests (Happy Path)"
    echo "  ./test.sh test-worker-v - Run Worker SM tests with verbose output"
    echo ""
    echo "ALL TESTS:"
    echo "  ./test.sh test-all      - Run ALL integration tests (basic + worker)"
    echo "  ./test.sh all           - Setup + Test All + Cleanup (full cycle)"
    echo ""
    echo "UTILITIES:"
    echo "  ./test.sh logs          - Show test environment logs"
    echo "  ./test.sh redis-cli     - Connect to test Redis CLI"
    echo "  ./test.sh psql          - Connect to test PostgreSQL"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Examples:"
    echo "  ./test.sh setup                                    # Start environment"
    echo "  ./test.sh test-all                                 # Run all tests"
    echo "  ./test.sh test-worker                              # Worker SM only"
    echo "  ./test.sh test-single TestEventFlow_PublishSubscribe"
    echo "  ./test.sh all                                      # Full cycle"
    echo ""
}

function setup() {
    echo -e "${YELLOW}Starting test environment (Redis + PostgreSQL)...${NC}"
    docker-compose -f docker-compose.test.yml up -d

    echo "Waiting for services to be healthy..."
    sleep 3

    docker-compose -f docker-compose.test.yml ps

    echo ""
    echo -e "${GREEN}✅ Test environment ready!${NC}"
    echo "   Redis:      localhost:6380"
    echo "   PostgreSQL: localhost:5433"
}

function run_tests_basic() {
    echo -e "${YELLOW}━━━ Running Basic Event Flow Tests ━━━${NC}"
    echo "Location: tests/integration/"
    echo ""
    go test -v ./... -timeout 30s
    local exit_code=$?
    echo ""
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Basic tests completed successfully${NC}"
    else
        echo -e "${RED}❌ Basic tests failed${NC}"
        return $exit_code
    fi
}

function run_tests_worker() {
    echo -e "${YELLOW}━━━ Running Worker State Machine Tests ━━━${NC}"
    echo "Location: go-services/worker/test/integration/"
    echo ""

    cd ../../go-services/worker
    go test ./test/integration/statemachine/... -v -timeout 30s
    local exit_code=$?
    cd - > /dev/null

    echo ""
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Worker SM tests completed successfully${NC}"
    else
        echo -e "${RED}❌ Worker SM tests failed${NC}"
        return $exit_code
    fi
}

function run_tests_worker_verbose() {
    echo -e "${YELLOW}━━━ Running Worker State Machine Tests (Verbose) ━━━${NC}"
    echo "Location: go-services/worker/test/integration/"
    echo ""

    cd ../../go-services/worker
    go test ./test/integration/statemachine/... -v -timeout 30s 2>&1 | tee ../../tests/integration/worker-test-results.log
    local exit_code=$?
    cd - > /dev/null

    echo ""
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Worker SM tests completed, log saved to worker-test-results.log${NC}"
    else
        echo -e "${RED}❌ Worker SM tests failed, check worker-test-results.log${NC}"
        return $exit_code
    fi
}

function run_tests_all() {
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Running ALL Integration Tests${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    local basic_passed=0
    local worker_passed=0

    # Run basic tests
    run_tests_basic
    if [ $? -eq 0 ]; then
        basic_passed=1
    fi

    echo ""
    echo ""

    # Run worker tests
    run_tests_worker
    if [ $? -eq 0 ]; then
        worker_passed=1
    fi

    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "SUMMARY:"
    echo ""

    if [ $basic_passed -eq 1 ]; then
        echo -e "  Basic Event Flow Tests:   ${GREEN}✅ PASS${NC}"
    else
        echo -e "  Basic Event Flow Tests:   ${RED}❌ FAIL${NC}"
    fi

    if [ $worker_passed -eq 1 ]; then
        echo -e "  Worker SM Tests:          ${GREEN}✅ PASS${NC}"
    else
        echo -e "  Worker SM Tests:          ${RED}❌ FAIL${NC}"
    fi

    echo ""

    if [ $basic_passed -eq 1 ] && [ $worker_passed -eq 1 ]; then
        echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}❌ SOME TESTS FAILED${NC}"
        echo ""
        return 1
    fi
}

function run_single_test() {
    if [ -z "$1" ]; then
        echo -e "${RED}Error: TEST name not provided${NC}"
        echo "Usage: ./test.sh test-single TestLockWorkflow_EndToEnd"
        exit 1
    fi

    echo -e "${YELLOW}Running single test: $1${NC}"
    go test -v -run "$1"
}

function cleanup() {
    echo -e "${YELLOW}Stopping test environment...${NC}"
    docker-compose -f docker-compose.test.yml down
    echo -e "${GREEN}✅ Test environment stopped${NC}"
}

function clean() {
    echo -e "${YELLOW}Cleaning test environment (removing volumes)...${NC}"
    docker-compose -f docker-compose.test.yml down -v
    echo -e "${GREEN}✅ Test environment cleaned${NC}"
}

function run_all() {
    setup
    echo ""
    echo ""
    run_tests_all
    local test_result=$?
    echo ""
    cleanup
    echo ""

    if [ $test_result -eq 0 ]; then
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}✅ FULL TEST CYCLE COMPLETED SUCCESSFULLY!${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    else
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${RED}❌ Some tests failed, check output above${NC}"
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    fi

    return $test_result
}

function show_status() {
    echo -e "${YELLOW}Test environment status:${NC}"
    docker-compose -f docker-compose.test.yml ps

    echo ""
    echo "Redis connection:"
    if docker exec cc1c-redis-test redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis available (localhost:6380)${NC}"
    else
        echo -e "${RED}❌ Redis not available${NC}"
        echo "   Run: ./test.sh setup"
    fi

    echo ""
    echo "PostgreSQL connection:"
    if docker exec cc1c-postgres-test pg_isready -U test > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL available (localhost:5433)${NC}"
    else
        echo -e "${RED}❌ PostgreSQL not available${NC}"
        echo "   Run: ./test.sh setup"
    fi
}

function show_logs() {
    echo -e "${YELLOW}Watching test environment logs (Ctrl+C to exit)...${NC}"
    docker-compose -f docker-compose.test.yml logs -f
}

function redis_cli() {
    echo -e "${YELLOW}Connecting to test Redis (localhost:6380)...${NC}"
    echo "Type 'exit' to quit"
    echo ""
    docker exec -it cc1c-redis-test redis-cli
}

function postgres_cli() {
    echo -e "${YELLOW}Connecting to test PostgreSQL (localhost:5433)...${NC}"
    echo "Database: commandcenter_test, User: test"
    echo "Type '\\q' to quit"
    echo ""
    docker exec -it cc1c-postgres-test psql -U test -d commandcenter_test
}

# Main command router
case "$1" in
    setup)
        setup
        ;;
    test-basic)
        run_tests_basic
        ;;
    test-worker)
        run_tests_worker
        ;;
    test-worker-v)
        run_tests_worker_verbose
        ;;
    test-all)
        run_tests_all
        ;;
    test-single)
        run_single_test "$2"
        ;;
    cleanup)
        cleanup
        ;;
    clean)
        clean
        ;;
    all)
        run_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    redis-cli)
        redis_cli
        ;;
    psql)
        postgres_cli
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
