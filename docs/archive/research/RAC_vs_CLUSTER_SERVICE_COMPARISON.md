# Сравнение функционала RAC и cluster-service

**Дата анализа:** 2025-11-01
**Версия:** 2.0
**Статус:** Итоговый анализ для планирования развития (ОБНОВЛЕНО: добавлен функционал управления БД)

---

## 🎯 Цель анализа

Сравнить возможности **RAC CLI** (официальная утилита 1С) с текущей реализацией **cluster-service** (Go микросервис через gRPC) для определения gaps и планирования дальнейшего развития.

---

## 📋 Executive Summary

### Функционал мониторинга (read-only)

| Аспект | RAC CLI | ras-grpc-gw (gRPC Gateway) | cluster-service (текущая реализация) |
|--------|---------|---------------------------|-------------------------------------|
| **Протокол** | CLI (text output) | gRPC (protobuf) | REST API → gRPC |
| **Получение кластеров** | ✅ `cluster list` | ✅ `GetClusters` | ✅ `GET /api/v1/clusters` |
| **Краткая инфо о базах** | ✅ `infobase summary list` | ✅ `GetShortInfobases` | ✅ `GET /api/v1/infobases` |
| **Детальная инфо о базе** | ✅ `infobase info --infobase=<uuid>` | ❌ НЕТ метода | ❌ НЕТ реализации |
| **Мониторинг сессий** | ✅ `session list` | ✅ `GetSessions` | ❌ НЕТ (Phase 2) |
| **Детали СУБД** | ✅ dbms, db-server, db-name | ❌ Только UUID, Name | ❌ Поля есть, НЕ заполнены |

### Функционал управления (write operations)

| Аспект | RAC CLI | ras-grpc-gw (gRPC Gateway) | cluster-service (текущая реализация) |
|--------|---------|---------------------------|-------------------------------------|
| **Создание базы** | ✅ `infobase create` | ❌ НЕТ метода | ❌ НЕТ реализации |
| **Изменение базы** | ✅ `infobase update` | ❌ НЕТ метода | ❌ НЕТ реализации |
| **Удаление базы** | ✅ `infobase drop` | ❌ НЕТ метода | ❌ НЕТ реализации |
| **Блокировка сессий** | ✅ `sessions-deny=on` | ❌ НЕТ метода | ❌ НЕТ реализации |
| **Блокировка рег. заданий** | ✅ `scheduled-jobs-deny=on` | ❌ НЕТ метода | ❌ НЕТ реализации |
| **Production ready** | ✅ Да (стабильная) | ⚠️ ALPHA (форк v1.0.0-cc) | ✅ Phase 1 завершена |

**Ключевой вывод:**
1. **GAP-1 (КРИТИЧНО):** cluster-service реализует **минимальный read-only** функционал, но **НЕ получает детальную информацию** о базах (DBMS, DBServer, DBName)
2. **GAP-4 (БЛОКИРУЮЩИЙ для CommandCenter1C):** Полностью **ОТСУТСТВУЕТ функционал управления** информационными базами (создание/изменение/удаление), который критичен для централизованного администрирования 700+ баз

---

## 📊 Детальное сравнение

### 1. Получение списка кластеров

#### RAC CLI
```bash
rac cluster list localhost:1545
```

**Вывод:**
```
cluster                : e3b0c442-98fc-1c14-b39f-92d1282048c0
name                   : Local cluster
host                   : localhost
port                   : 1541
```

#### ras-grpc-gw (gRPC)
```protobuf
service ClustersService {
  rpc GetClusters(GetClustersRequest) returns (GetClustersResponse);
}
```

**Protobuf response:**
```protobuf
message GetClustersResponse {
  repeated ClusterInfo clusters = 1;
}

message ClusterInfo {
  string cluster_id = 1;
  string name = 2;
  string host = 3;
  int32 port = 4;
}
```

#### cluster-service (REST API)
```bash
GET /api/v1/clusters?server=localhost:1545
```

**JSON response:**
```json
{
  "clusters": [
    {
      "uuid": "e3b0c442-98fc-1c14-b39f-92d1282048c0",
      "name": "Local cluster",
      "host": "localhost",
      "port": 1541
    }
  ]
}
```

**Статус:** ✅ **ПОЛНАЯ ЭКВИВАЛЕНТНОСТЬ** - все три метода возвращают одинаковую информацию.

---

### 2. Получение списка информационных баз

#### RAC CLI - Краткая информация
```bash
rac infobase summary list --cluster=<uuid> localhost:1545
```

**Вывод:**
```
infobase               : e94fc632-f38d-4866-8c39-3e98a6341c88
name                   : dev
infobase               : f21ab419-82c7-4d5a-9c2f-1e7b3a4d5c6e
name                   : delans_unf
```

**Поля:** Только `infobase` (UUID) и `name`.

