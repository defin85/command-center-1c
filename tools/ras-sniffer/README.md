# RAS Protocol Proxy Sniffer

TCP proxy для перехвата и анализа бинарного протокола RAS (Remote Administration Server) 1С Enterprise.

## Назначение

Инструмент для reverse engineering RAS протокола путём перехвата трафика между `rac.exe` и RAS Server.

## Архитектура

```
rac.exe → localhost:1546 → [PROXY SNIFFER] → localhost:1545 → RAS Server
                              ↓
                        ras-protocol-capture.log
                        - Hex dump всех пакетов
                        - Bi-directional logging
                        - Packet analysis
                        - Timestamps
```

## Использование

### 1. Запуск proxy sniffer

```bash
cd tools/ras-sniffer

# Вариант 1: Запуск через go run
go run main.go

# Вариант 2: Компиляция и запуск бинарника
go build -o ras-sniffer.exe
./ras-sniffer.exe
```

**Вывод:**
```
[2025-11-12 10:25:15.123] RAS Protocol Proxy Sniffer started
[2025-11-12 10:25:15.123] Listening on: localhost:1546
[2025-11-12 10:25:15.123] Forwarding to: localhost:1545
[2025-11-12 10:25:15.123] Usage: rac.exe cluster list localhost:1546
Proxy listening on localhost:1546, forwarding to localhost:1545
Waiting for rac.exe connection...
```

### 2. Использование rac.exe через proxy

Вместо прямого подключения к RAS Server (`localhost:1545`), используй proxy (`localhost:1546`):

```bash
# ВМЕСТО:
rac.exe cluster list localhost:1545

# ИСПОЛЬЗУЙ:
rac.exe cluster list localhost:1546

# Другие примеры:
rac.exe cluster list localhost:1546
rac.exe infobase summary list --cluster=<UUID> localhost:1546
rac.exe session list --cluster=<UUID> --cluster-user=admin --cluster-pwd=password localhost:1546
```

**Все команды будут работать как обычно, но трафик будет перехвачен и залогирован!**

### 3. Анализ захваченного трафика

Proxy создаёт файл `ras-protocol-capture.log` в текущей директории.

**Просмотр в реальном времени:**
```bash
tail -f ras-protocol-capture.log
```

**Пример лога:**

```
[2025-11-12 10:25:20.456]
[CONNECTION #1 ESTABLISHED] 10:25:20.456
Client: 127.0.0.1:54321 -> Proxy: localhost:1546 -> RAS: localhost:1545

--- Packet #1 [Conn #1] CLIENT→SERVER @ 10:25:20.457 ---
Length: 156 bytes

Offset  | Hex                                              | ASCII
--------|--------------------------------------------------|------------------
000000  | 01 00 00 00 9c 00 00 00  00 00 00 00 00 00 00 00 | ................
000010  | 0a 00 00 00 63 6c 75 73  74 65 72 00 04 00 00 00 | ....cluster.....
000020  | 6c 69 73 74 00 00 00 00  00 00 00 00 00 00 00 00 | list............
...

[ANALYSIS]
First 8 bytes (possible header): 010000009c000000
Contains printable strings: true
Possible length encoding (LE): 156
Possible length encoding (BE): 16777216
Extracted strings (min 4 chars): [cluster list]

================================================================================

--- Packet #1 [Conn #1] SERVER→CLIENT @ 10:25:20.489 ---
Length: 1024 bytes

Offset  | Hex                                              | ASCII
--------|--------------------------------------------------|------------------
000000  | 02 00 00 00 00 04 00 00  01 00 00 00 00 00 00 00 | ................
000010  | 24 00 00 00 61 62 63 64  65 66 67 68 2d 31 32 33 | $...abcdefgh-123
000020  | 34 2d 35 36 37 38 2d 39  30 61 62 2d 63 64 65 66 | 4-5678-90ab-cdef
...

[ANALYSIS]
First 8 bytes (possible header): 020000000004000000
Contains printable strings: true
Possible length encoding (LE): 1024
Possible length encoding (BE): 33554432
Found UUIDs: abcdefgh-1234-5678-90ab-cdef12345678
Extracted strings (min 4 chars): [abcdefgh-1234-5678-90ab-cdef12345678 cluster-name]

================================================================================
```

## Что логируется

