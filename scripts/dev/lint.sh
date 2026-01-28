#!/bin/bash

##############################################################################
# CommandCenter1C - Lint Check Script
##############################################################################
# Проверка кода на ошибки и warnings для всех компонентов
#
# Usage:
#   ./scripts/dev/lint.sh              # Проверить всё
#   ./scripts/dev/lint.sh --fix        # Авто-исправление (где возможно)
#   ./scripts/dev/lint.sh --python     # Только Python
#   ./scripts/dev/lint.sh --go         # Только Go
#   ./scripts/dev/lint.sh --ts         # Только TypeScript
##############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Flags
FIX_MODE=false
CHECK_PYTHON=true
CHECK_GO=true
CHECK_TS=true
CHECK_BROWSER=false

# Counters
ERRORS=0
WARNINGS=0

##############################################################################
# Parse arguments
##############################################################################
while [[ $# -gt 0 ]]; do
    case $1 in
        --fix)
            FIX_MODE=true
            shift
            ;;
        --python)
            CHECK_GO=false
            CHECK_TS=false
            shift
            ;;
        --go)
            CHECK_PYTHON=false
            CHECK_TS=false
            shift
            ;;
        --ts|--typescript)
            CHECK_PYTHON=false
            CHECK_GO=false
            shift
            ;;
        --browser)
            CHECK_BROWSER=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --fix        Auto-fix errors where possible"
            echo "  --python     Check only Python code"
            echo "  --go         Check only Go code"
            echo "  --ts         Check only TypeScript code"
            echo "  --browser    Check browser form field ids (requires Playwright)"
            echo "  --help       Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

##############################################################################
# Helper functions
##############################################################################
print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

print_result() {
    local name=$1
    local status=$2
    local details=$3

    if [[ "$status" == "OK" ]]; then
        echo -e "${GREEN}✓${NC} $name: ${GREEN}$status${NC}"
    elif [[ "$status" == "WARNINGS" ]]; then
        echo -e "${YELLOW}⚠${NC} $name: ${YELLOW}$status${NC} $details"
        ((++WARNINGS))
    else
        echo -e "${RED}✗${NC} $name: ${RED}$status${NC} $details"
        ((++ERRORS))
    fi
}

##############################################################################
# TypeScript Check (tsc + ESLint)
##############################################################################
check_typescript() {
    print_header "TypeScript Check"

    cd "$PROJECT_ROOT/frontend"

    if ! command -v npx &> /dev/null; then
        print_result "TypeScript" "SKIPPED" "(npx not found)"
        return
    fi

    # 1. TypeScript compiler check
    echo "Running: npx tsc --noEmit"
    if output=$(npx tsc --noEmit 2>&1); then
        print_result "TypeScript (tsc)" "OK"
    else
        echo "$output"
        print_result "TypeScript (tsc)" "ERRORS" "(see above)"
    fi

    # 2. ESLint check
    echo ""
    local eslint_args="src/"
    if [[ "$FIX_MODE" == true ]]; then
        eslint_args="src/ --fix"
        echo "Running: npx eslint $eslint_args"
    else
        echo "Running: npx eslint src/ (use --fix to auto-fix)"
    fi

    if output=$(npx eslint $eslint_args 2>&1); then
        print_result "ESLint" "OK"
    else
        # Count errors vs warnings
        error_count=$(echo "$output" | grep -c " error " || true)
        warning_count=$(echo "$output" | grep -c " warning " || true)

        if [[ "$error_count" -gt 0 ]]; then
            echo "$output" | head -30
            [[ $(echo "$output" | wc -l) -gt 30 ]] && echo "... (truncated)"
            print_result "ESLint" "ERRORS" "($error_count errors, $warning_count warnings)"
        else
            echo "$output" | head -20
            [[ $(echo "$output" | wc -l) -gt 20 ]] && echo "... (truncated)"
            echo -e "${YELLOW}⚠${NC} ESLint: ${YELLOW}WARNINGS${NC} ($warning_count warnings)"
            # Don't increment ERRORS for warnings-only
        fi
    fi

    cd "$PROJECT_ROOT"
}

