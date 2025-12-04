# Templates App Tests

Comprehensive test suite for the Templates application, including WorkflowTemplate and OperationTemplate models.

## Quick Start

### Run All Tests
```bash
cd orchestrator
source venv/bin/activate
python -m pytest apps/templates/tests/ -v
```

### Run Admin Tests Only
```bash
python -m pytest apps/templates/tests/test_admin.py -v
```

### Run with Coverage Report
```bash
python -m pytest apps/templates/tests/test_admin.py --cov=apps.templates.admin --cov-report=term-missing
```

---

## Test Files

### test_admin.py
Operation Templates Reference Panel in Django Admin

**Class:** `TestWorkflowTemplateAdminOperationTemplatesContext`

**Tests:** 15

**Coverage:** 100% of admin view methods

**Key Tests:**
- Context injection in changeform_view and add_view
- Filtering of active templates only
- Sorting by operation_type and name
- Performance with large datasets
- Edge cases (empty, special characters, etc.)

### Other Test Files
- `test_validator.py` - DAG validation tests
- `test_renderer.py` - Template rendering tests
- `test_compiler.py` - Template compilation tests
- `test_tasks.py` - Celery task tests
- `test_views.py` - API endpoint tests
- `test_integration_e2e.py` - End-to-end integration tests

---

## Test Statistics

| Test File | Test Count | Coverage | Status |
|-----------|-----------|----------|--------|
| test_admin.py | 15 | 100% | ✓ Passing |
| test_validator.py | N/A | N/A | - |
| test_renderer.py | N/A | N/A | - |
| test_compiler.py | N/A | N/A | - |
| test_tasks.py | N/A | N/A | - |
| test_views.py | N/A | N/A | - |

---

## Fixtures

Located in `conftest.py`:

- **admin_user** - Superuser for admin tests
- **simple_workflow_template** - Basic sequential workflow
- **workflow_execution** - Workflow execution instance

---

## Development

### Adding New Tests

1. Add test method to test class with `test_` prefix
2. Use `@pytest.mark.django_db` for database access
3. Follow AAA pattern: Arrange, Act, Assert
4. Use meaningful test names describing the scenario

Example:
```python
def test_new_feature(self):
    """Test description of what is being tested."""
    # Arrange
    tpl = OperationTemplate.objects.create(...)

    # Act
    response = self.workflow_admin.changeform_view(request, object_id)

    # Assert
    assert 'operation_templates' in response.context_data
```

### Running During Development

```bash
# Run tests in watch mode (requires pytest-watch)
ptw apps/templates/tests/test_admin.py

# Run with verbose output
pytest apps/templates/tests/test_admin.py -vv

# Run with pdb on failure
pytest apps/templates/tests/test_admin.py --pdb

# Run specific test class
pytest apps/templates/tests/test_admin.py::TestWorkflowTemplateAdminOperationTemplatesContext -v
```

---

## Dependencies

- Django 4.2.25+
- pytest 7.4.3+
- pytest-django 4.7.0+
- pytest-cov 4.1.0+

Install with:
```bash
pip install -r requirements.txt
```

---

## CI/CD Integration

### GitHub Actions / GitLab CI

```yaml
- name: Run Templates Tests
  run: |
    cd orchestrator
    source venv/bin/activate
    python -m pytest apps/templates/tests/ -v --tb=short
```

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:
```yaml
- repo: local
  hooks:
    - id: pytest-templates
      name: pytest templates
      entry: pytest apps/templates/tests/ -v
      language: system
      pass_filenames: false
```

---

## Troubleshooting

### Database Errors
```
django.db.utils.ProgrammingError: relation does not exist
```
**Solution:** Run migrations first
```bash
python manage.py migrate
```

### Import Errors
```
ModuleNotFoundError: No module named 'apps.templates'
```
**Solution:** Ensure you're in the `orchestrator` directory
```bash
cd orchestrator
```

### Fixture Not Found
```
fixture 'admin_user' not found
```
**Solution:** Check `conftest.py` is in tests directory and properly imported

---

## Performance Benchmarks

Current test execution times:

- Full suite (test_admin.py): ~2.5 seconds
- Single test: ~0.2 seconds
- With coverage: +0.7 seconds

---

## Documentation

- **TEST_ADMIN_DOCUMENTATION.md** - Detailed test documentation
- **conftest.py** - Shared fixtures and configuration
- **test_admin.py** - Test implementation

---

## Support

For issues or questions:
1. Check test documentation in TEST_ADMIN_DOCUMENTATION.md
2. Review test code in test_admin.py
3. Check Django admin documentation: https://docs.djangoproject.com/en/4.2/ref/contrib/admin/

---

**Status:** Production Ready ✓
**Last Updated:** 2025-12-04
