# Все варианты API для работы с RAS 1С - Полный обзор

## 🎯 Найденные решения

После тщательного исследования найдено **5 вариантов** работы с RAS:

| № | Решение | Тип | Язык | Лицензия | Статус |
|---|---------|-----|------|----------|--------|
| 1 | **rac.exe** | CLI | C++ | Proprietary | ✅ Stable |
| 2 | **Java API** | Library | Java | Proprietary | ✅ Stable |
| 3 | **ras-grpc-gw** | gRPC Gateway | Go | MIT | ⚠️ ALPHA |
| 4 | **hirac** | REST API | OneScript | MPL-2.0 | ✅ Stable |
| 5 | **v8platform/protos + grpc-gateway** | gRPC→REST | Go | MIT | 🔨 DIY |

---

## Вариант 1: rac.exe (CLI) ⭐ Проверенное решение

### Описание
Стандартная утилита командной строки от 1С для администрирования кластера.

### Характеристики
- **Язык:** CLI (текстовый вывод)
- **Лицензия:** Входит в платформу 1С
- **Статус:** Production-ready
- **Установка:** Включена в платформу 1С

### Преимущества
✅ Официальная поддержка
✅ Стабильная работа
✅ Полный функционал
✅ Не требует дополнительных компонентов

### Недостатки
❌ Парсинг текстового вывода
❌ Проблемы с кодировкой (Windows-1251)
❌ Медленнее для частых запросов
❌ Трудно тестировать

### Пример использования
```bash
# Получить список кластеров
rac.exe localhost:1545 cluster list

# Получить список баз
rac.exe localhost:1545 infobase summary list \
  --cluster=<uuid> \
  --cluster-user=admin \
  --cluster-pwd=password
```

### Рекомендация для CommandCenter1C
**✅ Используйте для Phase 1-2** - безопасный, надёжный вариант для старта.

**Документация:** `docs/1C_RAC_COMMANDS.md`

---

## Вариант 2: Java API (Official) ⭐ Официальное решение

### Описание
Официальный набор JAR библиотек от 1С для прямого взаимодействия с RAS.

### Характеристики
- **Язык:** Java
- **Лицензия:** Требуется лицензия 1С для скачивания
- **Статус:** Production-ready
- **Установка:** Скачать с 1c-dn.com (требуется регистрация)

### Преимущества
✅ Официальная поддержка от 1С
✅ Прямое взаимодействие с RAS (без rac.exe)
✅ Структурированные данные (Java объекты)
✅ Полный функционал
✅ Стабильная работа

### Недостатки
❌ Требуется лицензия 1С
❌ Только Java (нужен JVM)
❌ Дополнительная зависимость
❌ Сложная интеграция с Go

### Пример использования
```java
IAgentAdmin agent = IAgentAdminConnector.connectAgent("server:1545");
agent.authenticate(cluster, "admin", "password");
IClusterAdmin clusterAdmin = agent.getClusterAdmin(cluster);
IInfoBaseInfo[] infobases = clusterAdmin.getInfoBases();
```

### Интеграция с Go
- Вариант A: JNI (сложно, overhead)
- Вариант B: Микросервис на Java с REST API (рекомендуется)

### Где скачать
- **Официально:** https://1c-dn.com/library/1c_enterprise_8_administrative_service_api/
- **Неофициально:** https://github.com/MinimaJack/repository

### Рекомендация для CommandCenter1C
**⏳ Рассмотреть для Phase 3** - когда потребуется максимальная надёжность.

**Документация:** `docs/1C_RAS_API_OPTIONS.md`

---

## Вариант 3: ras-grpc-gw 🚀 Современное решение

### Описание
Open Source Go-проект, предоставляющий gRPC API для работы с RAS.

### Характеристики
- **Язык:** Go
- **Протокол:** gRPC
- **Лицензия:** MIT (Open Source)
- **Статус:** ⚠️ ALPHA (не рекомендуется для production)
- **Репозиторий:** https://github.com/v8platform/ras-grpc-gw

### Преимущества
✅ Написан на Go (легко интегрируется)
✅ gRPC API (структурированные данные)
✅ НЕ требует rac.exe
✅ НЕ требует лицензию 1C
✅ НЕ требует Java
✅ Open Source (MIT)
✅ Docker контейнер готов

