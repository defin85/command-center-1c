#!/bin/bash
# Create Django migrations for Sprint 1.2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Creating migrations for databases app..."
cd "$PROJECT_ROOT/orchestrator"
python manage.py makemigrations databases

echo ""
echo "Creating migrations for operations app..."
python manage.py makemigrations operations

echo ""
echo "====================================================================="
echo "✅ Migrations created successfully!"
echo "====================================================================="
echo ""
echo "To apply migrations, run:"
echo "  cd orchestrator"
echo "  python manage.py migrate"
echo ""
echo "To view SQL for migrations, run:"
echo "  python manage.py sqlmigrate databases 0001"
echo "  python manage.py sqlmigrate operations 0001"
echo ""