##############################################################################
# Python Check (ruff)
##############################################################################
check_python() {
    print_header "Python Check (ruff)"

    cd "$PROJECT_ROOT/orchestrator"

    if [[ ! -f "venv/Scripts/activate" ]] && [[ ! -f "venv/bin/activate" ]]; then
        print_result "Python" "SKIPPED" "(venv not found)"
        return
    fi

    source venv/Scripts/activate 2>/dev/null || source venv/bin/activate 2>/dev/null

    if ! command -v ruff &> /dev/null; then
        print_result "Python" "SKIPPED" "(ruff not installed)"
        return
    fi

    local ruff_args="check ."
    if [[ "$FIX_MODE" == true ]]; then
        ruff_args="check . --fix"
        echo "Running: ruff $ruff_args"
    else
        echo "Running: ruff check . (use --fix to auto-fix)"
    fi

    if output=$(ruff $ruff_args 2>&1); then
        print_result "Python (ruff)" "OK"
    else
        # Critical errors: F821 (undefined name), F811 (redefinition), E999 (syntax)
        critical=$(echo "$output" | grep -E "^(F821|F811|E999)" || true)
        critical_count=$(echo "$critical" | grep -c "^[A-Z]" || true)

        # All issues count
        total_count=$(echo "$output" | grep -c "Found [0-9]* error" || echo "0")
        total_count=$(echo "$output" | grep -oP "Found \K[0-9]+" || echo "0")

        if [[ -n "$critical" ]] && [[ "$critical_count" -gt 0 ]]; then
            echo -e "${RED}Critical errors:${NC}"
            echo "$critical"
            print_result "Python (ruff)" "ERRORS" "($critical_count critical, $total_count total)"
        else
            # Only non-critical warnings (F841 unused, E402 imports, etc.)
            echo "$output" | head -10
            echo "..."
            echo -e "${YELLOW}⚠${NC} Python (ruff): ${YELLOW}WARNINGS${NC} ($total_count non-critical issues, run --fix to clean up)"
            # Don't increment ERRORS for non-critical issues
        fi
    fi

    cd "$PROJECT_ROOT"
}