### 1. Connection Events
- Установка соединения (Client → Proxy → RAS)
- Закрытие соединения
- Connection ID для correlation пакетов

### 2. Packet Details (каждый пакет)
- **Direction:** CLIENT→SERVER или SERVER→CLIENT
- **Timestamp:** Точное время с миллисекундами
- **Length:** Размер пакета в байтах
- **Hex Dump:** 16 байт на строку с offset
- **ASCII View:** Printable символы или '.'

### 3. Packet Analysis
- **Header bytes:** Первые 8 байт (для pattern detection)
- **Printable content:** % printable символов
- **Length encoding:** Little-endian и Big-endian интерпретация первых 4 байт
- **UUID detection:** Автоматический поиск UUID паттернов (cluster/infobase IDs)
- **String extraction:** Извлечение printable строк (min 4 символа)

## Примеры использования

### Базовый сценарий

```bash
# Terminal 1: Запуск proxy
cd tools/ras-sniffer
go run main.go

# Terminal 2: Запуск команды через proxy
rac.exe cluster list localhost:1546

# Terminal 3: Просмотр лога в реальном времени
tail -f ras-protocol-capture.log
```

### Захват сложных операций

```bash
# Запуск proxy
go run main.go

# В другом терминале - последовательность команд:
rac.exe cluster list localhost:1546
rac.exe infobase summary list --cluster=<UUID> localhost:1546
rac.exe session list --cluster=<UUID> --cluster-user=admin --cluster-pwd=pass localhost:1546

# Анализировать лог для понимания протокола
cat ras-protocol-capture.log | grep "CLIENT→SERVER" | wc -l  # Сколько запросов
cat ras-protocol-capture.log | grep "Found UUIDs"            # Найденные UUID
```

### Фильтрация лога

```bash
# Только CLIENT→SERVER пакеты
grep -A 30 "CLIENT→SERVER" ras-protocol-capture.log

# Только SERVER→CLIENT пакеты
grep -A 30 "SERVER→CLIENT" ras-protocol-capture.log

# Найти все UUID в протоколе
grep "Found UUIDs" ras-protocol-capture.log

# Найти все строки в протоколе
grep "Extracted strings" ras-protocol-capture.log
```

## Troubleshooting

### Proxy не запускается

**Ошибка:** `bind: address already in use`

**Причина:** Порт 1546 уже занят

**Решение:**
```bash
# Найти процесс на порту 1546
netstat -ano | findstr :1546

# Убить процесс (Windows)
taskkill /PID <pid> /F
```

### rac.exe не подключается к proxy

**Причина:** Порт 1546 заблокирован firewall

**Решение:**
```bash
# Разрешить входящие подключения на 1546 (Windows Firewall)
# При первом запуске Windows спросит разрешение - нажми "Allow"
```

### RAS Server недоступен

**Ошибка в логе:** `Failed to connect to RAS: connection refused`

**Причина:** RAS Server не запущен на localhost:1545

**Решение:**
1. Проверить что RAS Server запущен
2. Проверить что RAS Server слушает на порту 1545:
   ```bash
   netstat -ano | findstr :1545
   ```
3. Если RAS на другом порту - изменить `targetAddr` в `main.go`

### Пустой лог файл

**Причина:** Нет прав на запись в директорию

**Решение:**
```bash
# Запустить с правами администратора
# или изменить директорию для лога
```

## Анализ протокола

После захвата трафика используй лог для:

1. **Определение структуры пакетов:**
   - Поиск header patterns
   - Определение encoding (Little-endian/Big-endian)
   - Поиск delimiter/terminator байтов

2. **Корреляция запросов и ответов:**
   - Сопоставление CLIENT→SERVER и SERVER→CLIENT пакетов
   - Определение request/response паттернов

3. **Извлечение метаданных:**
   - UUID форматы
   - Строковые поля
   - Числовые поля

4. **Определение message types:**
   - По первым байтам (message type?)
   - По длине пакета
   - По контенту

## Альтернативные инструменты

Если нужен более мощный анализ, можно использовать:

- **Wireshark:** GUI для анализа TCP трафика (но нужен loopback capture)
- **tcpdump:** Command-line packet capture
- **Burp Suite:** HTTP/TCP proxy (если протокол text-based)

Но этот sniffer специально заточен под RAS протокол с автоматическим анализом UUID и строк.

## Лицензия

Внутренний инструмент для CommandCenter1C проекта.
