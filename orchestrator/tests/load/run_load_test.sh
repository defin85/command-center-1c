#!/bin/bash
# Run Locust load tests for Workflow Engine
#
# Usage:
#   ./run_load_test.sh              # Interactive mode (Web UI)
#   ./run_load_test.sh light        # Light load (10 users)
#   ./run_load_test.sh medium       # Medium load (50 users)
#   ./run_load_test.sh heavy        # Heavy load (100 users)
#   ./run_load_test.sh burst        # Burst test (concurrent executions)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATOR_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
HOST="${LOCUST_HOST:-http://localhost:8000}"
RESULTS_DIR="${ORCHESTRATOR_DIR}/tests/load/results"

# Ensure results directory exists
mkdir -p "$RESULTS_DIR"

# Change to orchestrator directory
cd "$ORCHESTRATOR_DIR"

# Activate virtual environment if exists
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Check locust is installed
if ! command -v locust &> /dev/null; then
    echo "Locust not installed. Installing..."
    pip install locust
fi

# Create test user if not exists
echo "Ensuring test user exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='loadtest').exists():
    User.objects.create_user('loadtest', 'loadtest@test.com', 'loadtest123', is_staff=True)
    print('Test user created: loadtest')
else:
    print('Test user already exists')
" 2>/dev/null || echo "Note: Could not create test user (maybe DB not available)"

# Parse profile
PROFILE="${1:-interactive}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

case "$PROFILE" in
    light)
        echo "Running LIGHT load test (10 users, 2/s spawn, 1 minute)..."
        locust -f tests/load/workflow_load_test.py --host="$HOST" \
            --headless -u 10 -r 2 -t 1m \
            --csv="$RESULTS_DIR/light_${TIMESTAMP}" \
            --html="$RESULTS_DIR/light_${TIMESTAMP}.html"
        ;;
    medium)
        echo "Running MEDIUM load test (50 users, 5/s spawn, 2 minutes)..."
        locust -f tests/load/workflow_load_test.py --host="$HOST" \
            --headless -u 50 -r 5 -t 2m \
            --csv="$RESULTS_DIR/medium_${TIMESTAMP}" \
            --html="$RESULTS_DIR/medium_${TIMESTAMP}.html"
        ;;
    heavy)
        echo "Running HEAVY load test (100 users, 10/s spawn, 5 minutes)..."
        locust -f tests/load/workflow_load_test.py --host="$HOST" \
            --headless -u 100 -r 10 -t 5m \
            --csv="$RESULTS_DIR/heavy_${TIMESTAMP}" \
            --html="$RESULTS_DIR/heavy_${TIMESTAMP}.html"
        ;;
    burst)
        echo "Running BURST test (concurrent execution focus)..."
        locust -f tests/load/workflow_load_test.py --host="$HOST" \
            --headless -u 20 -r 5 -t 1m \
            --csv="$RESULTS_DIR/burst_${TIMESTAMP}" \
            --html="$RESULTS_DIR/burst_${TIMESTAMP}.html" \
            --tags concurrent
        ;;
    interactive|*)
        echo "Starting Locust Web UI at http://localhost:8089"
        echo "Target host: $HOST"
        echo ""
        echo "Press Ctrl+C to stop"
        locust -f tests/load/workflow_load_test.py --host="$HOST"
        ;;
esac

echo ""
echo "Results saved to: $RESULTS_DIR/"
