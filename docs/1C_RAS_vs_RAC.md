# RAS vs RAC: Архитектура администрирования 1С

## Краткий ответ

- **RAS** (ras.exe) = **Сервер** администрирования (Remote Administration **Server**)
- **RAC** (rac.exe) = **Клиент** администрирования (Remote Administration **Client**)

**RAC подключается к RAS для выполнения команд.**

---

## Архитектура системы администрирования 1С

```
┌─────────────┐
│   rac.exe   │ ← Клиент (командная строка)
│   (Client)  │
└──────┬──────┘
       │ TCP порт 1545
       ▼
┌─────────────┐
│   ras.exe   │ ← Сервер администрирования
│   (Server)  │    (должен быть запущен как служба)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  ragent.exe │ ← Агент кластера серверов
│ (Кластер 1С)│    (управляет рабочими процессами)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ rphost.exe  │ ← Рабочие процессы
│   (x 50)    │    (обрабатывают запросы клиентов)
└─────────────┘
```

---

## RAS (ras.exe) - Сервер администрирования

### Назначение

Сервер администрирования кластера - это служба/процесс, который:
- Предоставляет API для управления кластером
- Работает на порту 1545 (по умолчанию)
- Обязательно должен быть запущен для работы RAC
- Взаимодействует с агентами кластера (ragent.exe)

### Основные параметры

```bash
ras.exe [options]

Параметры:
  --port=<port>               # Порт сервера (по умолчанию: 1545)
  --monitor-address=<address> # IP для HTTP мониторинга (по умолчанию: 127.0.0.1)
  --monitor-port=<port>       # Порт HTTP мониторинга (по умолчанию: 1555)
  --monitor-base=<location>   # Базовый путь HTTP API (по умолчанию: /)
  --service                   # Запуск в режиме службы Windows
```

### Установка как служба Windows

```powershell
# Создать службу
sc create "1C:Enterprise RAS" ^
  binpath= "C:\Program Files\1cv8\8.3.27.1786\bin\ras.exe cluster --service" ^
  displayname= "1C:Enterprise RAS" ^
  start= auto

# Запустить службу
sc start "1C:Enterprise RAS"

# Проверить статус
sc query "1C:Enterprise RAS"
```

### HTTP мониторинг

RAS предоставляет встроенный HTTP endpoint для мониторинга:

```bash
# Запустить RAS с HTTP мониторингом на всех интерфейсах
ras.exe cluster --port=1545 --monitor-address=any --monitor-port=1555
```

Теперь можно получить метрики через HTTP:
```bash
curl http://localhost:1555/
```

---

## RAC (rac.exe) - Клиент администрирования

### Назначение

Утилита командной строки для выполнения административных операций:
- Получение списка кластеров
- Управление информационными базами
- Управление сеансами пользователей
- Настройка параметров кластера
- И многое другое...

### Основной синтаксис

```bash
rac.exe <server>:<port> <command> [options] [arguments]

# По умолчанию: localhost:1545
```

### Примеры команд

```bash
# Список кластеров
rac.exe localhost:1545 cluster list

# Список баз в кластере
rac.exe localhost:1545 infobase summary list --cluster=<uuid>

# Список активных сеансов
rac.exe localhost:1545 session list --cluster=<uuid>

# Завершить сеанс пользователя
rac.exe localhost:1545 session terminate --cluster=<uuid> --session=<session-id>
```

---

## Взаимодействие RAS и RAC

### Сценарий 1: Локальное администрирование

```bash
# 1. Запустить RAS локально
ras.exe cluster

# 2. В другом окне выполнить команды через RAC
rac.exe localhost:1545 cluster list
```

### Сценарий 2: Удалённое администрирование

```bash
# На сервере (Windows Server 2022):
# RAS запущен как служба Windows на порту 1545

# На рабочей станции администратора:
rac.exe 1cserver:1545 cluster list
```

### Сценарий 3: Через промежуточный сервер

```bash
# Архитектура:
# [Admin PC] → RAC → [Jump Server] → RAS → [1C Server] → Кластер

# На Jump Server запущен RAS, перенаправляющий запросы на 1C Server
rac.exe jumpserver:1545 cluster list
```

---

## Важные отличия

| Характеристика | RAS | RAC |
|----------------|-----|-----|
| **Тип** | Сервер (служба) | Клиент (CLI утилита) |
| **Запуск** | Постоянно работает | Запускается для каждой команды |
| **Порт** | Слушает 1545 (входящий) | Подключается к 1545 (исходящий) |
| **Установка** | Нужна как служба Windows | Не требует установки |
| **HTTP API** | Предоставляет (порт 1555) | Не предоставляет |
| **Доступ** | Через сеть | Локальный или удалённый |

---

## Использование в CommandCenter1C

