# OData Integration для работы с 1С:Бухгалтерия

**Статус:** Актуально для CommandCenter1C
**Версия:** 1.0
**Дата:** 2025-10-31

Практический гайд по работе с данными 1С через OData протокол для массовых операций.

---

## 🎯 Что такое OData в 1С

**OData (Open Data Protocol)** - стандартный RESTful протокол для CRUD операций с данными.

**В 1С:Бухгалтерия:**
- ✅ HTTP REST API для справочников, документов, регистров
- ✅ JSON/XML формат данных
- ✅ Поддержка batch operations (группировка запросов)
- ✅ Фильтрация, сортировка, пагинация

**Endpoint:**
```
http://server/database_name/odata/standard.odata/
```

---

## 🏗️ Архитектура в CommandCenter1C

```
Django Orchestrator → Python OData Client → HTTP → 1С HTTP Service → OData Publication
                                                                              ↓
                                                                    Справочники / Документы
```

**Преимущества для массовых операций:**
- ✅ **Batch requests** - до 100 операций в одной транзакции
- ✅ **Короткие транзакции** - выполнение < 15 секунд (критично для 1С!)
- ✅ **Атомарность** - весь batch либо успешен, либо откатывается
- ✅ **Производительность** - одно HTTP соединение вместо N запросов

---

## ⚙️ Настройка OData Publication в 1С

### 1. Включить HTTP Service

**Конфигурация → Публикация → HTTP сервисы**

1. Создать новый HTTP сервис
2. Имя: `odata`
3. Корневой URL: `/odata/standard.odata`
4. Включить публикацию

### 2. Настроить OData Publication

**Конфигурация → Общие → Публикация OData**

1. Создать новую публикацию
2. Имя: `StandardOData`
3. Добавить объекты для публикации:
   - Справочники (Catalogs)
   - Документы (Documents)
   - Регистры накопления (AccumulationRegisters)

### 3. Права доступа

Создать пользователя для OData:
```
Логин: odata_api
Пароль: <secure_password>
Роли:
  - Полные права (для массовых операций)
  - Базовые права (для чтения)
```

### 4. Проверка доступности

```bash
curl -u odata_api:password \
  "http://localhost/database_name/odata/standard.odata/\$metadata"
```

**Ожидаемый ответ:** XML с описанием всех entity types.

---

## 🐍 Python OData Client

### Установка

```bash
pip install requests
```

### OneCODataClient

**Файл:** `orchestrator/apps/databases/odata/client.py`

```python
import requests
from requests.auth import HTTPBasicAuth
import json

class OneCODataClient:
    def __init__(self, base_url, username, password):
        """
        base_url: http://localhost/database_name/odata/standard.odata
        """
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })

    def get_entity(self, entity_type, filters=None, top=None):
        """
        Получить список entity

        entity_type: "Catalog_Товары", "Document_ПоступлениеТоваров"
        filters: OData $filter string
        top: OData $top limit
        """
        url = f"{self.base_url}/{entity_type}"
        params = {}

        if filters:
            params['$filter'] = filters
        if top:
            params['$top'] = top

        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def create_entity(self, entity_type, data):
        """Создать новый entity"""
        url = f"{self.base_url}/{entity_type}"
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def update_entity(self, entity_type, entity_id, data):
        """Обновить entity"""
        url = f"{self.base_url}/{entity_type}(guid'{entity_id}')"
        response = self.session.patch(url, json=data)
        response.raise_for_status()
        return response.json()

    def delete_entity(self, entity_type, entity_id):
        """Удалить entity"""
        url = f"{self.base_url}/{entity_type}(guid'{entity_id}')"
        response = self.session.delete(url)
        response.raise_for_status()
```

---

## 🚀 Batch Operations (Критично!)

### Зачем нужны batch операции

**Проблема:**
```python
# ❌ БЕЗ batch - 1000 запросов = 1000 транзакций (МЕДЛЕННО!)
for user in users:
    client.create_entity("Catalog_Пользователи", user)
```

**Решение:**
```python
# ✅ С batch - 1 запрос = 1 транзакция (БЫСТРО!)
client.batch_create("Catalog_Пользователи", users)  # до 100 объектов
```

### BatchODataClient

```python
class BatchODataClient(OneCODataClient):
    def batch_create(self, entity_type, objects_list, batch_size=50):
        """
        Создание множества объектов через batch request

        КРИТИЧНО: 1С транзакции должны быть < 15 секунд!
        Поэтому batch_size не более 50-100 объектов.
        """
        results = []

        for i in range(0, len(objects_list), batch_size):
            batch = objects_list[i:i+batch_size]
            batch_results = self._execute_batch_create(entity_type, batch)
            results.extend(batch_results)

        return results

    def _execute_batch_create(self, entity_type, batch):
        """Выполнить один batch request"""
        # OData batch format
        batch_boundary = "batch_" + str(uuid.uuid4())
        changeset_boundary = "changeset_" + str(uuid.uuid4())

        headers = {
            'Content-Type': f'multipart/mixed; boundary={batch_boundary}'
        }

        # Формирование batch request body
        batch_body = self._build_batch_body(
            entity_type, batch, batch_boundary, changeset_boundary
        )

        url = f"{self.base_url}/$batch"
        response = self.session.post(url, data=batch_body, headers=headers)
        response.raise_for_status()

        return self._parse_batch_response(response.text, changeset_boundary)

    def _build_batch_body(self, entity_type, batch, batch_boundary, changeset_boundary):
        """
        Построить OData batch request body

        Format:
        --batch_boundary
        Content-Type: multipart/mixed; boundary=changeset_boundary

        --changeset_boundary
        Content-Type: application/http
        Content-Transfer-Encoding: binary

        POST Catalog_Пользователи HTTP/1.1
        Content-Type: application/json

        {"Наименование": "User1"}
        --changeset_boundary--
        --batch_boundary--
        """
        lines = []
        lines.append(f"--{batch_boundary}")
        lines.append(f"Content-Type: multipart/mixed; boundary={changeset_boundary}")
        lines.append("")

        for obj in batch:
            lines.append(f"--{changeset_boundary}")
            lines.append("Content-Type: application/http")
            lines.append("Content-Transfer-Encoding: binary")
            lines.append("")
            lines.append(f"POST {entity_type} HTTP/1.1")
            lines.append("Content-Type: application/json")
            lines.append("")
            lines.append(json.dumps(obj, ensure_ascii=False))
            lines.append("")

        lines.append(f"--{changeset_boundary}--")
        lines.append(f"--{batch_boundary}--")

        return "\r\n".join(lines)
```