#### RAC CLI - Детальная информация (КРИТИЧНО!)
```bash
rac infobase info \
  --cluster=<cluster-uuid> \
  --infobase=<infobase-uuid> \
  --cluster-user=admin \
  --cluster-pwd=password \
  localhost:1545
```

**Вывод (полные данные):**
```
infobase               : e94fc632-f38d-4866-8c39-3e98a6341c88
name                   : dev
dbms                   : MSSQLServer
db-server              : localhost
db-name                : dev_db
db-user                : sa
security-level         : 0
locale                 : ru_RU
date-offset            : 2000
scheduled-jobs-deny    : off
sessions-deny          : off
```

**Критичные поля для CommandCenter1C:**
- `dbms` - СУБД (MSSQLServer, PostgreSQL, IBMDb2, OracleDatabase)
- `db-server` - SQL сервер
- `db-name` - имя базы в SQL
- `db-user` - пользователь БД
- `security-level` - уровень защиты (0-3)

#### ras-grpc-gw (gRPC)

**Доступные методы:**
```protobuf
service InfobasesService {
  rpc GetShortInfobases(GetShortInfobasesRequest) returns (GetShortInfobasesResponse);
  rpc GetInfobaseSessions(GetInfobaseSessionsRequest) returns (GetInfobaseSessionsResponse);
}
```

**⚠️ КРИТИЧНЫЙ GAP:** Нет метода `GetInfobaseDetails` или `GetFullInfobase` для получения детальной информации!

**GetShortInfobases response:**
```protobuf
message InfobaseInfo {
  string uuid = 1;
  string name = 2;
  string descr = 3;  // description (опционально)
}
```

**Возвращает:** Только UUID, Name, Description.
**НЕ возвращает:** DBMS, DBServer, DBName, SecurityLevel.

#### cluster-service (текущая реализация)

**Модель данных (models/infobase.go):**
```go
type Infobase struct {
    UUID     string `json:"uuid"`
    Name     string `json:"name"`
    DBMS     string `json:"dbms"`      // ❌ НЕ ЗАПОЛНЯЕТСЯ
    DBServer string `json:"db_server"` // ❌ НЕ ЗАПОЛНЯЕТСЯ
    DBName   string `json:"db_name"`   // ❌ НЕ ЗАПОЛНЯЕТСЯ
}
```

**Сервисный слой (service/monitoring.go:78-133):**
```go
func (s *MonitoringService) GetInfobases(...) ([]models.Infobase, error) {
    // Вызывает gRPC метод GetShortInfobases
    resp, err := client.GetShortInfobases(ctx, req)

    // Создает модель
    for _, ib := range resp.Sessions {
        infobases = append(infobases, models.Infobase{
            UUID: ib.Uuid,
            Name: ib.Name,
            DBMS:     "",  // ❌ ПУСТОЕ ПОЛЕ
            DBServer: "",  // ❌ ПУСТОЕ ПОЛЕ
            DBName:   "",  // ❌ ПУСТОЕ ПОЛЕ
        })
    }
}
```

**API Response (фактический):**
```json
{
  "infobases": [
    {
      "uuid": "e94fc632-f38d-4866-8c39-3e98a6341c88",
      "name": "dev",
      "dbms": "",         // ❌ ПУСТО
      "db_server": "",    // ❌ ПУСТО
      "db_name": ""       // ❌ ПУСТО
    }
  ]
}
```

**API Response (в README документации - НЕВЕРНО!):**
```json
{
  "infobases": [
    {
      "uuid": "e94fc632-f38d-4866-8c39-3e98a6341c88",
      "name": "dev",
      "dbms": "MSSQLServer",      // ❌ ФЕЙК - не возвращается реально
      "db_server": "localhost",   // ❌ ФЕЙК - не возвращается реально
      "db_name": "dev_db"         // ❌ ФЕЙК - не возвращается реально
    }
  ]
}
```

**Статус:** ❌ **КРИТИЧНЫЙ GAP** - документация противоречит реализации. Детальные данные НЕ возвращаются.

---

### 3. Мониторинг активных сессий

#### RAC CLI
```bash
rac session list --cluster=<uuid> localhost:1545
```

**Вывод:**
```
session                : 12345
infobase               : e94fc632-f38d-4866-8c39-3e98a6341c88
user-name              : admin
app-id                 : 1CV8C
started-at             : 2025-11-01T10:30:00
last-active-at         : 2025-11-01T10:45:00
```

#### ras-grpc-gw (gRPC)
```protobuf
service SessionsService {
  rpc GetSessions(GetSessionsRequest) returns (GetSessionsResponse);
}
```

**✅ Метод СУЩЕСТВУЕТ** в ras-grpc-gw.

#### cluster-service (текущая реализация)

**API Endpoint:**
```bash
GET /api/v1/sessions?server=localhost:1545&cluster=<uuid>
```

**Статус:** ❌ **НЕ РЕАЛИЗОВАНО** (запланировано на Phase 2 по roadmap).

