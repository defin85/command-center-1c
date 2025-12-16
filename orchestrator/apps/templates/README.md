# Template Engine - Руководство

## Обзор

Template Engine для CommandCenter1C позволяет создавать гибкие шаблоны операций для 1С баз с использованием Jinja2 синтаксиса.

## Основные возможности

- ✅ Variables substitution (`{{var}}`)
- ✅ Conditional logic (`{% if %}...{% endif %}`)
- ✅ Loops (`{% for %}...{% endfor %}`)
- ✅ Custom 1С filters (`|guid1c`, `|datetime1c`, etc.)
- ✅ Custom tests (`is production_database`, `is empty`)
- ✅ Multi-layer security (validation + sandbox)
- ✅ Template caching (11.5x speedup)
- ✅ REST API (CRUD + validate + render)

## Быстрый старт

### Использование через Python API

```python
from apps.templates.engine import TemplateRenderer
from apps.templates.models import OperationTemplate

# Создать шаблон
template = OperationTemplate.objects.create(
    name='Create User',
    operation_type='create',
    target_entity='Catalog_Users',
    template_data={
        "Name": "{{user_name}}",
        "Email": "{{email}}",
        "ID": "{{user_id|guid1c}}"
    }
)

# Render
renderer = TemplateRenderer()
result = renderer.render(template, {
    "user_name": "Alice",
    "email": "alice@test.com",
    "user_id": "12345678-1234-1234-1234-123456789012"
})

# Результат:
# {
#   "Name": "Alice",
#   "Email": "alice@test.com",
#   "ID": "guid'12345678-1234-1234-1234-123456789012'"
# }
```

### Использование через REST API

```bash
# v1 CRUD endpoints удалены.
# Для операторов основной путь — SPA: /templates (sync from registry) и API v2:
#
# List templates
GET /api/v2/templates/list-templates/
#
# Sync templates from registry (staff-only)
POST /api/v2/templates/sync-from-registry/
{
  "dry_run": false
}
#
# Render/validate используются worker'ом через internal API:
# GET /api/v2/internal/get-template?template_id=...
# POST /api/v2/internal/render-template?template_id=...
```

### Использование в Worker (Go)