### Вариант 1: RAC через командную строку (текущий)

**Плюсы:**
- Простая реализация
- Не требует запуска дополнительных служб
- Полный контроль над командами

**Минусы:**
- Парсинг текстового вывода
- Медленнее при большом количестве запросов
- Проблемы с кодировкой (Windows-1251)

**Реализация в Go:**
```go
// Выполнить команду через rac.exe
cmd := exec.Command(
    "C:\\Program Files\\1cv8\\8.3.27.1786\\bin\\rac.exe",
    "1cserver:1545",
    "infobase", "summary", "list",
    "--cluster=" + clusterUUID,
)
output, err := cmd.CombinedOutput()
// Парсинг output...
```

---

### Вариант 2: HTTP API через RAS (альтернатива)

**Плюсы:**
- Структурированные данные (можно использовать JSON)
- Быстрее для множественных запросов
- Легче парсить в Go/Python

**Минусы:**
- Требует запущенного RAS с HTTP мониторингом
- Не все операции доступны через HTTP
- Документация ограничена

**Реализация:**

Если использовать проект [hirac](https://github.com/arkuznetsov/hirac) - REST API обёртка над RAS:

```go
// HTTP запрос к hirac API
resp, err := http.Get("http://1cserver:1555/api/clusters")
// Получить JSON с информацией о кластерах
```

---

## Мониторинг с помощью RAS

### Встроенный HTTP endpoint

RAS предоставляет встроенный HTTP endpoint для получения метрик производительности:

```bash
# Запустить RAS с мониторингом
ras.exe cluster --monitor-address=any --monitor-port=1555

# Получить метрики
curl http://localhost:1555/
```

### Интеграция с системами мониторинга

**Zabbix + RAS:**
```bash
# Скрипт для Zabbix вызывает rac.exe и парсит вывод
rac.exe localhost:1545 session list --cluster=$CLUSTER_UUID | grep "app-id" | wc -l
```

**Prometheus + Custom Exporter:**
```python
# Python exporter для Prometheus
import subprocess
import re

def get_session_count():
    output = subprocess.check_output([
        "rac.exe", "localhost:1545", "session", "list",
        f"--cluster={CLUSTER_UUID}"
    ])
    sessions = len(re.findall(r'session\s+:\s+', output.decode('cp1251')))
    return sessions
```

---

## Рекомендации для проекта

### Для получения списка баз (текущая задача)

**Рекомендую: RAC через командную строку**

Причины:
1. Не требует дополнительной настройки RAS
2. Простая реализация в Go
3. Достаточная скорость для периодической синхронизации (1-2 раза в день)

**План реализации:**
```
1. Go Installation Service запускает rac.exe локально
2. Парсит вывод команды "infobase summary list"
3. Отправляет список в Django Orchestrator через Redis
4. Django сохраняет в PostgreSQL
```

---

### Для real-time мониторинга (будущее)

**Рекомендую: RAS + HTTP API + REST wrapper (hirac)**

Причины:
1. Быстрее для частых запросов
2. Структурированные данные
3. Легче интегрировать с Prometheus/Grafana

**План реализации:**
```
1. Установить RAS как службу Windows
2. Настроить HTTP мониторинг (порт 1555)
3. Использовать hirac или написать свой REST wrapper
4. Django/Go запрашивает метрики через HTTP
```

---

## Полезные ссылки

- [GitHub: hirac - REST API для кластера 1С](https://github.com/arkuznetsov/hirac)
- [Мониторинг производительности кластера 1С](https://infostart.ru/1c/articles/1168942/)
- [Мониторинг 1С с помощью Zabbix](https://jakondo.ru/monitoring-1s-predpriyatie-8-3-s-pomoshhyu-zabbix/)
- [Сервер администрирования кластера](https://infostart.ru/1c/articles/810752/)

---

## Итого: Что использовать?

### Для CommandCenter1C

| Задача | Решение | Инструмент |
|--------|---------|-----------|
| **Получение списка баз** | RAC CLI | `rac.exe infobase summary list` |
| **Установка расширений** | RAC CLI | `rac.exe infobase info` + `1cv8.exe` |
| **Периодическая синхронизация** | RAC CLI | Celery task (1-2 раза/день) |
| **Real-time мониторинг** (Phase 3) | RAS HTTP | HTTP API через порт 1555 |
| **Grafana дашборды** (Phase 3) | RAS HTTP | Prometheus exporter |

### Текущий приоритет

✅ **Реализовать:** Go модуль для работы с `rac.exe`
⏳ **Отложить:** Интеграцию с RAS HTTP API до Phase 3 (Monitoring & Observability)

---

**Версия:** 1.0
**Дата:** 2025-10-27
**Автор:** CommandCenter1C Team