---

### 4. Управление информационными базами (КРИТИЧНЫЙ ФУНКЦИОНАЛ!)

#### RAC CLI - Создание базы

```bash
rac infobase create \
  --cluster=<cluster-uuid> \
  --cluster-user=admin \
  --cluster-pwd=password \
  --name="NewDatabase" \
  --dbms=MSSQLServer \
  --db-server=localhost \
  --db-name=new_database_db \
  --db-user=sa \
  --db-pwd=db_password \
  --descr="Новая база данных" \
  --locale=ru_RU \
  --date-offset=2000 \
  --security-level=0 \
  --create-database \
  localhost:1545
```

**Параметры:**
- `--name` - имя информационной базы (обязательно)
- `--dbms` - тип СУБД: MSSQLServer | PostgreSQL | IBMDB2 | OracleDatabase (обязательно)
- `--db-server` - адрес SQL сервера (обязательно)
- `--db-name` - имя базы данных в SQL (обязательно)
- `--db-user` - пользователь БД
- `--db-pwd` - пароль БД
- `--create-database` - создать БД при создании info

base (иначе БД должна существовать)
- `--security-level` - уровень безопасности (0-3)
- `--scheduled-jobs-deny` - блокировка регламентных заданий (on | off)
- `--license-distribution` - выдача лицензий (allow | deny)

**Вывод при успехе:**
```
infobase               : f3e9a42b-5c7d-4f9a-a1b2-3e4d5c6f7a8b
name                   : NewDatabase
```

#### RAC CLI - Изменение базы

```bash
rac infobase update \
  --cluster=<cluster-uuid> \
  --cluster-user=admin \
  --cluster-pwd=password \
  --infobase=<infobase-uuid> \
  --sessions-deny=on \
  --denied-from="2025-11-01T00:00:00" \
  --denied-to="2025-11-01T23:59:59" \
  --denied-message="Профилактические работы" \
  --scheduled-jobs-deny=on \
  localhost:1545
```

**Параметры (опциональные):**
- `--sessions-deny` - блокировка сеансов (on | off)
- `--denied-from` / `--denied-to` - интервал блокировки сеансов
- `--denied-message` - сообщение при попытке входа
- `--permission-code` - код разрешения для обхода блокировки
- `--scheduled-jobs-deny` - блокировка регламентных заданий
- `--dbms`, `--db-server`, `--db-name` - можно менять параметры БД
- `--security-profile-name` - профиль безопасности

#### RAC CLI - Удаление базы

```bash
rac infobase drop \
  --cluster=<cluster-uuid> \
  --cluster-user=admin \
  --cluster-pwd=password \
  --infobase=<infobase-uuid> \
  --drop-database \
  localhost:1545
```

**Параметры:**
- `--drop-database` - удалить БД вместе с информационной базой (опасно!)
- `--clear-database` - очистить БД, но не удалять (сохранить структуру)
- Без флагов - удалить только регистрацию в кластере (БД остается)

#### ras-grpc-gw (gRPC)

**❌ ПОЛНОЕ ОТСУТСТВИЕ функционала управления**

Upstream проект `v8platform/ras-grpc-gw` не реализовал **ни одного** метода для управления информационными базами:
- ❌ Нет `CreateInfobase`
- ❌ Нет `UpdateInfobase`
- ❌ Нет `DropInfobase`
- ❌ Нет `RegisterInfobase`
- ❌ Нет `UnregisterInfobase`

**Причина:** Upstream проект в ALPHA статусе, фокус только на мониторинге (read-only).

#### cluster-service (текущая реализация)

**❌ ПОЛНОЕ ОТСУТСТВИЕ API для управления**

Текущая реализация не предоставляет **ни одного** endpoint для управления:
- ❌ Нет `POST /api/v1/infobases` (создание)
- ❌ Нет `PUT /api/v1/infobases/{uuid}` (изменение)
- ❌ Нет `DELETE /api/v1/infobases/{uuid}` (удаление)
- ❌ Нет `POST /api/v1/infobases/{uuid}/lock` (блокировка сеансов)
- ❌ Нет `POST /api/v1/infobases/{uuid}/unlock` (разблокировка сеансов)

**Статус:** ❌ **БЛОКИРУЮЩИЙ GAP** для CommandCenter1C - невозможно централизованно управлять 700+ базами.

---

### 5. Блокировка и управление доступом

#### RAC CLI - Блокировка сеансов

```bash
# Включить блокировку
rac infobase update \
  --cluster=<cluster-uuid> \
  --infobase=<infobase-uuid> \
  --sessions-deny=on \
  --denied-from="2025-11-01T10:00:00" \
  --denied-to="2025-11-01T12:00:00" \
  --denied-message="Обновление системы с 10:00 до 12:00" \
  --permission-code="admin123" \
  localhost:1545
```

