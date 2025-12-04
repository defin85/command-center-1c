# Test Integration Guide

**Operation Templates Reference Panel Tests**

---

## Overview

This guide explains how to integrate the new admin tests into your development workflow and CI/CD pipeline.

---

## For Development

### Running Tests Locally

1. **Navigate to project directory:**
   ```bash
   cd /home/egor/code/command-center-1c/orchestrator
   ```

2. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

3. **Run all admin tests:**
   ```bash
   python -m pytest apps/templates/tests/test_admin.py -v
   ```

4. **Run specific test:**
   ```bash
   python -m pytest apps/templates/tests/test_admin.py::TestWorkflowTemplateAdminOperationTemplatesContext::test_changeform_view_includes_operation_templates -v
   ```

5. **Run with coverage:**
   ```bash
   python -m pytest apps/templates/tests/test_admin.py --cov=apps.templates.admin --cov-report=term-missing
   ```

### Development Best Practices

1. **Run before commit:**
   ```bash
   python -m pytest apps/templates/tests/test_admin.py -v
   ```

2. **Run full test suite before push:**
   ```bash
   python -m pytest apps/templates/tests/ -v
   ```

3. **Check coverage:**
   ```bash
   python -m pytest apps/templates/tests/test_admin.py --cov --cov-report=html
   ```

---

## For CI/CD Integration

### GitHub Actions

Add to `.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ master, develop ]
  pull_request:
    branches: [ master ]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        cd orchestrator
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Run Template Admin Tests
      run: |
        cd orchestrator
        python -m pytest apps/templates/tests/test_admin.py -v --tb=short

    - name: Generate Coverage Report
      run: |
        cd orchestrator
        python -m pytest apps/templates/tests/test_admin.py --cov=apps.templates.admin --cov-report=xml

    - name: Upload Coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./orchestrator/coverage.xml
```

### GitLab CI

Add to `.gitlab-ci.yml`:

```yaml
test:admin:
  stage: test
  image: python:3.11
  services:
    - postgres:15
  before_script:
    - cd orchestrator
    - pip install -r requirements.txt
  script:
    - pytest apps/templates/tests/test_admin.py -v --tb=short
  coverage: '/TOTAL.*\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
```

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest-admin-tests
        name: pytest admin tests
        entry: bash -c 'cd orchestrator && python -m pytest apps/templates/tests/test_admin.py -v'
        language: system
        pass_filenames: false
        stages: [commit]
        always_run: true
```

---

## Test Organization

### Directory Structure
```
orchestrator/
└── apps/templates/tests/
    ├── __init__.py
    ├── conftest.py                      # Shared fixtures
    ├── test_admin.py                    # New admin tests (15 tests)
    ├── test_validator.py                # Existing tests
    ├── test_renderer.py                 # Existing tests
    ├── test_compiler.py                 # Existing tests
    ├── test_tasks.py                    # Existing tests
    ├── test_views.py                    # Existing tests
    ├── test_integration_e2e.py          # Existing tests
    ├── TEST_ADMIN_DOCUMENTATION.md      # Documentation
    ├── TEST_SUMMARY.md                  # Summary report
    ├── README.md                        # Quick start
    └── INTEGRATION_GUIDE.md             # This file
