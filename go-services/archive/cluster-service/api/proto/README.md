# Protobuf API для cluster-service

## Обзор

Этот каталог содержит Protocol Buffers (protobuf) схемы для gRPC API сервиса `cluster-service`.

**Назначение:** Управление информационными базами 1С через gRPC интерфейс.

## Файлы

- `infobase_management.proto` - Управление информационными базами (создание, изменение, удаление, блокировка)

## Генерация Go кода

### Предварительные требования

#### 1. Установить protoc compiler

**Windows (через chocolatey):**
```bash
choco install protoc
```

**Windows (вручную):**
1. Скачать с https://github.com/protocolbuffers/protobuf/releases
2. Распаковать в `C:\protoc\`
3. Добавить `C:\protoc\bin` в PATH

**Linux/macOS:**
```bash
# Ubuntu/Debian
sudo apt install protobuf-compiler

# macOS
brew install protobuf
```

#### 2. Установить Go плагины

```bash
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
```

Убедитесь что `$GOPATH/bin` (или `$HOME/go/bin`) добавлен в PATH.

### Генерация кода

**Из корня cluster-service:**
```bash
cd go-services/cluster-service

# Генерация Go кода
make proto-gen
```

**Или вручную:**
```bash
protoc --go_out=. --go_opt=paths=source_relative \
       --go-grpc_out=. --go-grpc_opt=paths=source_relative \
       api/proto/infobase_management.proto
```

**Результат:**
- `api/proto/infobase_management.pb.go` - Go структуры для сообщений
- `api/proto/infobase_management_grpc.pb.go` - gRPC клиент и сервер

## ⚠️ Безопасность (ОБЯЗАТЕЛЬНО для Production)

### TLS шифрование (КРИТИЧНО!)

**ВНИМАНИЕ:** Поля `*_password` (пароли БД и кластера) передаются в plaintext через gRPC!

**ОБЯЗАТЕЛЬНО** использовать TLS в production для защиты паролей.

#### Настройка TLS на сервере (ras-grpc-gw)

```go
package main

import (
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials"
)

func main() {
    // Загрузить TLS сертификаты
    creds, err := credentials.NewServerTLSFromFile(
        "/path/to/server.crt",  // Сертификат
        "/path/to/server.key",  // Приватный ключ
    )
    if err != nil {
        log.Fatalf("Failed to load TLS credentials: %v", err)
    }

    // Создать gRPC сервер с TLS
    grpcServer := grpc.NewServer(grpc.Creds(creds))
    pb.RegisterInfobaseManagementServiceServer(grpcServer, &service{})

    log.Println("gRPC server with TLS running on :50051")
    grpcServer.Serve(lis)
}
```

#### Настройка TLS на клиенте (cluster-service)

```go
package main

import (
    "crypto/tls"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials"
)

