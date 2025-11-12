# RAS Sniffer - Быстрый старт

## Запуск (3 простых шага)

### Шаг 1: Запустить proxy

```bash
cd C:/1CProject/command-center-1c/tools/ras-sniffer
./start.sh
```

**Вывод:**
```
Starting RAS Protocol Proxy Sniffer...
========================================
  RAS Protocol Proxy Sniffer
========================================

Proxy: localhost:1546
Target: localhost:1545
Log: C:/1CProject/command-center-1c/tools/ras-sniffer/ras-protocol-capture.log

Usage in another terminal:
  rac.exe cluster list localhost:1546

View log in real-time:
  tail -f C:/1CProject/command-center-1c/tools/ras-sniffer/ras-protocol-capture.log

Press Ctrl+C to stop

Proxy listening on localhost:1546, forwarding to localhost:1545
Waiting for rac.exe connection...
```

### Шаг 2: Запустить команду rac.exe (в ДРУГОМ терминале)

```bash
# Найти путь к rac.exe
find /c/Program\ Files* -name "rac.exe" 2>/dev/null | head -1

# Использовать найденный путь (пример для 8.3.27)
"/c/Program Files/1cv8/8.3.27.1786/bin/rac.exe" cluster list localhost:1546

# Или добавить в PATH и использовать просто:
rac.exe cluster list localhost:1546
```

### Шаг 3: Смотреть захваченный трафик (в ТРЕТЬЕМ терминале)

```bash
cd C:/1CProject/command-center-1c/tools/ras-sniffer
tail -f ras-protocol-capture.log
```

## Примеры команд для захвата

```bash
# 1. Список кластеров (самая простая команда)
rac.exe cluster list localhost:1546

# 2. Информация о кластере
rac.exe cluster info --cluster=<UUID> localhost:1546

# 3. Список информационных баз
rac.exe infobase summary list --cluster=<UUID> localhost:1546

# 4. Информация об информационной базе
rac.exe infobase info --cluster=<UUID> --infobase=<UUID> localhost:1546

# 5. Список сессий (требует аутентификацию)
rac.exe session list --cluster=<UUID> --cluster-user=admin --cluster-pwd=password localhost:1546

# 6. Список соединений
rac.exe connection list --cluster=<UUID> --cluster-user=admin --cluster-pwd=password localhost:1546
```

## Пример вывода лога

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
000030  | 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 | ................

[ANALYSIS]
First 8 bytes (possible header): 010000009c000000
Contains printable strings: true
Possible length encoding (LE): 156
Possible length encoding (BE): 16777216
Extracted strings (min 4 chars): [cluster list]

================================================================================

--- Packet #1 [Conn #1] SERVER→CLIENT @ 10:25:20.489 ---
Length: 384 bytes

Offset  | Hex                                              | ASCII
--------|--------------------------------------------------|------------------
000000  | 02 00 00 00 80 01 00 00  01 00 00 00 00 00 00 00 | ................
000010  | 24 00 00 00 61 32 62 33  63 34 64 35 2d 65 36 66 | $...a2b3c4d5-e6f
000020  | 37 2d 38 39 30 61 2d 62  63 64 65 2d 66 30 31 32 | 7-890a-bcde-f012
000030  | 33 34 35 36 37 38 39 61  00 00 00 00 0f 00 00 00 | 3456789a........

[ANALYSIS]
First 8 bytes (possible header): 020000008001000000
Contains printable strings: true
Possible length encoding (LE): 384
Possible length encoding (BE): 33554432
Found UUIDs: a2b3c4d5-e6f7-890a-bcde-f0123456789a
Extracted strings (min 4 chars): [a2b3c4d5-e6f7-890a-bcde-f0123456789a MainCluster]

================================================================================

[CONNECTION #1 CLOSED] 10:25:20.512
```

## Анализ результатов

### 1. Идентификация message types

Смотри на первые байты пакетов:
- `01 00 00 00` - возможно REQUEST
- `02 00 00 00` - возможно RESPONSE
- `03 00 00 00` - возможно ERROR

### 2. Extraction UUID

Все UUID в формате: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

Proxy автоматически находит их:
```bash
grep "Found UUIDs" ras-protocol-capture.log
```

### 3. Extraction строк

Proxy извлекает printable строки:
```bash
grep "Extracted strings" ras-protocol-capture.log
```

### 4. Корреляция запросов и ответов

Используй Packet # и Timestamp для matching:
```bash
# Запросы
grep "CLIENT→SERVER" ras-protocol-capture.log

# Ответы
grep "SERVER→CLIENT" ras-protocol-capture.log
```

## Troubleshooting

### Port 1546 already in use

```bash
# Найти процесс
netstat -ano | findstr :1546

# Убить процесс (Windows)
taskkill /PID <pid> /F
```

### RAS Server connection refused

Убедись что RAS Server запущен:
```bash
netstat -ano | findstr :1545
```

Если нет - запусти RAS Server или измени `targetAddr` в `main.go`.

### rac.exe not found

Найди путь к rac.exe:
```bash
find /c/Program\ Files* -name "rac.exe" 2>/dev/null
```

Используй полный путь:
```bash
"/c/Program Files/1cv8/8.3.27.1786/bin/rac.exe" cluster list localhost:1546
```

## Остановка proxy

Нажми `Ctrl+C` в терминале где запущен proxy.

---

**Время на setup:** ~2 минуты
**Готов к использованию:** ✅ YES