```python
# Celery удалён; выполнение операций делает Go Worker.
# Template render/validation выполняются через internal API (`/api/v2/internal/*`).
```

## Синтаксис шаблонов

### Variables

```jinja2
{{variable_name}}                    # Простая переменная
{{user.name}}                        # Вложенный объект
{{items[0]}}                         # Элемент списка
{{price|default(0)}}                 # С default значением
{{name|upper}}                       # С фильтром
```

### Filters (1С-специфичные)

```jinja2
{{user_id|guid1c}}                   # guid'12345678-1234-1234-1234-123456789012'
{{timestamp|datetime1c}}             # datetime'2025-11-09T15:30:00'
{{date|date1c}}                      # datetime'2025-11-09T00:00:00'
{{is_active|bool1c}}                 # true / false (lowercase)
```

**Встроенные Jinja2 фильтры также доступны:**
- `|upper`, `|lower`, `|title` - преобразование регистра
- `|default(value)` - значение по умолчанию
- `|round(precision)` - округление чисел
- `|length` - длина списка/строки
- См. [Jinja2 Built-in Filters](https://jinja.palletsprojects.com/en/3.1.x/templates/#builtin-filters)

### Conditionals

```jinja2
{% if condition %}...{% endif %}
{% if x > 10 %}...{% elif x > 5 %}...{% else %}...{% endif %}
{% if database_type == 'production' %}...{% endif %}
{% if items is empty %}No items{% endif %}
```

**Custom tests (1С-специфичные):**
```jinja2
{% if database is production_database %}...{% endif %}
{% if list is empty %}...{% endif %}
```

### Loops

```jinja2
{% for item in list %}
  {{item.name}}{% if not loop.last %}, {% endif %}
{% endfor %}

{% for key, value in dict.items() %}
  {{key}}: {{value}}
{% endfor %}
```

### Комбинированные примеры

**Динамические права доступа:**
```jinja2
{
  "Permissions": [
    "{% if is_admin %}read{% endif %}",
    "{% if is_admin or is_moderator %}write{% endif %}",
    "{% if is_admin %}admin{% endif %}"
  ]
}
```

**Условная логика для production/test:**
```jinja2
{
  "IsActive": "{% if database_type == 'production' %}{{is_active|bool1c}}{% else %}false{% endif %}"
}
```

**Автоматический расчет скидки:**
```jinja2
{
  "Discount": "{% if old_price and new_price < old_price %}{{((old_price - new_price) / old_price * 100)|round(2)}}{% else %}0{% endif %}"
}
```

## Security

Template Engine использует **ImmutableSandboxedEnvironment** для защиты от injection attacks.

**Блокируется:**
- `__class__`, `__globals__` (introspection)
- `exec()`, `eval()` (code execution)
- `import`, `__import__` (module loading)
- `open()`, `file()` (file operations)
- List/dict modification (immutable)

**Безопасность на 3 уровнях:**

1. **Validation Layer** - проверка схемы перед рендерингом
2. **Sandboxed Environment** - изоляция выполнения
3. **Immutable Collections** - запрет модификации данных

## Performance

- **Rendering:** ~0.5-2ms (с cache)
- **Validation:** ~0.4ms
- **Throughput:** ~7000 renders/sec
- **Cache hit rate:** >90%

**Оптимизации:**
- LRU cache для скомпилированных templates (max 1000)
- Ленивая компиляция (compile on first use)
- Thread-safe кеширование
- Автоматическая invalidation при изменении template

## Template Library

Готовые шаблоны для типовых операций доступны в `apps/templates/library/`.

```python
from apps.templates.library import get_template_library, load_template

# Загрузить все шаблоны
all_templates = get_template_library()
print(all_templates.keys())  # ['catalog_users', 'update_prices', 'document_sales']

# Загрузить конкретный шаблон
catalog_users = load_template('catalog_users')

# Создать OperationTemplate из library
template = OperationTemplate.objects.create(
    name=catalog_users['name'],
    operation_type=catalog_users['operation_type'],
    target_entity=catalog_users['target_entity'],
    template_data=catalog_users['template_data']
)
```

**См. также:** [Template Library README](library/README.md)

## REST API Reference

### Endpoints

v1 CRUD endpoints удалены.

**GET /api/v2/templates/list-templates/**
- Список OperationTemplate (для SPA)

**POST /api/v2/templates/sync-from-registry/**
- Синхронизация шаблонов из registry (staff-only; основной путь через SPA `/templates`)

**Internal API (для Worker)**
- `GET /api/v2/internal/get-template?template_id=...`
- `POST /api/v2/internal/render-template?template_id=...`

### Example API Usage

```bash
# Sync from registry (staff-only)
curl -X POST http://localhost:8200/api/v2/templates/sync-from-registry/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

## Testing

```bash
cd orchestrator
source venv/Scripts/activate

# Unit tests
pytest apps/templates/tests/test_engine.py -v

# Validation tests
pytest apps/templates/tests/test_validation.py -v

# E2E integration tests
pytest apps/templates/tests/test_integration_e2e.py -v

# All tests with coverage
pytest apps/templates/tests/ --cov=apps/templates/engine --cov-report=term-missing

# Specific test
pytest apps/templates/tests/test_engine.py::TestTemplateRenderer::test_render_simple_template -v
```

## Architecture

```
apps/templates/
├── engine/
│   ├── __init__.py          # Public API exports
│   ├── renderer.py          # TemplateRenderer (main entry point)
│   ├── validator.py         # TemplateValidator (security + schema validation)
│   ├── cache.py             # TemplateCache (LRU caching)
│   ├── filters.py           # Custom 1С filters
│   ├── tests.py             # Custom Jinja2 tests
│   └── exceptions.py        # Custom exceptions
├── library/
│   ├── __init__.py          # Library loader
│   ├── catalog_users.json   # Pre-built template
│   ├── update_prices.json   # Pre-built template
│   ├── document_sales.json  # Pre-built template
│   └── README.md            # Library documentation
├── models.py                # OperationTemplate model
├── serializers.py           # DRF serializers
├── views.py                 # REST API viewsets
└── tests/
    ├── test_engine.py       # Unit tests
    ├── test_validation.py   # Validation tests
    └── test_integration_e2e.py  # E2E tests
```

## OpenAPI Documentation

После запуска сервера доступна интерактивная документация:

- **Swagger UI:** http://localhost:8000/api/docs/
- **ReDoc:** http://localhost:8000/api/redoc/

## Troubleshooting

### Template не рендерится

**Проблема:** `TemplateRenderError: Undefined variable 'user_name'`

**Решение:** Убедитесь что все переменные из template присутствуют в context:
```python
renderer.render(template, {
    "user_name": "Alice",  # Обязательная переменная!
    "email": "alice@test.com"
})
```

### Validation ошибка

**Проблема:** `TemplateValidationError: Invalid operation_type`

**Решение:** Используйте только допустимые operation types: `create`, `update`, `delete`, `query`

### Cache не работает

**Проблема:** Каждый render занимает одинаковое время

**Решение:** Убедитесь что используете один и тот же template instance:
```python
# ✅ Правильно - кеш работает
template = OperationTemplate.objects.get(id=1)
renderer.render(template, context1)  # Compile + cache
renderer.render(template, context2)  # Use cache

# ❌ Неправильно - кеш не работает
renderer.render(OperationTemplate.objects.get(id=1), context1)  # New instance
renderer.render(OperationTemplate.objects.get(id=1), context2)  # New instance
```

### Security warning

**Проблема:** `SecurityError: Attribute '__class__' is not allowed`

**Решение:** Это защита от injection attacks. Не используйте introspection в templates:
```jinja2
# ❌ Запрещено
{{obj.__class__}}
{{obj.__globals__}}

# ✅ Разрешено
{{obj.name}}
{{obj.id}}
```

## Best Practices

1. **Всегда валидируйте templates** перед production:
   ```python
   renderer.render(template, context, validate=True)
   ```

2. **Используйте готовые templates из library** для типовых операций

3. **Переиспользуйте template instances** для максимального cache hit rate

4. **Логируйте все операции** для отладки:
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.info(f"Rendering template {template.id}")
   ```

5. **Используйте default values** для optional переменных:
   ```jinja2
   {{phone|default('')}}
   {{department|default('Unknown')}}
   ```

6. **Тестируйте templates** перед развертыванием:
   ```bash
   pytest apps/templates/tests/test_integration_e2e.py -v
   ```

## Roadmap

**Track 1 (DONE):**
- ✅ Template Engine Core
- ✅ Conditional Logic
- ✅ Validation Layer
- ✅ Caching & Optimization
- ✅ Integration & Documentation

**Track 2 (TODO):**
- ⏳ Worker Integration (Push to Redis queue)
- ⏳ Real OData Execution
- ⏳ WebSocket Progress Updates
- ⏳ Batch Operations

**Track 3 (Future):**
- 📋 Advanced Loop Support
- 📋 Custom Functions
- 📋 Template Versioning
- 📋 Template Inheritance

## Contributing

См. [CONTRIBUTING.md](../../../docs/CONTRIBUTING.md) для деталей.

## License

MIT License - см. [LICENSE](../../../LICENSE)

## Support

- Issues: https://github.com/your-org/command-center-1c/issues
- Docs: https://docs.commandcenter1c.com
- Email: support@commandcenter1c.com
