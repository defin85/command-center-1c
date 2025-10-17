# CommandCenter1C Demo Environment

Демонстрационный стенд для тестирования CommandCenter1C с Mock 1C OData серверами.

---

## 🎯 Описание

Demo стенд включает:
- **3 Mock 1C OData Server** - эмуляция баз 1С (Moscow, St. Petersburg, Ekaterinburg)
- **Django Orchestrator** - центр управления и координации
- **PostgreSQL** - основная база данных
- **Redis** - очереди задач и кэширование
- **Automated Test Suite** - автоматизированные тесты всех компонентов

---

## 🚀 Quick Start

### Запуск стенда

```bash
# Из корня проекта
docker-compose -f docker-compose.demo.yml up -d

# Ожидание запуска (30-60 секунд)
docker-compose -f docker-compose.demo.yml logs -f orchestrator

# Когда увидите "Quit the server with CONTROL-C", стенд готов
```

### Запуск тестов

```bash
# Установка зависимостей (первый раз)
pip install requests

# Запуск тестов
python demo/test_demo.py
```

### Остановка стенда

```bash
docker-compose -f docker-compose.demo.yml down

# С удалением данных
docker-compose -f docker-compose.demo.yml down -v
```

---

## 📊 Список сервисов

| Сервис | URL | Описание |
|--------|-----|----------|
| Mock 1C Moscow | http://localhost:8081 | База moscow_001 |
| Mock 1C SPB | http://localhost:8082 | База spb_001 |
| Mock 1C EKB | http://localhost:8083 | База ekb_001 |
| Django Orchestrator | http://localhost:8000 | API и админка |
| PostgreSQL | localhost:5432 | БД (user: cc1c_user, pass: cc1c_password) |
| Redis | localhost:6379 | Очереди и кэш |

---

## 🔐 Учетные данные

### Mock 1C Servers
- **Username**: `Администратор`
- **Password**: `mock_password`

### PostgreSQL
- **Database**: `commandcenter`
- **Username**: `cc1c_user`
- **Password**: `cc1c_password`

---

## 📝 Примеры использования

### Работа с Mock 1C Server напрямую

#### Health Check
```bash
curl http://localhost:8081/health
```

#### Получение метаданных
```bash
curl http://localhost:8081/odata/standard.odata/\$metadata
```

#### Получение списка пользователей
```bash
curl -u "Администратор:mock_password" \
  http://localhost:8081/odata/standard.odata/Catalog_Пользователи
```

#### Создание пользователя
```bash
curl -u "Администратор:mock_password" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "Description": "Иванов Иван",
    "Code": "00001",
    "ИмяПользователя": "ivanov",
    "Email": "ivanov@example.com"
  }' \
  http://localhost:8081/odata/standard.odata/Catalog_Пользователи
```

#### Обновление пользователя
```bash
# Сначала получите Ref_Key пользователя
curl -u "Администратор:mock_password" \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"Email": "new@example.com"}' \
  "http://localhost:8081/odata/standard.odata/Catalog_Пользователи(guid'YOUR-GUID-HERE')"
```

#### Удаление пользователя
```bash
curl -u "Администратор:mock_password" \
  -X DELETE \
  "http://localhost:8081/odata/standard.odata/Catalog_Пользователи(guid'YOUR-GUID-HERE')"
```

---

### Работа через Django Orchestrator API

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Создание базы данных
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Moscow Office",
    "code": "moscow_001",
    "odata_url": "http://mock-1c-moscow:8080/odata/standard.odata",
    "username": "Администратор",
    "password": "mock_password",
    "is_active": true
  }' \
  http://localhost:8000/api/databases/
```

#### Получение списка баз
```bash
curl http://localhost:8000/api/databases/
```

#### Health Check базы через API
```bash
# Замените {id} на ID созданной базы
curl -X POST http://localhost:8000/api/databases/{id}/health_check/
```

---

## 📦 Структура Mock данных

### Entity Types

Mock сервер поддерживает 3 типа сущностей:

#### 1. Catalog_Пользователи
```json
{
  "Ref_Key": "uuid",
  "Description": "ФИО пользователя",
  "Code": "код",
  "ИмяПользователя": "логин",
  "Email": "email"
}
```

#### 2. Catalog_Организации
```json
{
  "Ref_Key": "uuid",
  "Description": "название организации",
  "Code": "код",
  "ИНН": "ИНН",
  "КПП": "КПП"
}
```

#### 3. Catalog_Номенклатура
```json
{
  "Ref_Key": "uuid",
  "Description": "наименование товара",
  "Code": "код",
  "Артикул": "артикул",
  "Цена": 1000.00
}
```

---

## 🧪 Структура тестов

### Test Suite включает:

1. **Mock Server Tests**
   - Health check каждого сервера
   - Получение метаданных OData
   - CRUD операции (Create, Read, Update, Delete)

2. **Orchestrator Tests**
   - Health check Django
   - Database API (создание, получение списка)
   - Health check баз через API

3. **Integration Tests**
   - Интеграция Orchestrator ↔ Mock Servers
   - End-to-end проверка полного цикла

### Запуск конкретных тестов

```bash
# Весь набор
python demo/test_demo.py

