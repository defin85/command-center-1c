# Настройка TLS для cluster-service

## Зачем нужен TLS?

Protobuf API передает **пароли БД** и **пароли кластера** в plaintext. Без TLS эти пароли могут быть перехвачены при передаче по сети.

**КРИТИЧНО:** TLS ОБЯЗАТЕЛЕН в production окружении!

## Production Setup

### 1. Получить TLS сертификаты

**Рекомендуется:** Let's Encrypt (бесплатно, автоматизация)

```bash
# Установить certbot
sudo apt-get install certbot

# Получить сертификат для домена
sudo certbot certonly --standalone -d ras.example.com
```

Сертификаты будут сохранены в:
- `/etc/letsencrypt/live/ras.example.com/fullchain.pem` - сертификат
- `/etc/letsencrypt/live/ras.example.com/privkey.pem` - приватный ключ

### 2. Настроить ras-grpc-gw

```go
creds, err := credentials.NewServerTLSFromFile(
    "/etc/letsencrypt/live/ras.example.com/fullchain.pem",
    "/etc/letsencrypt/live/ras.example.com/privkey.pem",
)
grpcServer := grpc.NewServer(grpc.Creds(creds))
```

### 3. Настроить cluster-service

```go
creds := credentials.NewTLS(&tls.Config{
    ServerName:         "ras.example.com",
    InsecureSkipVerify: false,  // ОБЯЗАТЕЛЬНО false в production!
})
conn, err := grpc.Dial("ras.example.com:50051", grpc.WithTransportCredentials(creds))
```

## Тестирование TLS соединения

```bash
# Проверить что TLS работает
grpcurl -insecure ras.example.com:50051 list

# Проверить сертификат
openssl s_client -connect ras.example.com:50051 -showcerts
```

## Mutual TLS (mTLS) - опционально

Для дополнительной безопасности можно настроить mTLS (клиент тоже аутентифицируется сертификатом).

См. документацию: https://grpc.io/docs/guides/auth/#with-server-authentication-ssltls-and-a-custom-header-with-token

## Troubleshooting

**Ошибка: "x509: certificate signed by unknown authority"**
- Убедитесь что CA сертификат доверенный
- В dev окружении можно временно использовать `InsecureSkipVerify: true` (НЕ в production!)

**Ошибка: "tls: first record does not look like a TLS handshake"**
- Клиент пытается подключиться без TLS к серверу с TLS
- Убедитесь что используете `grpc.WithTransportCredentials(creds)`
