# Серверная валидация для InfobaseManagementService

## Обязательная валидация (Sprint 3.2)

При реализации gRPC сервера **ОБЯЗАТЕЛЬНО** добавить валидацию для предотвращения некорректных запросов.

### CreateInfobase - Валидация

```go
func (s *InfobaseService) CreateInfobase(ctx context.Context, req *pb.CreateInfobaseRequest) (*pb.CreateInfobaseResponse, error) {
    // ВАЛИДАЦИЯ 1: Имя базы не пустое
    if strings.TrimSpace(req.Name) == "" {
        return nil, status.Error(codes.InvalidArgument, "name is required and cannot be empty")
    }

    // ВАЛИДАЦИЯ 2: Имя базы соответствует формату (буквы, цифры, подчеркивание)
    if !regexp.MustCompile(`^[a-zA-Z0-9_-]+$`).MatchString(req.Name) {
        return nil, status.Error(codes.InvalidArgument, "name must contain only letters, digits, underscore and dash")
    }

    // ВАЛИДАЦИЯ 3: DBMS указан
    if req.Dbms == pb.DBMSType_DBMS_TYPE_UNSPECIFIED {
        return nil, status.Error(codes.InvalidArgument, "dbms must be specified (MSSQL, PostgreSQL, DB2, Oracle)")
    }

    // ВАЛИДАЦИЯ 4: DB Server не пустой
    if strings.TrimSpace(req.DbServer) == "" {
        return nil, status.Error(codes.InvalidArgument, "db_server is required")
    }

    // ВАЛИДАЦИЯ 5: DB Name не пустое
    if strings.TrimSpace(req.DbName) == "" {
        return nil, status.Error(codes.InvalidArgument, "db_name is required")
    }

    // Вызов RAC CLI...
}
```

### UpdateInfobase - Валидация

```go
func (s *InfobaseService) UpdateInfobase(ctx context.Context, req *pb.UpdateInfobaseRequest) (*pb.UpdateInfobaseResponse, error) {
    // ВАЛИДАЦИЯ 1: Интервал блокировки корректен
    if req.DeniedFrom != nil && req.DeniedTo != nil {
        from := req.DeniedFrom.AsTime()
        to := req.DeniedTo.AsTime()

        if to.Before(from) {
            return nil, status.Error(codes.InvalidArgument,
                "denied_to must be after denied_from")
        }
    }

    // ВАЛИДАЦИЯ 2: Хотя бы одно поле для обновления
    if !hasAnyFieldSet(req) {
        return nil, status.Error(codes.InvalidArgument,
            "at least one field must be set for update")
    }

    // Вызов RAC CLI...
}

func hasAnyFieldSet(req *pb.UpdateInfobaseRequest) bool {
    return req.SessionsDeny != nil ||
           req.ScheduledJobsDeny != nil ||
           req.Dbms != nil ||
           req.DbServer != nil ||
           // ... остальные поля
}
```

### LockInfobase - Валидация

```go
func (s *InfobaseService) LockInfobase(ctx context.Context, req *pb.LockInfobaseRequest) (*pb.LockInfobaseResponse, error) {
    // ВАЛИДАЦИЯ 1: Хотя бы один тип блокировки
    if !req.SessionsDeny && !req.ScheduledJobsDeny {
        return nil, status.Error(codes.InvalidArgument,
            "at least one lock type must be enabled (sessions_deny or scheduled_jobs_deny)")
    }

    // ВАЛИДАЦИЯ 2: Интервал блокировки корректен
    if req.DeniedFrom != nil && req.DeniedTo != nil {
        from := req.DeniedFrom.AsTime()
        to := req.DeniedTo.AsTime()

        if to.Before(from) {
            return nil, status.Error(codes.InvalidArgument,
                "denied_to must be after denied_from")
        }
    }

    // Вызов RAC CLI...
}
```

### DropInfobase - Валидация

```go
func (s *InfobaseService) DropInfobase(ctx context.Context, req *pb.DropInfobaseRequest) (*pb.DropInfobaseResponse, error) {
    // ВАЛИДАЦИЯ 1: DropMode указан
    if req.DropMode == pb.DropMode_DROP_MODE_UNSPECIFIED {
        return nil, status.Error(codes.InvalidArgument,
            "drop_mode must be specified")
    }

    // ВАЛИДАЦИЯ 2 (опционально): Защита от случайного удаления БД
    if req.DropMode == pb.DropMode_DROP_MODE_DROP_DATABASE {
        // TODO: Добавить дополнительную проверку (например, confirmation token)
        log.Warn("DANGEROUS: Dropping database", "infobase_id", req.InfobaseId)
    }

    // Вызов RAC CLI...
}
```

## Unit тесты валидации

```go
func TestCreateInfobase_Validation(t *testing.T) {
    service := &InfobaseService{}

    tests := []struct {
        name    string
        req     *pb.CreateInfobaseRequest
        wantErr bool
        errCode codes.Code
    }{
        {
            name: "empty name",
            req: &pb.CreateInfobaseRequest{
                ClusterId: "cluster-123",
                Name:      "",  // ПУСТОЕ
                Dbms:      pb.DBMSType_DBMS_TYPE_MSSQL_SERVER,
            },
            wantErr: true,
            errCode: codes.InvalidArgument,
        },
        {
            name: "unspecified dbms",
            req: &pb.CreateInfobaseRequest{
                ClusterId: "cluster-123",
                Name:      "test_db",
                Dbms:      pb.DBMSType_DBMS_TYPE_UNSPECIFIED,  // UNSPECIFIED
            },
            wantErr: true,
            errCode: codes.InvalidArgument,
        },
        // ... остальные тесты
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            _, err := service.CreateInfobase(context.Background(), tt.req)
            if tt.wantErr {
                require.Error(t, err)
                st, ok := status.FromError(err)
                require.True(t, ok)
                assert.Equal(t, tt.errCode, st.Code())
            }
        })
    }
}
```

## Рекомендации

- Валидация на **двух уровнях**: REST API (cluster-service) + gRPC сервер (ras-grpc-gw fork)
- Использовать **google.golang.org/grpc/codes** для error codes
- Логировать **все валидационные ошибки** (для audit trail)