func main() {
    // TLS конфигурация
    tlsConfig := &tls.Config{
        InsecureSkipVerify: false,  // В production: ОБЯЗАТЕЛЬНО false!
    }
    creds := credentials.NewTLS(tlsConfig)

    // Подключение к gRPC серверу с TLS
    conn, err := grpc.Dial(
        "ras-grpc-gw:50051",
        grpc.WithTransportCredentials(creds),
    )
    if err != nil {
        log.Fatalf("Failed to connect: %v", err)
    }
    defer conn.Close()

    client := pb.NewInfobaseManagementServiceClient(conn)
}
```

#### Генерация самоподписанных сертификатов (для тестирования)

```bash
# НЕ используйте в production! Только для dev/test
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes
```

#### Production checklist

- [ ] TLS сертификаты от доверенного CA (Let's Encrypt, DigiCert)
- [ ] `InsecureSkipVerify = false` на клиенте
- [ ] Сертификаты регулярно обновляются (автоматизация через cert-manager)
- [ ] mTLS (mutual TLS) для дополнительной безопасности

См. детальную инструкцию: [TLS_SETUP.md](../../docs/TLS_SETUP.md)

### Серверная валидация

Все gRPC методы **ОБЯЗАНЫ** выполнять валидацию входных данных:

- `CreateInfobase`: Проверка name (не пустое), dbms (не UNSPECIFIED), db_server, db_name
- `UpdateInfobase`: Проверка интервала блокировки (denied_from < denied_to)
- `LockInfobase`: Хотя бы один тип блокировки (sessions_deny или scheduled_jobs_deny)
- `DropInfobase`: drop_mode не UNSPECIFIED

См. детали: [VALIDATION_GUIDE.md](../../docs/VALIDATION_GUIDE.md)

### Audit Trail (Обязательно для Production)

**ТРЕБОВАНИЕ:** Все деструктивные операции ОБЯЗАНЫ логироваться в audit log.

#### Критичные операции

- `DropInfobase` с `drop_mode = DROP_MODE_DROP_DATABASE` - удаление БД
- `DropInfobase` с `drop_mode = DROP_MODE_CLEAR_DATABASE` - очистка БД
- `UpdateInfobase` с изменением параметров БД (dbms, db_server, db_name)
- `LockInfobase` на массовые блокировки (>100 баз одновременно)

#### Формат audit log

```json
{
  "timestamp": "2025-11-02T10:30:00Z",
  "operation": "DropInfobase",
  "user": "admin@example.com",
  "cluster_id": "e3b0c442-98fc-1c14-b39f-92d1282048c0",
  "infobase_id": "f3e9a42b-5c7d-4f9a-a1b2-3e4d5c6f7a8b",
  "infobase_name": "production_db",
  "drop_mode": "DROP_MODE_DROP_DATABASE",
  "result": "success",
  "duration_ms": 1234
}
```

#### Реализация (Sprint 3.2)

```go
func (s *InfobaseService) DropInfobase(ctx context.Context, req *pb.DropInfobaseRequest) (*pb.DropInfobaseResponse, error) {
    start := time.Now()

    // Audit log ПЕРЕД выполнением
    auditLog.Info("Starting destructive operation",
        "operation", "DropInfobase",
        "user", getUserFromContext(ctx),
        "cluster_id", req.ClusterId,
        "infobase_id", req.InfobaseId,
        "drop_mode", req.DropMode.String(),
    )

    // Выполнить операцию
    resp, err := s.performDropInfobase(ctx, req)

    // Audit log ПОСЛЕ выполнения
    auditLog.Info("Destructive operation completed",
        "operation", "DropInfobase",
        "result", getResult(err),
        "duration_ms", time.Since(start).Milliseconds(),
    )

    return resp, err
}
```

#### Хранение audit logs

- **Рекомендуется:** Отдельный audit log файл (rotation 30 дней)
- **Production:** Интеграция с ELK Stack (Elasticsearch + Logstash + Kibana)
- **Compliance:** Immutable logs (append-only, нельзя изменить задним числом)

## Использование API

### 1. CreateInfobase

Создание новой информационной базы в кластере 1С.

**Пример:**
```go
import (
    pb "github.com/yourusername/command-center-1c/go-services/cluster-service/api/proto/cluster/v1"
    "google.golang.org/protobuf/types/known/wrapperspb"
)