```

### Running All Template Tests
```bash
python -m pytest apps/templates/tests/ -v
```

---

## Database Configuration

### Test Database
- Uses Django test database (test_commandcenter)
- Automatically created and destroyed per test
- Transactions rolled back after each test
- No external database required

### PostgreSQL for Local Testing (Optional)
If you want to test against real PostgreSQL:

1. Create test database:
   ```bash
   createdb test_commandcenter
   ```

2. Run migrations:
   ```bash
   python manage.py migrate
   ```

3. Run tests:
   ```bash
   python -m pytest apps/templates/tests/test_admin.py -v
   ```

---

## Troubleshooting

### Database Connection Error
```
django.db.utils.OperationalError: could not connect to server
```

**Solution:**
```bash
# Use Django test database instead
cd orchestrator
python -m pytest apps/templates/tests/test_admin.py -v
```

### Import Error
```
ModuleNotFoundError: No module named 'apps.templates'
```

**Solution:**
```bash
# Ensure you're in orchestrator directory
cd orchestrator
python -m pytest apps/templates/tests/test_admin.py -v
```

### Fixture Not Found
```
fixture 'admin_user' not found
```

**Solution:**
- Check `conftest.py` is in `apps/templates/tests/`
- Verify pytest can find it:
  ```bash
  python -m pytest --fixtures | grep admin_user
  ```

### Test Hangs
```bash
# Run with timeout
pytest apps/templates/tests/test_admin.py -v --timeout=30
```

---

## Performance Guidelines

### Expected Execution Times
- Single test: ~0.2 seconds
- All admin tests (15): ~2.5 seconds
- Full template suite: ~5-10 seconds

### Optimization Tips
1. Run tests in parallel (requires pytest-xdist):
   ```bash
   pytest apps/templates/tests/test_admin.py -n auto
   ```

2. Run only modified tests:
   ```bash
   pytest apps/templates/tests/test_admin.py --lf
   ```

3. Run failed tests first:
   ```bash
   pytest apps/templates/tests/test_admin.py --ff
   ```

---

## Monitoring & Reporting

### Coverage Report
```bash
python -m pytest apps/templates/tests/test_admin.py \
  --cov=apps.templates.admin \
  --cov-report=html \
  --cov-report=term-missing
```

### JUnit XML Report (for CI systems)
```bash
python -m pytest apps/templates/tests/test_admin.py \
  --junit-xml=test-results.xml
```

### Detailed Output
```bash
python -m pytest apps/templates/tests/test_admin.py \
  -v \
  --tb=long \
  --capture=no
```

---

## Maintenance

### When to Update Tests

1. **Model Changes:**
   - If OperationTemplate fields change
   - If WorkflowTemplate structure changes
   - If filtering/sorting logic changes

2. **Admin Changes:**
   - If admin views are modified
   - If context injection changes
   - If new methods are added

3. **Requirements Changes:**
   - If new filtering rules added
   - If new sorting requirements added
   - If new views added

### How to Update Tests

1. Add new test case:
   ```python
   def test_new_feature(self):
       """Test description."""
       # Arrange

       # Act

       # Assert
   ```

2. Update existing test:
   ```bash
   # Edit test_admin.py
   # Run tests to verify
   python -m pytest apps/templates/tests/test_admin.py -v
   ```

3. Update documentation:
   - Update TEST_ADMIN_DOCUMENTATION.md
   - Update TEST_SUMMARY.md

---

## Documentation Links

### Test Documentation
- **TEST_ADMIN_DOCUMENTATION.md** - Comprehensive test documentation
- **TEST_SUMMARY.md** - Executive summary and test results
- **README.md** - Quick start guide
- **INTEGRATION_GUIDE.md** - This file

### Project Documentation
- **admin.py** - Admin configuration
- **models.py** - Model definitions
- Django Admin Docs: https://docs.djangoproject.com/en/4.2/ref/contrib/admin/

---

## Support & Questions

### Where to Find Information

1. **Test Documentation:**
   - See TEST_ADMIN_DOCUMENTATION.md for detailed test descriptions

2. **Test Code:**
   - See test_admin.py for implementation details

3. **Quick Start:**
   - See README.md for quick start instructions

4. **Integration:**
   - See this file (INTEGRATION_GUIDE.md)

### Reporting Issues

If tests fail:
1. Run test with verbose output: `pytest -vv`
2. Check TEST_ADMIN_DOCUMENTATION.md for troubleshooting
3. Review test code in test_admin.py
4. Check Django admin documentation

---

## Appendix: Quick Reference

### Run Tests
```bash
cd orchestrator && source venv/bin/activate
python -m pytest apps/templates/tests/test_admin.py -v
```

### Run with Coverage
```bash
python -m pytest apps/templates/tests/test_admin.py --cov=apps.templates.admin --cov-report=term-missing
```

### Run Specific Test
```bash
python -m pytest apps/templates/tests/test_admin.py::TestWorkflowTemplateAdminOperationTemplatesContext::test_changeform_view_includes_operation_templates -v
```

### Run in Watch Mode
```bash
ptw apps/templates/tests/test_admin.py
```

### Debug Failed Test
```bash
pytest apps/templates/tests/test_admin.py --pdb -x
```

---

**Last Updated:** 2025-12-04
**Status:** Production Ready ✓