# С выводом деталей (модифицируйте скрипт)
python demo/test_demo.py --verbose
```

---

## 🔍 Troubleshooting

### Сервисы не запускаются

```bash
# Проверка статуса
docker-compose -f docker-compose.demo.yml ps

# Проверка логов
docker-compose -f docker-compose.demo.yml logs

# Проверка конкретного сервиса
docker-compose -f docker-compose.demo.yml logs mock-1c-moscow
docker-compose -f docker-compose.demo.yml logs orchestrator
```

### Orchestrator не подключается к PostgreSQL

```bash
# Проверка готовности PostgreSQL
docker-compose -f docker-compose.demo.yml exec postgres pg_isready

# Проверка миграций
docker-compose -f docker-compose.demo.yml exec orchestrator python manage.py migrate
```

### Mock сервер возвращает 401 Unauthorized

Проверьте учетные данные:
- Username: `Администратор` (кириллица!)
- Password: `mock_password`

### Порты заняты

Если порты 8000, 8081-8083, 5432, 6379 заняты:

```bash
# Проверка занятости портов (Windows)
netstat -ano | findstr "8000"
netstat -ano | findstr "8081"

# Либо измените порты в docker-compose.demo.yml
```

### Тесты падают с timeout

Увеличьте время ожидания в `test_demo.py`:

```python
# В функции wait_for_services()
max_attempts = 60  # было 30
```

---

## 📁 Структура файлов

```
demo/
├── mock_1c_server/
│   ├── app.py              # Flask приложение
│   ├── requirements.txt    # Python зависимости
│   └── Dockerfile          # Docker образ
├── test_demo.py            # Автоматизированные тесты
├── README.md               # Эта документация
└── .gitignore              # Игнорируемые файлы
```

---

## 🎨 OData v3 Response Format

Mock сервер возвращает данные в OData v3 формате:

### Collection (список)
```json
{
  "d": {
    "results": [
      {"Ref_Key": "...", "Description": "..."},
      {"Ref_Key": "...", "Description": "..."}
    ]
  }
}
```

### Single Entity (одна сущность)
```json
{
  "d": {
    "Ref_Key": "550e8400-e29b-41d4-a716-446655440000",
    "Description": "Иванов Иван",
    "Code": "00001"
  }
}
```

### Error Response
```json
{
  "odata.error": {
    "code": "404",
    "message": {
      "lang": "ru-RU",
      "value": "Entity not found"
    }
  }
}
```

---

## ⚠️ Ограничения Mock Server

1. **In-memory storage** - данные теряются при перезапуске
2. **Нет фильтрации** - `$filter`, `$orderby`, `$skip`, `$top` не поддерживаются
3. **Нет batch operations** - `$batch` не реализован
4. **Упрощенная валидация** - минимальная проверка данных
5. **Нет транзакций** - каждая операция атомарна

---

## 🔗 Полезные ссылки

- **OData v3 Spec**: https://www.odata.org/documentation/odata-version-3-0/
- **1С OData**: https://its.1c.ru/db/v8std/content/639/hdoc
- **Flask Documentation**: https://flask.palletsprojects.com/
- **Docker Compose**: https://docs.docker.com/compose/

---

## 📊 Метрики производительности

### Ожидаемые значения

| Метрика | Значение |
|---------|----------|
| Mock Server startup | < 5 сек |
| Orchestrator startup | < 30 сек |
| Health check response | < 100 мс |
| CRUD operation | < 500 мс |
| Full test suite | < 60 сек |

---

## 🎯 Следующие шаги

После успешного запуска demo стенда:

1. Изучите API Orchestrator (будет добавлено в `docs/api/`)
2. Интегрируйте с Go API Gateway (Phase 1, Sprint 1.3)
3. Реализуйте Worker Pool (Phase 1, Sprint 1.4)
4. Добавьте Frontend (Phase 1, Sprint 1.5)

---

**Версия**: 1.0
**Дата**: 2025-01-17
**Статус**: Phase 1, Sprint 1.2 Complete