func createInfobase(client pb.InfobaseManagementServiceClient) error {
    req := &pb.CreateInfobaseRequest{
        ClusterId: "e3b0c442-98fc-1c14-b39f-92d1282048c0",
        Name:      "new_accounting_base",
        Dbms:      pb.DBMSType_DBMS_TYPE_MSSQL_SERVER,
        DbServer:  "localhost",
        DbName:    "accounting_db",
        DbUser:    proto.String("sa"),
        DbPassword: proto.String("SecurePassword123"),  // ТОЛЬКО через TLS!
        CreateDatabase: proto.Bool(true),
        SecurityLevel: pb.SecurityLevel_SECURITY_LEVEL_0.Enum(),
        Locale: proto.String("ru_RU"),
        DateOffset: proto.Int32(2000),
        Description: proto.String("Бухгалтерия предприятия"),
        ScheduledJobsDeny: proto.Bool(false),
    }

    resp, err := client.CreateInfobase(context.Background(), req)
    if err != nil {
        return fmt.Errorf("failed to create infobase: %w", err)
    }

    fmt.Printf("Created infobase: %s (ID: %s)\n", resp.Name, resp.InfobaseId)
    return nil
}
```

### 2. UpdateInfobase

Изменение параметров существующей информационной базы.

**Пример (блокировка сеансов):**
```go
func blockSessions(client pb.InfobaseManagementServiceClient, infobaseID string) error {
    deniedFrom := timestamppb.New(time.Now())
    deniedTo := timestamppb.New(time.Now().Add(2 * time.Hour))

    req := &pb.UpdateInfobaseRequest{
        ClusterId:      "e3b0c442-98fc-1c14-b39f-92d1282048c0",
        InfobaseId:     infobaseID,
        SessionsDeny:   proto.Bool(true),
        DeniedFrom:     deniedFrom,
        DeniedTo:       deniedTo,
        DeniedMessage:  proto.String("Техническое обслуживание до 18:00"),
        PermissionCode: proto.String("admin2024"),
    }

    resp, err := client.UpdateInfobase(context.Background(), req)
    if err != nil {
        return fmt.Errorf("failed to update infobase: %w", err)
    }

    fmt.Printf("Updated infobase: %s\n", resp.Message)
    return nil
}
```

### 3. DropInfobase

Удаление информационной базы из кластера.

**⚠️ ОПАСНАЯ ОПЕРАЦИЯ!**

**Пример (безопасное удаление - БД остается):**
```go
func dropInfobaseSafe(client pb.InfobaseManagementServiceClient, infobaseID string) error {
    // Безопасное удаление: только регистрация в кластере, БД остается
    req := &pb.DropInfobaseRequest{
        ClusterId:   "e3b0c442-...",
        InfobaseId:  infobaseID,
        DropMode:    pb.DropMode_DROP_MODE_UNREGISTER_ONLY,  // БД остается - БЕЗОПАСНО
        ClusterUser: proto.String("admin"),
        ClusterPassword: proto.String("admin_password"),  // ТОЛЬКО через TLS!
    }

    resp, err := client.DropInfobase(context.Background(), req)
    if err != nil {
        return fmt.Errorf("failed to drop infobase: %w", err)
    }

    fmt.Printf("Dropped infobase: %s\n", resp.Message)
    return nil
}
```

**Пример (полное удаление включая БД - ОПАСНО!):**
```go
func dropInfobaseWithDB(client pb.InfobaseManagementServiceClient, infobaseID string) error {
    // ⚠️ ЭТО УДАЛИТ ВСЕ ДАННЫЕ БЕЗ ВОЗМОЖНОСТИ ВОССТАНОВЛЕНИЯ!
    req := &pb.DropInfobaseRequest{
        ClusterId:   "e3b0c442-...",
        InfobaseId:  infobaseID,
        DropMode:    pb.DropMode_DROP_MODE_DROP_DATABASE,  // УДАЛИТ БД! ОПАСНО!
        ClusterUser: proto.String("admin"),
        ClusterPassword: proto.String("admin_password"),
    }

    resp, err := client.DropInfobase(context.Background(), req)
    if err != nil {
        return fmt.Errorf("failed to drop infobase: %w", err)
    }

    fmt.Printf("Dropped infobase with database: %s\n", resp.Message)
    return nil
}
```

**Пример (очистка БД без удаления - ОПАСНО!):**
```go
func clearInfobaseDB(client pb.InfobaseManagementServiceClient, infobaseID string) error {
    // ⚠️ Очистит все данные, но сохранит структуру БД
    req := &pb.DropInfobaseRequest{
        ClusterId:   "e3b0c442-...",
        InfobaseId:  infobaseID,
        DropMode:    pb.DropMode_DROP_MODE_CLEAR_DATABASE,  // Очистит БД, сохранит структуру
        ClusterUser: proto.String("admin"),
        ClusterPassword: proto.String("admin_password"),
    }

    resp, err := client.DropInfobase(context.Background(), req)
    if err != nil {
        return fmt.Errorf("failed to clear infobase: %w", err)
    }

    fmt.Printf("Cleared infobase database: %s\n", resp.Message)
    return nil
}
```

### 4. LockInfobase

Блокировка доступа к информационной базе (для технических работ).

**Пример:**
```go
func lockInfobase(client pb.InfobaseManagementServiceClient, infobaseID string) error {
    deniedFrom := timestamppb.New(time.Now())
    deniedTo := timestamppb.New(time.Now().Add(4 * time.Hour))

    req := &pb.LockInfobaseRequest{
        ClusterId:          "e3b0c442-...",
        InfobaseId:         infobaseID,
        SessionsDeny:       true,  // Блокировать сеансы
        DeniedFrom:         deniedFrom,
        DeniedTo:           deniedTo,
        DeniedMessage:      proto.String("Обновление конфигурации. Вход запрещен до 20:00."),
        PermissionCode:     proto.String("maint2024"),
        ScheduledJobsDeny:  true,  // Блокировать регламентные задания
        ClusterUser:        proto.String("admin"),
        ClusterPassword:    proto.String("admin_password"),
    }

    resp, err := client.LockInfobase(context.Background(), req)
    if err != nil {
        return fmt.Errorf("failed to lock infobase: %w", err)
    }

    fmt.Printf("Locked infobase: %s\n", resp.Message)
    return nil
}
```

### 5. UnlockInfobase

Снятие блокировки с информационной базы.

**Пример:**
```go
func unlockInfobase(client pb.InfobaseManagementServiceClient, infobaseID string) error {
    req := &pb.UnlockInfobaseRequest{
        ClusterId:            "e3b0c442-...",
        InfobaseId:           infobaseID,
        UnlockSessions:       true,  // Разблокировать сеансы
        UnlockScheduledJobs:  true,  // Разблокировать регламентные задания
        ClusterUser:          proto.String("admin"),
        ClusterPassword:      proto.String("admin_password"),
    }

    resp, err := client.UnlockInfobase(context.Background(), req)
    if err != nil {
        return fmt.Errorf("failed to unlock infobase: %w", err)
    }

    fmt.Printf("Unlocked infobase: %s\n", resp.Message)
    return nil
}
```

## Безопасность

### ⚠️ КРИТИЧЕСКИ ВАЖНО

**1. TLS обязателен в production**

Все поля с паролями (`*_password`) должны передаваться **ТОЛЬКО через TLS-шифрованное соединение**:
- `db_password`
- `cluster_password`

**Настройка TLS для gRPC сервера:**
```go
creds, err := credentials.NewServerTLSFromFile("server.crt", "server.key")
if err != nil {
    log.Fatalf("Failed to generate credentials: %v", err)
}

