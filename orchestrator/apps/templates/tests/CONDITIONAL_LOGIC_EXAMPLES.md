# Conditional Logic Examples

## Custom Jinja2 Tests

### production_database

Проверяет, является ли база данных production типом:

```jinja2
{% if database is production_database %}
{
  "Наименование": "{{ database.name }}",
  "ПометкаУдаления": false,
  "Комментарий": "Production база - осторожно!"
}
{% else %}
{
  "Наименование": "{{ database.name }}",
  "ПометкаУдаления": false
}
{% endif %}
```

### test_database / development_database

Аналогично для test и development:

```jinja2
{% if database is test_database %}
  "ТестовыеДанные": true,
{% elif database is development_database %}
  "Разработка": true,
{% endif %}
```

### empty / nonempty

Проверка на пустоту:

```jinja2
{% if users is empty %}
{
  "Сообщение": "Нет пользователей"
}
{% else %}
{
  "Пользователи": [
    {% for user in users %}
    "{{ user }}"{% if not loop.last %},{% endif %}
    {% endfor %}
  ]
}
{% endif %}
```

## {% if %} Conditions

### Простые условия

```jinja2
{% if is_active %}
"Статус": "Активен",
{% endif %}
```

### if-else

```jinja2
"Статус": "{% if is_active %}Активен{% else %}Неактивен{% endif %}",
```

### if-elif-else

```jinja2
"Уровень": "{% if score >= 90 %}Отлично{% elif score >= 70 %}Хорошо{% else %}Удовлетворительно{% endif %}",
```

### Операторы сравнения

```jinja2
{% if quantity > 0 %}
"ДоступноКЗаказу": true,
{% endif %}

{% if price <= 1000 %}
"Скидка": 10,
{% endif %}
```

### Логические операторы (and, or, not)

```jinja2
{% if is_active and is_verified %}
"ПолныйДоступ": true,
{% endif %}

{% if is_admin or is_moderator %}
"Права": ["Модерация"],
{% endif %}

{% if not is_banned %}
"Доступ": "Разрешен",
{% endif %}
```

### Оператор in

```jinja2
{% if 'admin' in roles %}
"АдминПрава": true,
{% endif %}
```

### Вложенные условия

```jinja2
{% if database is production_database %}
  {% if users is nonempty %}
    "Пользователей": {{ users|length }},
  {% else %}
    "Пользователей": 0,
  {% endif %}
{% endif %}
```

## {% for %} Loops

### Простой цикл

```jinja2
"Пользователи": [
  {% for user in users %}
  {
    "Имя": "{{ user.name }}",
    "Email": "{{ user.email }}"
  }{% if not loop.last %},{% endif %}
  {% endfor %}
]
```

### loop.index / loop.index0

```jinja2
{% for item in items %}
"Позиция{{ loop.index }}": "{{ item }}",
{% endfor %}

{% for item in items %}
"Item_{{ loop.index0 }}": "{{ item }}",  // 0-based index
{% endfor %}
```

### loop.first / loop.last

```jinja2
"Строка": "{% for item in items %}{% if loop.first %}[{% endif %}{{ item }}{% if not loop.last %}, {% endif %}{% if loop.last %}]{% endif %}{% endfor %}"
```

### Цикл по словарю

```jinja2
{% for key, value in data.items() %}
"{{ key }}": "{{ value }}",
{% endfor %}
```

### Вложенные циклы

```jinja2
"Матрица": [
  {% for row in matrix %}
  [
    {% for cell in row %}
    {{ cell }}{% if not loop.last %},{% endif %}
    {% endfor %}
  ]{% if not loop.last %},{% endif %}
  {% endfor %}
]
```

### for-else (если список пустой)

```jinja2
"Результат": [
  {% for item in items %}
  "{{ item }}"
  {% else %}
  "Нет элементов"
  {% endfor %}
]
```

### Фильтрация внутри цикла

```jinja2
"ЧетныеЧисла": [
  {% for num in numbers %}
  {% if num % 2 == 0 %}
  {{ num }}{% if not loop.last %},{% endif %}
  {% endif %}
  {% endfor %}
]
```

## Комбинированные примеры

### Сложный пример с множественными условиями

```jinja2
{
  "База": "{{ database.name }}",
  {% if database is production_database %}
  "Тип": "Production",
  "ПометкаУдаления": false,
  "Резервирование": true,
  {% elif database is test_database %}
  "Тип": "Test",
  "ПометкаУдаления": false,
  "Резервирование": false,
  {% endif %}
  
  {% if users is nonempty %}
  "Пользователи": [
    {% for user in users %}
    {
      "Ref_Key": "{{ user.id|guid1c }}",
      "Наименование": "{{ user.name }}",
      {% if user.is_admin %}
      "Роль": "Администратор",
      {% elif user.is_moderator %}
      "Роль": "Модератор",
      {% else %}
      "Роль": "Пользователь",
      {% endif %}
      "Активен": {{ user.is_active|bool1c }}
    }{% if not loop.last %},{% endif %}
    {% endfor %}
  ]
  {% else %}
  "Пользователи": []
  {% endif %}
}
```

### OData $filter с условиями

```jinja2
{
  "$filter": "{% if database is production_database %}ПометкаУдаления eq false{% else %}ПометкаУдаления eq true{% endif %} and {% if min_price %}Цена ge {{ min_price }}{% endif %}"
}
```