### Недостатки
❌ ALPHA версия (не для production)
❌ Ограниченный функционал
❌ Может быть нестабилен
❌ Документация ограничена

### Функционал
```protobuf
✅ GetClusters              // Список кластеров
✅ GetInfobasesSummary      // Список баз (краткая информация)
✅ GetInfobases             // Список баз (полная информация)
✅ GetSessions              // Список сессий
✅ AuthenticateCluster      // Авторизация
```

### Пример использования

**Docker:**
```bash
docker run -d --name ras-grpc-gw \
  -p 3002:3002 \
  v8platform/ras-grpc-gw:latest \
  1cserver:1545
```

**Go код:**
```go
conn, _ := grpc.Dial("localhost:3002", grpc.WithInsecure())
infobasesClient := infobasesv1.NewInfobasesServiceClient(conn)

ctx := metadata.AppendToOutgoingContext(context.Background(),
    "endpoint_id", "1")

infobases, _ := infobasesClient.GetInfobasesSummary(ctx,
    &infobasesv1.GetInfobasesSummaryRequest{
        ClusterId: clusterID,
    })
```

### Рекомендация для CommandCenter1C
**🧪 Протестировать в Phase 2.5** - перспективное решение, но нужно проверить стабильность.

**Документация:** `docs/1C_RAS_GRPC_SOLUTION.md`

---

## Вариант 4: hirac (REST API) ⭐ Production-ready REST

### Описание
REST API приложение на OneScript, предоставляющее HTTP интерфейс к RAC.

### Характеристики
- **Язык:** OneScript (специфичный для 1С экосистемы)
- **Протокол:** HTTP/REST
- **Лицензия:** MPL-2.0 (Open Source)
- **Статус:** ✅ Production-ready
- **Репозиторий:** https://github.com/arkuznetsov/hirac

### Преимущества
✅ REST API (простой HTTP)
✅ Production-ready (активно используется)
✅ Полный функционал
✅ Фильтрация и агрегация
✅ Поддержка Prometheus метрик
✅ Docker контейнер
✅ Open Source

### Недостатки
❌ Написан на OneScript (специфичный язык)
❌ Требует OneScript.Web фреймворк
❌ Использует rac.exe внутри (обёртка)
❌ Дополнительная зависимость

### API Endpoints

```http
GET /cluster/list              # Список кластеров
GET /infobase/list             # Список всех баз
GET /infobase/<path>           # Информация о конкретной базе
GET /session/list              # Список сессий
GET /connection/list           # Список соединений
GET /counter/session?dim=_all  # Счётчики сессий
```

### Форматы вывода
- JSON (по умолчанию)
- Prometheus
- Plain text

### Пример использования

**Docker:**
```bash
docker run -d -p 5000:5000 oscript/hirac:latest
```

**HTTP запрос:**
```bash
curl http://localhost:5005/infobase/list
```

**Ответ (JSON):**
```json
[
  {
    "uuid": "e1092854-3660-11e7-6b9e-d017c292ea7a",
    "name": "BUH",
    "descr": "Бухгалтерия предприятия"
  },
  {
    "uuid": "f2193965-4771-11e7-7c0f-e128d383fb8b",
    "name": "TRADE",
    "descr": "Торговля и склад"
  }
]
```

### Рекомендация для CommandCenter1C
**✅ Отличный вариант для Phase 2** - если нужен готовый REST API.

**Преимущество:** Не нужно писать код - просто деплой Docker контейнера.

---

## Вариант 5: v8platform/protos + grpc-gateway 🔨 DIY решение

### Описание
Proto definitions с grpc-gateway аннотациями - можно сгенерировать REST API из gRPC.

### Характеристики
- **Язык:** Go (генерация из proto)
- **Протокол:** gRPC + REST (grpc-gateway)
- **Лицензия:** MIT
- **Статус:** 🔨 Требует доработки
- **Репозиторий:** https://github.com/v8platform/protos

### Что это даёт
В proto файлах уже есть аннотации для grpc-gateway:

```protobuf
message GetInfobasesSummaryRequest {
  option (grpc.gateway.protoc_gen_openapiv2.options.openapiv2_schema) = {
    json_schema: {
      title: "GetInfobasesSummaryRequest";
      description: "Get cluster infobase summary list";
      required: ["cluster_id"];
    };
  };
  // ...
}
```

### Что нужно сделать
1. Раскомментировать grpc-gateway в `buf.gen.yaml`
2. Сгенерировать Go код с REST endpoints
3. Запустить gRPC server + REST gateway
4. Использовать REST API

### Преимущества
✅ Автоматическая генерация REST из gRPC
✅ Swagger/OpenAPI документация
✅ Один сервер для gRPC и REST
✅ Типизированные данные

### Недостатки
❌ Требует настройки и сборки
❌ Нужно понимать protobuf/grpc-gateway
❌ DIY (сделай сам)

### Пример архитектуры

```
┌────────────────────────┐
│    Go Application      │
│  ┌──────────────────┐  │
│  │  gRPC Server     │  │ ← gRPC клиенты
│  │  (port 9090)     │  │
│  └──────────────────┘  │
│  ┌──────────────────┐  │
│  │  REST Gateway    │  │ ← HTTP/REST клиенты
│  │  (port 8080)     │  │
│  └──────────────────┘  │
└───────────┬────────────┘
            │
            ▼
      RAS (port 1545)
```

### Рекомендация для CommandCenter1C
**⏳ Рассмотреть в будущем** - если захочется кастомное решение с полным контролем.

---

## 📊 Сравнительная таблица

| Критерий | rac.exe | Java API | ras-grpc-gw | hirac | protos+gateway |
|----------|---------|----------|-------------|-------|----------------|
| **Простота** | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| **Лицензия** | ✅ Включена | ❌ Требуется | ✅ MIT | ✅ MPL-2.0 | ✅ MIT |
| **Язык** | CLI | Java | Go | OneScript | Go |
| **Протокол** | Text | Binary | gRPC | REST | gRPC+REST |
| **Production** | ✅ Да | ✅ Да | ❌ ALPHA | ✅ Да | ⚠️ DIY |
| **Go интеграция** | ⭐⭐ exec | ⭐ JNI | ⭐⭐⭐ Native | ⭐⭐⭐ HTTP | ⭐⭐⭐ Native |
| **Производительность** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **Функционал** | ⭐⭐⭐ Полный | ⭐⭐⭐ Полный | ⭐⭐ Базовый | ⭐⭐⭐ Полный | ⭐⭐ Базовый |
| **Документация** | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ |
| **Сообщество** | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ |

---

## 🎯 Рекомендации для CommandCenter1C

### Краткосрочно (Phase 1-2): **rac.exe** ✅

**Почему:**
- Стабильно, проверено
- Не требует дополнительных компонентов
- Быстро запустить
- Низкий риск

**Реализация:**
```
Go Installation Service → rac.exe → парсинг → Redis → Django
```

**Время:** 2-3 дня

---

### Среднесрочно (Phase 2.5): **Тестирование hirac** 🧪

**Почему:**
- Production-ready REST API
- Простая интеграция (HTTP)
- Docker контейнер готов
- Не нужно писать код

**Архитектура:**
```
┌─────────────────┐
│ Go Installation │
│    Service      │
└────────┬────────┘
         │ HTTP
┌────────▼────────┐
│     hirac       │ ← Docker контейнер
│  (REST API)     │
└────────┬────────┘
         │ rac.exe
┌────────▼────────┐
│   RAS Server    │
└─────────────────┘
```

**План:**
1. Деплой hirac в Docker
2. Протестировать на staging
3. Сравнить с rac.exe подходом
4. Если стабильно → мигрировать

**Время:** 1 неделя на тестирование

---

### Долгосрочно (Phase 3+): **ras-grpc-gw или Java API** 🚀

**Выбор зависит от:**

#### Если ras-grpc-gw стабилизируется:
- Чистый Go код
- Нативная интеграция
- Современный gRPC
- Open Source

#### Если нужна максимальная надёжность:
- Java API (официальное решение)
- Java микросервис с REST API
- Полный функционал
- Официальная поддержка