server := grpc.NewServer(grpc.Creds(creds))
pb.RegisterInfobaseManagementServiceServer(server, &myService{})
```

**Настройка TLS для gRPC клиента:**
```go
creds, err := credentials.NewClientTLSFromFile("ca.crt", "")
if err != nil {
    log.Fatalf("Failed to load credentials: %v", err)
}

conn, err := grpc.Dial("localhost:50051", grpc.WithTransportCredentials(creds))
if err != nil {
    log.Fatalf("Failed to connect: %v", err)
}
defer conn.Close()

client := pb.NewInfobaseManagementServiceClient(conn)
```

**2. Логирование**

Пароли НЕ должны попадать в логи! Используйте фильтрацию:

```go
import "google.golang.org/grpc/grpclog"

// НЕ логировать sensitive поля
func sanitizeRequest(req proto.Message) proto.Message {
    // Клонировать request и очистить пароли
    sanitized := proto.Clone(req)
    // ... очистка полей password
    return sanitized
}

log.Info("Received request", "request", sanitizeRequest(req))
```

**3. Audit Trail**

Для деструктивных операций (`DropInfobase` с `drop_database=true`) **обязательно** вести audit log:

```go
func auditLog(operation string, userID string, infobaseID string, details map[string]interface{}) {
    log.Warn("AUDIT",
        "operation", operation,
        "user_id", userID,
        "infobase_id", infobaseID,
        "timestamp", time.Now(),
        "details", details,
    )
}