**Use case:** Плановое обновление конфигурации без завершения активных сеансов пользователей.

#### RAC CLI - Блокировка регламентных заданий

```bash
# Отключить регламентные задания (например, для массового обновления данных)
rac infobase update \
  --cluster=<cluster-uuid> \
  --infobase=<infobase-uuid> \
  --scheduled-jobs-deny=on \
  localhost:1545
```

**Use case:** Остановка фоновых заданий перед выполнением массовых операций через OData.

#### ras-grpc-gw & cluster-service

**Статус:** ❌ НЕТ реализации

---

## 🔍 Gap Analysis

### Критичные gaps (блокируют использование в CommandCenter1C)

| Gap # | Описание | Влияние | Приоритет |
|-------|----------|---------|-----------|
| **GAP-1** | **Нет получения детальной информации о базах** | **КРИТИЧНО** | 🔴 P0 |
| Детали | cluster-service не получает DBMS, DBServer, DBName | Невозможно определить тип СУБД и строку подключения | Must-have для Phase 2 |
| Причина | ras-grpc-gw не имеет метода `GetInfobaseDetails` | Форк не реализовал детальное получение данных | Требует доработки форка |

| Gap # | Описание | Влияние | Приоритет |
|-------|----------|---------|-----------|
| **GAP-4** | **❌ ПОЛНОЕ ОТСУТСТВИЕ функционала управления БД** | **БЛОКИРУЮЩИЙ** | 🔴 P0 |
| Детали | Нет создания/изменения/удаления информационных баз | **Невозможно централизованное администрирование 700+ баз** | **ОБЯЗАТЕЛЬНО для CommandCenter1C** |
| Причина | ras-grpc-gw не имеет методов `CreateInfobase`, `UpdateInfobase`, `DropInfobase` | Upstream проект ALPHA, фокус только на мониторинге | **Критичная доработка форка** |
| Требуется | 5 новых gRPC методов + 8 REST API endpoints | - Создание базы<br>- Изменение параметров<br>- Удаление базы<br>- Блокировка сеансов<br>- Блокировка рег. заданий | **Phase 3+** (15-20 дней разработки) |

| Gap # | Описание | Влияние | Приоритет |
|-------|----------|---------|-----------|
| **GAP-2** | **Нет мониторинга активных сессий** | Средний приоритет | 🟡 P1 |
| Детали | Endpoint `/api/v1/sessions` не реализован | Нет real-time мониторинга пользователей | Nice-to-have для Phase 2 |
| Причина | ras-grpc-gw имеет метод `GetSessions`, но cluster-service не вызывает | Просто не добавили API handler | Легко исправить (2 дня) |

### Некритичные gaps (функциональность для будущего)

| Gap # | Описание | Влияние | Приоритет |
|-------|----------|---------|-----------|
| **GAP-3** | **Нет управления сессиями** (terminate session) | Низкий | 🟢 P2 |
| **GAP-5** | **Нет конфигурации кластера** (настройки) | Низкий | 🟢 P3 |
| **GAP-6** | **Нет управления блокировками БД** (db locks) | Низкий | 🟢 P3 |

---

## 📐 Архитектурные выводы

### Текущая архитектура (упрощенная)

```
┌─────────────────────────────────────────────────────────────────┐
│                         cluster-service                         │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │   REST API                                                │  │
│  │   GET /clusters  → GetClusters()   ✅ Полные данные      │  │
│  │   GET /infobases → GetInfobases()  ❌ Только UUID, Name  │  │
│  │   GET /sessions  → ❌ НЕ РЕАЛИЗОВАНО                      │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│                           │                                     │
│  ┌────────────────────────▼─────────────────────────────────┐  │
│  │   MonitoringService (gRPC wrapper)                        │  │
│  │   - GetClusters()      → gRPC GetClusters ✅              │  │
│  │   - GetInfobases()     → gRPC GetShortInfobases ⚠️        │  │
│  │   - GetSessions()      → ❌ НЕ ВЫЗЫВАЕТСЯ                 │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │ gRPC
               ┌────────────▼─────────────┐
               │   ras-grpc-gw (форк)     │
               │                          │
               │   GetClusters         ✅ │
               │   GetShortInfobases   ✅ │
               │   GetInfobaseDetails  ❌ │ ← НЕТ МЕТОДА!
               │   GetSessions         ✅ │
               └────────────┬─────────────┘
                            │ RAS Binary Protocol
                    ┌───────▼────────┐
                    │   RAS Server   │
                    │   Port: 1545   │
                    └────────────────┘
```

### Проблема в цепочке вызовов

**Запрос детальной информации о базе:**

```
Orchestrator → cluster-service → ras-grpc-gw → RAS Server
     ↓              ↓                  ↓            ↓
Нужны DBMS,    Вызывает        НЕТ метода!   Может вернуть
DBServer,      GetShortInfobases  для детальных   через rac CLI
DBName         (короткая инфа)    данных          `infobase info`
```