**Время:** 3-4 недели

---

## 🏗️ Архитектура с REST API (Рекомендуемая)

### Вариант A: hirac (Простой)

```yaml
version: '3.8'
services:
  hirac:
    image: oscript/hirac:latest
    container_name: commandcenter-hirac
    ports:
      - "5005:5005"
    volumes:
      - ./hirac-config:/app/config
    networks:
      - commandcenter-network

  installation-service:
    build: ./installation-service
    environment:
      - CLUSTER_API_URL=http://hirac:5005
    depends_on:
      - hirac
    networks:
      - commandcenter-network
```

### Go код для работы с hirac

```go
package cluster

import (
    "encoding/json"
    "fmt"
    "net/http"
)

type HiracClient struct {
    baseURL string
    client  *http.Client
}

func NewHiracClient(baseURL string) *HiracClient {
    return &HiracClient{
        baseURL: baseURL,
        client:  &http.Client{},
    }
}

func (c *HiracClient) GetInfobaseList() ([]InfobaseInfo, error) {
    resp, err := c.client.Get(c.baseURL + "/infobase/list")
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var infobases []InfobaseInfo
    if err := json.NewDecoder(resp.Body).Decode(&infobases); err != nil {
        return nil, err
    }

    return infobases, nil
}

type InfobaseInfo struct {
    UUID string `json:"uuid"`
    Name string `json:"name"`
    Descr string `json:"descr"`
}
```

---

## 📝 Итоговая матрица принятия решений

| Требование | Решение |
|------------|---------|
| **Быстрый старт** | rac.exe |
| **Production-ready REST** | hirac |
| **Официальная поддержка** | Java API |
| **Современный Go** | ras-grpc-gw (после стабилизации) |
| **Полный контроль** | v8platform/protos + gateway (DIY) |
| **Минимум зависимостей** | rac.exe |
| **Легче тестировать** | hirac или ras-grpc-gw (HTTP/gRPC) |
| **Интеграция с Prometheus** | hirac |

---

## 📚 Документация

Созданные файлы документации:
- `docs/1C_RAC_COMMANDS.md` - Полное руководство по rac.exe
- `docs/1C_RAS_vs_RAC.md` - Отличия RAS и RAC
- `docs/1C_RAS_API_OPTIONS.md` - Java API и альтернативы
- `docs/1C_RAS_GRPC_SOLUTION.md` - ras-grpc-gw детальное описание
- `docs/1C_RAS_ALL_API_OPTIONS.md` - Этот файл (полный обзор)

---

## 🔗 Полезные ссылки

### Официальные ресурсы
- [1C Administrative Service API](https://1c-dn.com/library/1c_enterprise_8_administrative_service_api/)
- [1C Documentation](https://kb.1ci.com/)

### Open Source проекты
- [v8platform/ras-grpc-gw](https://github.com/v8platform/ras-grpc-gw) - gRPC Gateway
- [arkuznetsov/hirac](https://github.com/arkuznetsov/hirac) - REST API
- [v8platform/protos](https://github.com/v8platform/protos) - Proto definitions
- [MinimaJack/1C-server-api](https://github.com/MinimaJack/1C-server-api) - Java API примеры

---

## ✅ Рекомендованный план действий

### Week 1-2: Реализация с rac.exe
- ✅ Создать Go модуль `cluster_manager.go`
- ✅ Парсинг вывода rac.exe
- ✅ Интеграция с Django

### Week 3-4: Тестирование hirac
- ⏳ Деплой hirac в Docker
- ⏳ Переписать Go код для HTTP API
- ⏳ A/B тестирование с rac.exe

### Week 5-6: Принятие решения
- ⏳ Анализ результатов
- ⏳ Выбор финального решения
- ⏳ Миграция или продолжение с rac.exe

### Phase 3 (3+ месяца): Production оптимизация
- ⏳ Если нужна максимальная надёжность → Java API
- ⏳ Если ras-grpc-gw стабилен → миграция на gRPC
- ⏳ Если всё работает → оставить текущее решение

---

**Версия:** 1.0
**Дата:** 2025-10-27
**Автор:** CommandCenter1C Team
**Статус:** Финальная рекомендация