// При удалении базы с drop_database=true
if req.DropDatabase != nil && *req.DropDatabase {
    auditLog("DROP_INFOBASE_WITH_DATABASE", userID, req.InfobaseId, map[string]interface{}{
        "cluster_id": req.ClusterId,
        "drop_database": true,
    })
}
```

**4. RBAC (Role-Based Access Control)**

Деструктивные операции должны требовать специальных прав:

```go
func (s *service) DropInfobase(ctx context.Context, req *pb.DropInfobaseRequest) (*pb.DropInfobaseResponse, error) {
    userRole := extractUserRole(ctx)

    if req.DropDatabase != nil && *req.DropDatabase {
        // Удаление БД требует роли SUPER_ADMIN
        if userRole != "SUPER_ADMIN" {
            return nil, status.Errorf(codes.PermissionDenied, "drop_database requires SUPER_ADMIN role")
        }
    }

    // ... остальная логика
}
```

## Enum типы

### DBMSType

| Значение | Описание | Поддерживается 1С |
|----------|----------|-------------------|
| `DBMS_TYPE_MSSQL_SERVER` | Microsoft SQL Server | ✅ Да |
| `DBMS_TYPE_POSTGRESQL` | PostgreSQL | ✅ Да |
| `DBMS_TYPE_IBM_DB2` | IBM DB2 | ✅ Да |
| `DBMS_TYPE_ORACLE` | Oracle Database | ✅ Да |

### SecurityLevel

| Уровень | Описание | Рекомендации |
|---------|----------|--------------|
| `SECURITY_LEVEL_0` | Нет защиты | Только для development/testing |
| `SECURITY_LEVEL_1` | Базовая защита | Минимум для production |
| `SECURITY_LEVEL_2` | Повышенная защита | Рекомендуется для production |
| `SECURITY_LEVEL_3` | Максимальная защита | Для критичных систем |

## Структура директорий после генерации

```
api/
└── proto/
    ├── README.md                          # Эта документация
    ├── infobase_management.proto          # Protobuf схема
    ├── infobase_management.pb.go          # Сгенерированные Go структуры
    └── infobase_management_grpc.pb.go     # Сгенерированный gRPC код
```

## Версионирование

**Текущая версия:** `cluster.v1`

При breaking changes создается новая версия (`cluster.v2`), старая версия остается для обратной совместимости.

**Breaking changes:**
- Удаление или переименование полей
- Изменение типов полей
- Удаление методов RPC

**Non-breaking changes:**
- Добавление новых полей (optional)
- Добавление новых методов RPC
- Добавление новых enum значений

## Troubleshooting

### Ошибка: protoc not found

```bash
# Проверьте что protoc установлен
protoc --version

# Если нет - установите (см. раздел "Предварительные требования")
```

### Ошибка: protoc-gen-go not found

```bash
# Установите плагины
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Проверьте что $GOPATH/bin в PATH
echo $PATH | grep -q "$GOPATH/bin" && echo "OK" || echo "Add $GOPATH/bin to PATH"
```

### Ошибка: import "google/protobuf/timestamp.proto" not found

```bash
# Убедитесь что protoc может найти стандартные proto файлы
protoc --version  # Должно показать версию >= 3.15

# Если используете Windows и устанавливали вручную - проверьте что
# C:\protoc\include\ содержит google/protobuf/*.proto файлы
```

## Полезные ссылки

- [Protocol Buffers Documentation](https://developers.google.com/protocol-buffers)
- [gRPC Go Tutorial](https://grpc.io/docs/languages/go/quickstart/)
- [Buf - Modern Protobuf Tooling](https://buf.build/)
- [1С:Предприятие - Документация по RAC](https://its.1c.ru/db/metod8dev/content/3221/hdoc)

---

**Версия документа:** 1.0
**Дата создания:** 2025-11-02
**Sprint:** 3.1 - Protobuf Schema Design