**Root Cause:** ras-grpc-gw (даже форк v1.0.0-cc) не реализовал метод получения **детальной** информации о базе, хотя RAS протокол это поддерживает (есть в RAC CLI как `infobase info`).

---

## 🛠️ Решения проблемы GAP-1 (детальная информация)

### Вариант 1: Доработка форка ras-grpc-gw (Recommended)

**Что нужно:**
1. Добавить protobuf метод:
   ```protobuf
   service InfobasesService {
     rpc GetInfobaseDetails(GetInfobaseDetailsRequest) returns (InfobaseDetailsResponse);
   }

   message InfobaseDetailsResponse {
     string uuid = 1;
     string name = 2;
     string dbms = 3;           // MSSQLServer, PostgreSQL, etc
     string db_server = 4;
     string db_name = 5;
     string db_user = 6;
     int32 security_level = 7;
     string locale = 8;
     // ... остальные поля
   }
   ```

2. Реализовать метод в форке (Go код):
   ```go
   func (s *InfobasesService) GetInfobaseDetails(ctx context.Context, req *pb.GetInfobaseDetailsRequest) (*pb.InfobaseDetailsResponse, error) {
       // Вызвать RAS Binary Protocol: infobase info
       // Парсить результат
       // Вернуть полные данные
   }
   ```

3. Обновить cluster-service для использования нового метода:
   ```go
   func (s *MonitoringService) GetInfobases(...) ([]models.Infobase, error) {
       // Получить короткий список
       shortList, _ := client.GetShortInfobases(ctx, req)

       // ДЛЯ КАЖДОЙ базы получить детальную информацию
       var infobases []models.Infobase
       for _, ib := range shortList.Infobases {
           details, _ := client.GetInfobaseDetails(ctx, &pb.GetInfobaseDetailsRequest{
               ClusterId: clusterId,
               InfobaseId: ib.Uuid,
           })

           infobases = append(infobases, models.Infobase{
               UUID:     details.Uuid,
               Name:     details.Name,
               DBMS:     details.Dbms,        // ✅ ЗАПОЛНЕНО
               DBServer: details.DbServer,    // ✅ ЗАПОЛНЕНО
               DBName:   details.DbName,      // ✅ ЗАПОЛНЕНО
           })
       }
   }
   ```

**Плюсы:**
- ✅ Чистое gRPC решение (без exec)
- ✅ Типизированные данные (protobuf)
- ✅ Высокая производительность
- ✅ Полный контроль над форком

**Минусы:**
- ⏱️ Требует времени на разработку (5-7 дней)
- 🧪 Требует тестирования с реальным RAS
- 🔄 Нужно поддерживать форк (синхронизация с upstream)

**Оценка:** 5-7 дней разработки + тестирование

---

### Вариант 2: Fallback на RAC CLI (Quick Workaround)

**Что нужно:**
1. Добавить в cluster-service вызов RAC CLI:
   ```go
   func (s *MonitoringService) GetInfobaseDetails(clusterID, infobaseID string) (*models.InfobaseDetails, error) {
       cmd := exec.Command("rac", "infobase", "info",
           "--cluster=" + clusterID,
           "--infobase=" + infobaseID,
           "localhost:1545")

       output, err := cmd.CombinedOutput()
       if err != nil {
           return nil, err
       }

       // Парсить текстовый вывод RAC
       details := parseRACOutput(string(output))
       return details, nil
   }
   ```

2. Комбинировать gRPC + RAC CLI:
   ```go
   func (s *MonitoringService) GetInfobases(...) ([]models.Infobase, error) {
       // 1. Получить короткий список через gRPC (быстро)
       shortList, _ := s.grpcClient.GetShortInfobases(ctx, req)

       // 2. ДЛЯ КАЖДОЙ базы вызвать RAC CLI (медленно)
       var infobases []models.Infobase
       for _, ib := range shortList.Infobases {
           details, _ := s.GetInfobaseDetailsRAC(clusterID, ib.Uuid)

           infobases = append(infobases, models.Infobase{
               UUID:     ib.Uuid,
               Name:     ib.Name,
               DBMS:     details.DBMS,     // ✅ Из RAC CLI
               DBServer: details.DBServer, // ✅ Из RAC CLI
               DBName:   details.DBName,   // ✅ Из RAC CLI
           })
       }
   }
   ```

**Плюсы:**
- ⚡ Быстрая реализация (1-2 дня)
- ✅ Не требует доработки форка
- ✅ Получаем детальные данные сразу

**Минусы:**
- ❌ Смешанный подход (gRPC + exec)
- 🐌 Медленная производительность (700+ баз = 700+ вызовов RAC CLI)
- 🔧 Парсинг текстового вывода (хрупкий код)
- ⚠️ Проблемы безопасности (пароли в CLI параметрах)

