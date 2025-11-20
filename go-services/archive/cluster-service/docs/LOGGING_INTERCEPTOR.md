# gRPC Logging Interceptor с Sanitization

## Проблема

При логировании gRPC запросов пароли (`*_password` поля) могут попасть в логи в plaintext.

**Пример ОПАСНОГО лога:**
```
INFO gRPC call method=/cluster.v1.InfobaseManagementService/CreateInfobase
request={cluster_id:"abc", name:"test", db_password:"SecretPassword123"}
```

## Решение

Использовать gRPC interceptor с sanitization паролей.

### Реализация (Sprint 3.2)

```go
package interceptor

import (
    "context"
    "fmt"
    "reflect"
    "strings"

    "google.golang.org/grpc"
    "google.golang.org/protobuf/proto"
)

// SanitizePasswordsInterceptor - gRPC interceptor для удаления паролей из логов
func SanitizePasswordsInterceptor(
    ctx context.Context,
    req interface{},
    info *grpc.UnaryServerInfo,
    handler grpc.UnaryHandler,
) (interface{}, error) {
    // Клонировать запрос для sanitization
    sanitized := sanitizePasswords(req)

    // Логировать sanitized версию
    log.Info("gRPC call",
        "method", info.FullMethod,
        "request", sanitized,
    )

    // Вызвать handler с ОРИГИНАЛЬНЫМ запросом (не sanitized!)
    resp, err := handler(ctx, req)

    if err != nil {
        log.Error("gRPC call failed",
            "method", info.FullMethod,
            "error", err,
        )
    }

    return resp, err
}

// sanitizePasswords - удаляет все поля *_password из структуры
func sanitizePasswords(req interface{}) string {
    if req == nil {
        return "<nil>"
    }

    // Используем reflection для обхода полей
    v := reflect.ValueOf(req)
    if v.Kind() == reflect.Ptr {
        v = v.Elem()
    }

    if v.Kind() != reflect.Struct {
        return fmt.Sprintf("%v", req)
    }

    // Собираем поля, скрывая пароли
    var fields []string
    t := v.Type()
    for i := 0; i < v.NumField(); i++ {
        field := t.Field(i)
        value := v.Field(i)

        // Проверяем имя поля
        fieldName := field.Name
        if strings.HasSuffix(strings.ToLower(fieldName), "password") {
            fields = append(fields, fmt.Sprintf("%s:***REDACTED***", fieldName))
        } else {
            fields = append(fields, fmt.Sprintf("%s:%v", fieldName, value.Interface()))
        }
    }

    return fmt.Sprintf("{%s}", strings.Join(fields, ", "))
}

// Альтернатива: использовать protobuf reflection
func sanitizePasswordsProto(msg proto.Message) string {
    // TODO: Использовать protoreflect для более точной sanitization
    return sanitizePasswords(msg)
}
```

### Регистрация interceptor

```go
func main() {
    // Создать gRPC сервер с interceptor
    grpcServer := grpc.NewServer(
        grpc.UnaryInterceptor(interceptor.SanitizePasswordsInterceptor),
    )

    pb.RegisterInfobaseManagementServiceServer(grpcServer, &service{})
    grpcServer.Serve(lis)
}
```

### Пример безопасного лога

**ДО sanitization:**
```
INFO gRPC call method=/CreateInfobase request={name:"test", db_password:"Secret123"}
```

**ПОСЛЕ sanitization:**
```
INFO gRPC call method=/CreateInfobase request={name:"test", db_password:***REDACTED***}
```

## Unit тесты

```go
func TestSanitizePasswords(t *testing.T) {
    req := &pb.CreateInfobaseRequest{
        Name:        "test_db",
        DbPassword:  proto.String("SecretPassword123"),
        ClusterPassword: proto.String("AdminPassword456"),
    }

    sanitized := sanitizePasswords(req)

    assert.Contains(t, sanitized, "test_db")
    assert.Contains(t, sanitized, "***REDACTED***")
    assert.NotContains(t, sanitized, "SecretPassword123")
    assert.NotContains(t, sanitized, "AdminPassword456")
}
```
