# Template Engine

Jinja2-based template engine для CommandCenter1C с поддержкой 1С-специфичного форматирования.

## Архитектура

```
TemplateRenderer (facade)
  ├── ImmutableSandboxedEnvironment (Jinja2)
  ├── ContextBuilder (safe context)
  ├── Custom Filters (guid1c, datetime1c, date1c, bool1c)
  └── StrictUndefined (error on missing variables)
```

## Использование

```python
from apps.templates.engine import TemplateRenderer

renderer = TemplateRenderer()

# OperationTemplate instance
template.template_data = {
    "filter": "Ref_Key eq {{user_id|guid1c}}",
    "created_at": "{{timestamp|datetime1c}}",
    "is_active": "{{active|bool1c}}"
}

result = renderer.render(
    template,
    {
        "user_id": "12345678-1234-1234-1234-123456789012",
        "timestamp": datetime(2025, 1, 1, 12, 0, 0),
        "active": True
    }
)

# Result:
# {
#     "filter": "Ref_Key eq guid'12345678-1234-1234-1234-123456789012'",
#     "created_at": "datetime'2025-01-01T12:00:00'",
#     "is_active": "true"
# }
```

## Custom Filters

### guid1c
Форматирует GUID в OData формат.
```
{{user_id|guid1c}} => guid'12345678-...'
```

### datetime1c
Форматирует datetime в OData формат.
```
{{created_at|datetime1c}} => datetime'2025-01-01T12:00:00'
```

### date1c
Форматирует date в OData формат.
```
{{created_date|date1c}} => datetime'2025-01-01T00:00:00'
```

### bool1c
Форматирует boolean в 1С формат.
```
{{is_active|bool1c}} => true / false (lowercase)
```

## System Variables

- `current_timestamp` - текущее datetime
- `current_date` - текущая дата
- `template_id` - ID шаблона
- `template_name` - имя шаблона
- `operation_type` - тип операции
- `uuid4()` - генератор UUID

## Security

- ✅ ImmutableSandboxedEnvironment - песочница Jinja2
- ✅ Context sanitization - фильтрация опасных ключей
- ✅ StrictUndefined - ошибка на undefined variables
- ✅ No autoescape - для JSON/OData (не HTML)
- ✅ Whitelisted globals только безопасные функции

## Testing

```bash
cd orchestrator
export DB_ENCRYPTION_KEY='tnWi3xkVlsnkGvZX9ohL-PxdQB8Hn_9rLIikDeQveXc='
source venv/Scripts/activate
pytest apps/templates/tests/test_renderer.py -v --cov=apps/templates/engine
```

Coverage: **89%**

## Files

- `renderer.py` - Main facade (TemplateRenderer)
- `context.py` - Context builder (ContextBuilder)
- `filters.py` - Custom Jinja2 filters
- `exceptions.py` - Custom exceptions
- `config.py` - Engine configuration
- `__init__.py` - Public exports
