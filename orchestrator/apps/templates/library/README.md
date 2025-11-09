# Template Library

Готовые шаблоны для типовых операций в 1С.

## Доступные шаблоны

### catalog_users.json
Создание пользователя в справочнике `Catalog_Users`.

**Required variables:**
- `user_code` - код пользователя
- `user_name` - ФИО пользователя
- `email` - email адрес
- `is_active` - активен ли пользователь

**Optional variables:**
- `phone` - телефон
- `department` - отдел
- `is_admin` - права администратора
- `is_moderator` - права модератора
- `database_type` - тип базы данных (production/test)

**Особенности:**
- Условная логика для production баз (поле `IsActive`)
- Динамические права доступа на основе ролей
- Автоматическая timestamp

**Example:**
```python
from apps.templates.library import load_template

template_data = load_template('catalog_users')
# Use template_data to create OperationTemplate
```

### update_prices.json
Обновление цены товара в `Catalog_Products`.

**Required variables:**
- `product_code` - код товара
- `new_price` - новая цена

**Optional variables:**
- `old_price` - старая цена (для расчета скидки)
- `user_name` - кто обновил
- `current_timestamp` - время обновления

**Особенности:**
- Автоматический расчет скидки (если `old_price` указана)
- OData фильтр по коду товара
- Отслеживание кто и когда обновил

**Example:**
```python
from apps.templates.library import load_template
from apps.templates.models import OperationTemplate

# Load template from library
price_update = load_template('update_prices')

# Create OperationTemplate
template = OperationTemplate.objects.create(
    name=price_update['name'],
    operation_type=price_update['operation_type'],
    target_entity=price_update['target_entity'],
    template_data=price_update['template_data']
)

# Render with context
from apps.templates.engine import TemplateRenderer

renderer = TemplateRenderer()
result = renderer.render(template, {
    "product_code": "PROD001",
    "new_price": 850.50,
    "old_price": 1000.00
})
```

### document_sales.json
Создание документа продажи в `Document_Sales`.

**Required variables:**
- `document_number` - номер документа
- `document_date` - дата документа
- `customer_code` - код контрагента
- `customer_name` - наименование контрагента
- `product_code` - код товара
- `quantity` - количество
- `price` - цена за единицу
- `total_amount` - сумма без НДС

**Optional variables:**
- `is_draft` - черновик или проведен
- `current_timestamp` - время создания

**Особенности:**
- Автоматический расчет НДС (20%)
- Автоматический расчет итоговой суммы
- Поддержка позиций документа (line items)

## Использование

### Вариант 1: Загрузить все шаблоны

```python
from apps.templates.library import get_template_library

all_templates = get_template_library()
print(all_templates.keys())  # ['catalog_users', 'update_prices', 'document_sales']
```

### Вариант 2: Загрузить конкретный шаблон

```python
from apps.templates.library import load_template
from apps.templates.models import OperationTemplate

# Load from library
catalog_users = load_template('catalog_users')

# Create OperationTemplate from library
template = OperationTemplate.objects.create(
    name=catalog_users['name'],
    operation_type=catalog_users['operation_type'],
    target_entity=catalog_users['target_entity'],
    template_data=catalog_users['template_data']
)

# Render
from apps.templates.engine import TemplateRenderer

renderer = TemplateRenderer()
result = renderer.render(template, catalog_users['example_context'])
```

### Вариант 3: REST API

```bash
# Load template from library
curl -X POST http://localhost:8000/api/v1/templates/ \
  -H "Content-Type: application/json" \
  -d @apps/templates/library/catalog_users.json

# Render template
curl -X POST http://localhost:8000/api/v1/templates/{id}/render/ \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "user_code": "USER001",
      "user_name": "Иванов Алексей",
      "email": "ivanov@company.com",
      "is_active": true
    }
  }'
```

## Добавление новых шаблонов

Чтобы добавить новый шаблон в библиотеку:

1. Создайте JSON файл в директории `apps/templates/library/`
2. Используйте следующую структуру:

```json
{
  "name": "Template Name",
  "description": "What this template does",
  "operation_type": "create|update|delete|query",
  "target_entity": "1C_Entity_Name",
  "template_data": {
    "Field1": "{{variable1}}",
    "Field2": "{% if condition %}value{% endif %}"
  },
  "required_variables": ["variable1", "variable2"],
  "optional_variables": ["variable3"],
  "example_context": {
    "variable1": "example_value",
    "variable2": "example_value"
  }
}
```

3. Обновите этот README.md с описанием нового шаблона