##############################################################################
# JSON Validation (Grafana dashboards)
##############################################################################
validate_json() {
    print_header "JSON Validation"

    local dashboard_dir="$PROJECT_ROOT/infrastructure/monitoring/grafana/dashboards"

    if [[ ! -d "$dashboard_dir" ]]; then
        print_result "JSON Validation" "SKIPPED" "(dashboards dir not found)"
        return 0
    fi

    local errors=0
    local count=0

    for f in "$dashboard_dir"/*.json; do
        if [[ -f "$f" ]]; then
            ((++count))
            if ! python3 -m json.tool "$f" > /dev/null 2>&1; then
                echo -e "  ${RED}✗${NC} Invalid JSON: $(basename "$f")"
                ((++errors))
            fi
        fi
    done

    if [[ $count -eq 0 ]]; then
        print_result "JSON Validation" "SKIPPED" "(no JSON files found)"
        return 0
    fi

    if [[ $errors -eq 0 ]]; then
        print_result "JSON Validation" "OK" "($count files checked)"
    else
        print_result "JSON Validation" "ERRORS" "($errors/$count files invalid)"
    fi

    return $errors
}

##############################################################################
# Prometheus Rules Validation
##############################################################################
validate_prometheus_rules() {
    print_header "Prometheus Rules Validation"

    if ! command -v promtool &> /dev/null; then
        echo -e "  ${YELLOW}⚠${NC} promtool not found, skipping validation"
        echo -e "  Install: ${YELLOW}sudo pacman -S prometheus${NC}"
        return 0
    fi

    local rules_dir="$PROJECT_ROOT/infrastructure/monitoring/prometheus"
    local errors=0
    local count=0

    # Check recording rules
    if [[ -f "$rules_dir/recording_rules.yml" ]]; then
        ((++count))
        if ! promtool check rules "$rules_dir/recording_rules.yml" 2>/dev/null; then
            echo -e "  ${RED}✗${NC} Invalid: recording_rules.yml"
            ((++errors))
        fi
    fi

    # Check alert rules
    if [[ -d "$rules_dir/alerts" ]]; then
        for f in "$rules_dir/alerts"/*.yml; do
            if [[ -f "$f" ]]; then
                ((++count))
                if ! promtool check rules "$f" 2>/dev/null; then
                    echo -e "  ${RED}✗${NC} Invalid: $(basename "$f")"
                    ((++errors))
                fi
            fi
        done
    fi

    if [[ $count -eq 0 ]]; then
        print_result "Prometheus Rules" "SKIPPED" "(no rule files found)"
        return 0
    fi

    if [[ $errors -eq 0 ]]; then
        print_result "Prometheus Rules" "OK" "($count files checked)"
    else
        print_result "Prometheus Rules" "ERRORS" "($errors/$count files invalid)"
    fi

    return $errors
}

##############################################################################
# Go Check (go vet)
##############################################################################
check_go() {
    print_header "Go Check (go vet + golangci-lint)"

    if ! command -v go &> /dev/null; then
        print_result "Go" "SKIPPED" "(go not found)"
        return
    fi

    local go_services=("api-gateway" "worker")
    local all_ok=true

    for service in "${go_services[@]}"; do
        local service_dir="$PROJECT_ROOT/go-services/$service"
        if [[ -d "$service_dir" ]]; then
            cd "$service_dir"
            echo "Checking: $service"
            if output=$(go vet ./... 2>&1); then
                echo -e "  ${GREEN}✓${NC} $service: OK"
            else
                echo "$output"
                echo -e "  ${RED}✗${NC} $service: ERRORS"
                all_ok=false
            fi
        fi
    done

    if [[ "$all_ok" == true ]]; then
        print_result "Go (vet)" "OK"
    else
        print_result "Go (vet)" "ERRORS"
    fi

    # golangci-lint (optional, but preferred when available)
    echo ""
    local lint_ok=true
    local lint_runner="$PROJECT_ROOT/scripts/dev/golangci-lint.sh"
    if [[ -x "$lint_runner" ]]; then
        for service in "${go_services[@]}"; do
            local service_dir="$PROJECT_ROOT/go-services/$service"
            if [[ -d "$service_dir" ]]; then
                cd "$service_dir"
                echo "Linting: $service"
                if output=$("$lint_runner" run 2>&1); then
                    echo -e "  ${GREEN}✓${NC} $service: OK"
                else
                    echo "$output"
                    echo -e "  ${RED}✗${NC} $service: ERRORS"
                    lint_ok=false
                fi
            fi
        done

        if [[ "$lint_ok" == true ]]; then
            print_result "Go (golangci-lint)" "OK"
        else
            print_result "Go (golangci-lint)" "ERRORS"
        fi
    else
        print_result "Go (golangci-lint)" "SKIPPED" "(runner script not found)"
    fi

    cd "$PROJECT_ROOT"
}

##############################################################################
# Browser Checks (Playwright)
##############################################################################
check_browser_forms() {
    print_header "Browser Form Field Checks"

    cd "$PROJECT_ROOT/frontend"

    if ! command -v npx &> /dev/null; then
        print_result "Browser forms" "SKIPPED" "(npx not found)"
        cd "$PROJECT_ROOT"
        return
    fi

    if [[ ! -d "node_modules/@playwright/test" ]]; then
        print_result "Browser forms" "SKIPPED" "(@playwright/test not installed)"
        cd "$PROJECT_ROOT"
        return
    fi

    echo "Running: npx playwright test tests/browser/form-field-ids.spec.ts"
    if output=$(npx playwright test tests/browser/form-field-ids.spec.ts 2>&1); then
        print_result "Browser forms" "OK"
    else
        echo "$output"
        print_result "Browser forms" "ERRORS" "(see above)"
    fi

    cd "$PROJECT_ROOT"
}

##############################################################################
# Main
##############################################################################
main() {
    echo -e "${BLUE}CommandCenter1C - Lint Check${NC}"
    echo -e "Project: $PROJECT_ROOT"
    echo -e "Fix mode: $FIX_MODE"

    [[ "$CHECK_TS" == true ]] && check_typescript
    [[ "$CHECK_PYTHON" == true ]] && check_python
    [[ "$CHECK_GO" == true ]] && check_go
    [[ "$CHECK_BROWSER" == true ]] && check_browser_forms

    # Additional validations (always run)
    validate_json
    validate_prometheus_rules

    print_header "Summary"

    if [[ $ERRORS -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
        echo -e "${GREEN}All checks passed!${NC}"
        exit 0
    elif [[ $ERRORS -eq 0 ]]; then
        echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
        echo -e "${GREEN}No critical errors.${NC}"
        exit 0
    else
        echo -e "${RED}Errors: $ERRORS${NC}"
        echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
        echo ""
        echo -e "Run ${YELLOW}./scripts/dev/lint.sh --fix${NC} to auto-fix where possible"
        exit 1
    fi
}

main