**Оценка:** 1-2 дня, но НЕ РЕКОМЕНДУЕТСЯ для production.

---

### Вариант 3: Batch запрос детальных данных (гибридное решение)

**Что нужно:**
1. Добавить в форк ras-grpc-gw метод batch запроса:
   ```protobuf
   service InfobasesService {
     rpc GetInfobaseDetailsBatch(GetInfobaseDetailsBatchRequest) returns (GetInfobaseDetailsBatchResponse);
   }

   message GetInfobaseDetailsBatchRequest {
     string cluster_id = 1;
     repeated string infobase_ids = 2;  // Batch список UUID
   }

   message GetInfobaseDetailsBatchResponse {
     repeated InfobaseDetails infobases = 1;
   }
   ```

2. Реализовать batch обработку:
   ```go
   func (s *InfobasesService) GetInfobaseDetailsBatch(...) {
       var details []*pb.InfobaseDetails
       for _, ibID := range req.InfobaseIds {
           // Вызвать RAS для каждой базы
           detail := s.getInfobaseDetailsFromRAS(req.ClusterId, ibID)
           details = append(details, detail)
       }
       return &pb.GetInfobaseDetailsBatchResponse{Infobases: details}
   }
   ```

3. Использовать в cluster-service:
   ```go
   func (s *MonitoringService) GetInfobases(...) ([]models.Infobase, error) {
       // 1. Получить короткий список
       shortList, _ := s.grpcClient.GetShortInfobases(ctx, req)

       // 2. Собрать UUID
       var uuids []string
       for _, ib := range shortList.Infobases {
           uuids = append(uuids, ib.Uuid)
       }

       // 3. Batch запрос детальных данных
       details, _ := s.grpcClient.GetInfobaseDetailsBatch(ctx, &pb.GetInfobaseDetailsBatchRequest{
           ClusterId: clusterID,
           InfobaseIds: uuids,
       })

       // 4. Объединить данные
       for i, detail := range details.Infobases {
           infobases[i].DBMS = detail.Dbms
           infobases[i].DBServer = detail.DbServer
           infobases[i].DBName = detail.DbName
       }
   }
   ```

**Плюсы:**
- ⚡ Оптимизация: один gRPC вызов вместо N
- ✅ Чистое gRPC решение
- 📊 Возможность batch обработки на стороне форка

**Минусы:**
- ⏱️ Требует больше времени (7-10 дней)
- 🧪 Сложнее тестировать

**Оценка:** 7-10 дней разработки.

---

---

## 🛠️ Решение GAP-4: Управление информационными базами

### Вариант 1: Полная доработка ras-grpc-gw (Рекомендуется для production)

**Что нужно реализовать в форке:**

1. **Protobuf методы** (5 новых методов):
   ```protobuf
   service InfobasesService {
     rpc CreateInfobase(CreateInfobaseRequest) returns (CreateInfobaseResponse);
     rpc UpdateInfobase(UpdateInfobaseRequest) returns (UpdateInfobaseResponse);
     rpc DropInfobase(DropInfobaseRequest) returns (DropInfobaseResponse);
     rpc LockInfobase(LockInfobaseRequest) returns (LockInfobaseResponse);     // sessions-deny + scheduled-jobs-deny
     rpc UnlockInfobase(UnlockInfobaseRequest) returns (UnlockInfobaseResponse);
   }
   ```

2. **REST API в cluster-service** (8 endpoints):
   ```
   POST   /api/v1/infobases                    - создание базы
   PUT    /api/v1/infobases/{uuid}             - изменение параметров
   DELETE /api/v1/infobases/{uuid}             - удаление базы
   POST   /api/v1/infobases/{uuid}/lock        - блокировка сеансов
   POST   /api/v1/infobases/{uuid}/unlock      - разблокировка
   POST   /api/v1/infobases/{uuid}/lock-jobs   - блокировка рег. заданий
   POST   /api/v1/infobases/{uuid}/unlock-jobs - разблокировка рег. заданий
   PUT    /api/v1/infobases/{uuid}/params      - изменение параметров БД (dbms, db-server, etc)
   ```

**Трудозатраты:** 15-20 дней
- 7-10 дней: доработка форка ras-grpc-gw
- 5-7 дней: реализация REST API в cluster-service
- 3-5 дней: тестирование с реальным RAS

**Плюсы:**
- ✅ Полноценное gRPC решение (чистая архитектура)
- ✅ Централизованное управление через REST API
- ✅ Типизированные данные (protobuf)
- ✅ Production-ready решение

**Минусы:**
- ⏱️ Длительная разработка (15-20 дней)
- 🧪 Требует extensive тестирования
- 🔄 Поддержка форка

---

### Вариант 2: Гибридный подход (Quick workaround)

**Идея:** Оставить gRPC для мониторинга, использовать RAC CLI для управления.

**Реализация:**
- cluster-service использует gRPC для read-only операций (GET)
- Для write операций (POST/PUT/DELETE) - прямой вызов RAC CLI через exec.Command

