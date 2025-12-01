#!/bin/bash

##############################################################################
# CommandCenter1C - Generate Fernet Encryption Key
##############################################################################
#
# Генерирует валидный Fernet ключ для шифрования полей в Django.
# Ключ можно использовать для DB_ENCRYPTION_KEY в .env.local
#
# Usage:
#   ./scripts/utils/generate-encryption-key.sh
#
# Output:
#   Выводит сгенерированный ключ в stdout
#
##############################################################################

# Генерация 32 байт случайных данных и кодирование в url-safe base64
# Fernet требует именно такой формат

if command -v python3 &>/dev/null; then
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null && exit 0
elif command -v python &>/dev/null; then
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null && exit 0
fi

# Fallback: использовать openssl если cryptography недоступен
if command -v openssl &>/dev/null; then
    openssl rand -base64 32 | tr '+/' '-_'
    exit 0
fi

echo "ERROR: Требуется python с cryptography или openssl" >&2
exit 1