---

## 💡 Примеры использования

### 1. Создание пользователей (массово)

```python
from apps.databases.odata.client import BatchODataClient

client = BatchODataClient(
    base_url="http://localhost/accounting/odata/standard.odata",
    username="odata_api",
    password="password"
)

# Подготовка данных
users = [
    {"Наименование": "Иванов И.И.", "ИмяПользователя": "ivanov"},
    {"Наименование": "Петров П.П.", "ИмяПользователя": "petrov"},
    # ... до 1000 пользователей
]

# Массовое создание (batch by 50)
results = client.batch_create("Catalog_Пользователи", users, batch_size=50)

print(f"Created {len(results)} users")
```

### 2. Обновление данных

```python
# Получить существующие записи
response = client.get_entity("Catalog_Номенклатура", top=100)
items = response['value']

# Обновить batch
updates = []
for item in items:
    updates.append({
        'Ref_Key': item['Ref_Key'],
        'Цена': item['Цена'] * 1.1  # Увеличить цену на 10%
    })

client.batch_update("Catalog_Номенклатура", updates)
```

### 3. Фильтрация и поиск

```python
# Найти активных пользователей
active_users = client.get_entity(
    "Catalog_Пользователи",
    filters="НеДействителен eq false",
    top=100
)

# Найти документы за период
documents = client.get_entity(
    "Document_ПоступлениеТоваров",
    filters="Дата ge datetime'2025-01-01' and Дата le datetime'2025-01-31'"
)
```

---

## ⏱️ Производительность и ограничения

### Транзакции 1С

**КРИТИЧНО:** Транзакции в 1С не должны превышать 15 секунд!

**Рекомендации:**
- ✅ Batch size: 50-100 объектов
- ✅ Timeout: 30 секунд для HTTP запроса
- ✅ Retry logic для failed batches
- ❌ Не создавать > 100 объектов в одном batch

### Оптимизация

```python
# ❌ ПЛОХО: Один большой batch (может превысить 15 сек)
client.batch_create("Catalog_Пользователи", users_1000, batch_size=1000)

# ✅ ХОРОШО: Несколько небольших batches
client.batch_create("Catalog_Пользователи", users_1000, batch_size=50)
```

---

## 🔍 Troubleshooting

### "Не удалось выполнить HTTP-запрос"

**Причина:** OData publication не включена.

**Решение:** Проверить в 1С настройки публикации OData.

### "401 Unauthorized"

**Причина:** Неверные credentials.

**Решение:**
```python
# Проверить доступ
curl -u odata_api:password \
  "http://localhost/database/odata/standard.odata/"
```

### "Превышено время ожидания транзакции"

**Причина:** Batch слишком большой (> 100 объектов).

**Решение:** Уменьшить `batch_size` до 50.

---

## 📚 Справочная информация

### Детальная документация (архив)

Для глубокого погружения см. `docs/archive/odata/`:
- `TZ_ODATA_AUTOMATION.md` - техническое задание и настройка
- `README.md` - общее описание OData integration
- `IMPLEMENTATION.md` - детали реализации Python клиента

### OData спецификация

- [OData v4.0](https://www.odata.org/documentation/) - официальная документация
- [1С OData Guide](https://its.1c.ru/) - документация 1С

### Полезные ссылки

- [batch-service README](../go-services/batch-service/README.md) - Go batch обработка
- [Django Cluster Integration](./DJANGO_CLUSTER_INTEGRATION.md) - интеграция с Django

---

## ✅ Checklist для настройки

- [ ] OData publication включена в 1С
- [ ] HTTP Service настроен (порт 80/443)
- [ ] Создан пользователь для OData API
- [ ] $metadata endpoint доступен
- [ ] Python client работает (get_entity)
- [ ] Batch operations работают (batch_create)
- [ ] Транзакции выполняются < 15 секунд

---

## 🚀 Next Steps (Phase 2)

- [ ] Retry logic для failed batches
- [ ] Метрики OData операций (Prometheus)
- [ ] Кэширование metadata
- [ ] Параллельные batch requests (Go workers)

---

**Версия:** 1.0
**Последнее обновление:** 2025-10-31
**Автор:** Architecture Team

**См. также:**
- `docs/1C_ADMINISTRATION_GUIDE.md` - работа с RAS/RAC
- `docs/DJANGO_CLUSTER_INTEGRATION.md` - интеграция Django
- `go-services/batch-service/README.md` - batch processing в Go