**Код примера:**
```go
func (s *MonitoringService) CreateInfobase(req *CreateInfobaseRequest) error {
    cmd := exec.Command("rac", "infobase", "create",
        "--cluster=" + req.ClusterID,
        "--name=" + req.Name,
        "--dbms=" + req.DBMS,
        "--db-server=" + req.DBServer,
        "--db-name=" + req.DBName,
        // ... остальные параметры
        "localhost:1545")

    output, err := cmd.CombinedOutput()
    if err != nil {
        return fmt.Errorf("RAC create failed: %w", err)
    }

    // Парсить вывод RAC для получения UUID новой базы
    infobaseUUID := parseRACCreateOutput(string(output))
    return nil
}
```

**Трудозатраты:** 5-7 дней

**Плюсы:**
- ⚡ Быстрая реализация
- ✅ Не требует доработки форка
- ✅ Полный функционал RAC доступен сразу

**Минусы:**
- ❌ Смешанный подход (gRPC + exec)
- 🐌 Медленная производительность для массовых операций
- 🔧 Парсинг текстового вывода RAC
- ⚠️ Проблемы безопасности (пароли в CLI)

---

### Вариант 3: Использовать batch-service

**Идея:** НЕ добавлять управление БД в cluster-service, вынести в отдельный `admin-service`.

**Архитектура:**
```
cluster-service  → Мониторинг (read-only, gRPC)
admin-service    → Управление БД (write, RAC CLI fallback)
batch-service    → Установка расширений (subprocess)
```

**Плюсы:**
- ✅ Разделение ответственности (SRP)
- ✅ cluster-service остается легковесным
- ✅ admin-service может эволюционировать независимо

**Минусы:**
- 🏗️ Дополнительный сервис (усложнение архитектуры)
- 🔄 Требует координации между сервисами

---

## 📋 Рекомендации

### Краткосрочная перспектива (Phase 2, Week 6-8)

**Приоритет 🔴 P0: Решить GAP-1 (детальная информация о базах)**

**Рекомендуемое решение:** **Вариант 1** (доработка форка ras-grpc-gw)

**План действий:**
1. **Sprint 2.1: Доработка форка** (5 дней)
   - [ ] Добавить protobuf метод `GetInfobaseDetails`
   - [ ] Реализовать вызов RAS Binary Protocol
   - [ ] Unit тесты для нового метода
   - [ ] Обновить форк до v1.1.0-cc

2. **Sprint 2.2: Интеграция в cluster-service** (3 дня)
   - [ ] Обновить gRPC клиента
   - [ ] Реализовать вызов `GetInfobaseDetails` в MonitoringService
   - [ ] Обновить модели для заполнения DBMS/DBServer/DBName
   - [ ] Unit тесты

3. **Sprint 2.3: E2E тестирование** (2 дня)
   - [ ] Тесты с реальным RAS
   - [ ] Проверка производительности (700+ баз)
   - [ ] Обновление документации

**Итого:** 10 дней (вписывается в Phase 2)

---

**Приоритет 🟡 P1: Реализовать GAP-2 (мониторинг сессий)**

**Решение:** Легко - ras-grpc-gw уже имеет метод `GetSessions`, нужно только добавить API handler в cluster-service.

**План действий:**
1. **Sprint 2.4: Sessions endpoint** (2 дня)
   - [ ] Добавить модель `Session`
   - [ ] Реализовать `MonitoringService.GetSessions()`
   - [ ] Добавить API handler `GET /api/v1/sessions`
   - [ ] Unit + integration тесты

**Итого:** 2 дня

---

### Долгосрочная перспектива (Phase 3+, Week 11-16)

**Приоритет 🔴 P0: Решить GAP-4 (управление информационными базами)**

**Рекомендуемое решение:** **Вариант 1** (полная доработка ras-grpc-gw)

**Обоснование:**
- CommandCenter1C требует централизованное управление 700+ базами
- Гибридный подход (Вариант 2) не масштабируется для массовых операций
- Чистое gRPC решение обеспечивает лучшую производительность

**План действий:**
1. **Sprint 3.1: Protobuf schema design** (3 дня)
   - [ ] Спроектировать protobuf schema для CreateInfobase
   - [ ] Спроектировать schema для UpdateInfobase / DropInfobase
   - [ ] Спроектировать schema для LockInfobase / UnlockInfobase
   - [ ] Code review архитектуры

2. **Sprint 3.2: Доработка форка ras-grpc-gw** (7-10 дней)
   - [ ] Реализовать CreateInfobase в форке
   - [ ] Реализовать UpdateInfobase в форке
   - [ ] Реализовать DropInfobase в форке
   - [ ] Реализовать LockInfobase / UnlockInfobase
   - [ ] Unit тесты (coverage > 70%)
   - [ ] Обновить форк до v1.2.0-cc

3. **Sprint 3.3: Интеграция в cluster-service** (5-7 дней)
   - [ ] Обновить gRPC клиента
   - [ ] Реализовать REST API handlers (POST/PUT/DELETE)
   - [ ] Валидация входных данных
   - [ ] Error handling для destructive операций
   - [ ] Unit + integration тесты

4. **Sprint 3.4: E2E тестирование и безопасность** (3-5 дней)
   - [ ] E2E тесты с реальным RAS
   - [ ] Security audit (нет утечек паролей)
   - [ ] Тесты разрушительных операций (drop database)
   - [ ] Load testing (создание 100+ баз параллельно)
   - [ ] Обновление документации

**Итого:** 18-25 дней (вписывается в Phase 3)

**Use cases для проверки:**
- [ ] Создание новой базы через REST API
- [ ] Изменение параметров БД (db-server, db-name)
- [ ] Блокировка сеансов на 700+ базах одновременно (для обновления)
- [ ] Удаление тестовых баз после миграции

---

### Долгосрочная перспектива (Phase 4+)

**Приоритет 🟢 P2-P3: Nice-to-have функции**
- GAP-3: Управление сессиями (terminate)
- GAP-5: Конфигурация кластера
- GAP-6: Управление блокировками БД

Эти функции не критичны для MVP/Balanced подхода, можно отложить на Phase 4 или после production deployment.

---

## 📊 Влияние на CommandCenter1C roadmap

### Текущий roadmap (Balanced Approach)

**Phase 2: Extended Functionality (Week 7-10)** - 4 недели

Если добавить решение GAP-1 и GAP-2:

**Обновленный Phase 2:**
- Week 6-7: Доработка форка (GAP-1)
- Week 7-8: Интеграция в cluster-service (GAP-1)
- Week 8-9: Sessions endpoint (GAP-2)
- Week 9-10: Advanced features (connection pooling, circuit breaker)

**Итого:** Укладываемся в изначальные 4 недели Phase 2 (с небольшим overlap).

---

## 🎯 Критерии успеха

После решения GAP-1 и GAP-2, cluster-service должен:

| Критерий | До (текущая реализация) | После (обновленная реализация) |
|----------|------------------------|--------------------------------|
| **Получение кластеров** | ✅ Полные данные | ✅ Полные данные (без изменений) |
| **Получение баз данных** | ❌ Только UUID, Name | ✅ UUID, Name, **DBMS, DBServer, DBName** |
| **Мониторинг сессий** | ❌ НЕТ | ✅ Список активных сессий |
| **API эндпоинты** | 2 (clusters, infobases) | 3 (clusters, infobases, sessions) |
| **Production readiness** | ⚠️ Не хватает детальных данных | ✅ Готов для CommandCenter1C |

---

## 📚 Справочные материалы

### Документация 1С (архив)
- `docs/archive/research/ras_rac/1C_RAC_COMMANDS.md` - полный список RAC команд
- `docs/archive/research/ras_rac/1C_RAS_GRPC_SOLUTION.md` - описание gRPC подхода
- `docs/archive/research/ras_rac/1C_RAC_SECURITY.md` - ограничения безопасности RAC CLI
- `docs/1C_ADMINISTRATION_GUIDE.md` - практическое руководство

### Код cluster-service
- `go-services/cluster-service/README.md` - документация сервиса
- `go-services/cluster-service/internal/models/infobase.go:6-14` - модель Infobase с неиспользуемыми полями
- `go-services/cluster-service/internal/service/monitoring.go:78-133` - GetInfobases реализация

### Форк ras-grpc-gw
- Repository: https://github.com/defin85/ras-grpc-gw
- Current version: v1.0.0-cc
- Upstream: https://github.com/v8platform/ras-grpc-gw

---

## ✅ Action Items

### Для Architect Agent (немедленно)
- [ ] Исследовать RAS Binary Protocol для `infobase info` команды
- [ ] Спроектировать protobuf schema для `GetInfobaseDetails`
- [ ] Оценить трудозатраты на доработку форка

### Для Coder Agent (после утверждения плана)
- [ ] Реализовать `GetInfobaseDetails` в форке ras-grpc-gw
- [ ] Обновить cluster-service для использования нового метода
- [ ] Реализовать `GET /api/v1/sessions` endpoint

### Для Reviewer Agent (после реализации)
- [ ] Code review доработок форка
- [ ] Code review обновлений cluster-service
- [ ] Проверка безопасности (нет утечек паролей в логах)

### Для Tester Agent (после code review)
- [ ] Unit тесты для новых методов
- [ ] Integration тесты с реальным RAS
- [ ] Performance тесты (700+ баз)

---

**Версия:** 2.0
**Дата:** 2025-11-01
**Автор:** Architect Team (AI Analysis)
**Статус:** Итоговый анализ для планирования Phase 2-3 (включая функционал управления БД)
