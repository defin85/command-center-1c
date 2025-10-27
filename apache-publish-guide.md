# Публикация баз 1С через Apache (webinst.exe)

## Общая информация

Apache уже настроен для работы с 1С:Предприятие:
- Модуль `wsap24.dll` подключен
- Таймауты увеличены до 300 секунд
- Путь к платформе: `C:/Program Files/1cv8/8.3.27.1786`

## Публикация базы через webinst.exe

### Для файловой базы данных

```bash
"C:/Program Files/1cv8/8.3.27.1786/bin/webinst.exe" \
  -publish \
  -apache24 \
  -wsdir ИмяПубликации \
  -dir "C:/Apache24/htdocs/ИмяПубликации" \
  -connstr "File=\"C:/Путь/К/Базе\";" \
  -confpath "C:/Apache24/conf/httpd.conf"
```

**Параметры:**
- `-publish` - команда публикации
- `-apache24` - тип веб-сервера (Apache 2.4)
- `-wsdir` - имя публикации (будет в URL: http://localhost/ИмяПубликации)
- `-dir` - физический путь к публикации (htdocs)
- `-connstr` - строка подключения к базе
- `-confpath` - путь к конфигурационному файлу Apache

### Для серверной базы данных

```bash
"C:/Program Files/1cv8/8.3.27.1786/bin/webinst.exe" \
  -publish \
  -apache24 \
  -wsdir ИмяПубликации \
  -dir "C:/Apache24/htdocs/ИмяПубликации" \
  -connstr "Srvr=localhost;Ref=ИмяБазыНаСервере;" \
  -confpath "C:/Apache24/conf/httpd.conf"
```

## Примеры публикации

### Пример 1: Публикация файловой базы TestBase

```bash
"C:/Program Files/1cv8/8.3.27.1786/bin/webinst.exe" \
  -publish \
  -apache24 \
  -wsdir testbase \
  -dir "C:/Apache24/htdocs/testbase" \
  -connstr "File=\"C:/1CProject/bases/TestBase\";" \
  -confpath "C:/Apache24/conf/httpd.conf"
```

После публикации база будет доступна по адресу: `http://localhost/testbase`

### Пример 2: Публикация серверной базы CommandCenter

```bash
"C:/Program Files/1cv8/8.3.27.1786/bin/webinst.exe" \
  -publish \
  -apache24 \
  -wsdir commandcenter \
  -dir "C:/Apache24/htdocs/commandcenter" \
  -connstr "Srvr=localhost;Ref=CommandCenter;" \
  -confpath "C:/Apache24/conf/httpd.conf"
```

После публикации база будет доступна по адресу: `http://localhost/commandcenter`

## Управление публикациями

### Список опубликованных баз

```bash
"C:/Program Files/1cv8/8.3.27.1786/bin/webinst.exe" \
  -list \
  -apache24 \
  -confpath "C:/Apache24/conf/httpd.conf"
```

### Снятие публикации

```bash
"C:/Program Files/1cv8/8.3.27.1786/bin/webinst.exe" \
  -unpublish \
  -apache24 \
  -wsdir ИмяПубликации \
  -confpath "C:/Apache24/conf/httpd.conf"
```

## Работа с Apache

### Проверка конфигурации

```bash
/c/Apache24/bin/httpd.exe -t
```

### Перезапуск сервера

```bash
# Перезапуск Apache
/c/Apache24/bin/httpd.exe -k restart

# Остановка
/c/Apache24/bin/httpd.exe -k stop

# Запуск
/c/Apache24/bin/httpd.exe -k start
```

### Проверка статуса службы

```bash
# Через службы Windows
net start | grep Apache

# Запуск службы
net start Apache2.4

# Остановка службы
net stop Apache2.4
```

## Типичные проблемы

### Ошибка: Apache не запускается после публикации

**Решение:**
1. Проверить синтаксис конфигурации: `/c/Apache24/bin/httpd.exe -t`
2. Проверить логи: `tail -f /c/Apache24/logs/error.log`
3. Убедиться, что путь к wsap24.dll правильный

### База не открывается в браузере

**Решение:**
1. Проверить, что Apache запущен
2. Проверить URL (должен быть `http://localhost/wsdir_name`)
3. Проверить логи Apache: `tail -f /c/Apache24/logs/error.log`

### Ошибка "Не удается найти файл wsap24.dll"

**Решение:**
Проверить путь в httpd.conf (строка 190):
```apache
LoadModule _1cws_module "C:/Program Files/1cv8/8.3.27.1786/bin/wsap24.dll"
```

## Дополнительные параметры webinst

### Публикация с пулом соединений

```bash
"C:/Program Files/1cv8/8.3.27.1786/bin/webinst.exe" \
  -publish \
  -apache24 \
  -wsdir testbase \
  -dir "C:/Apache24/htdocs/testbase" \
  -connstr "File=\"C:/1CProject/bases/TestBase\";" \
  -confpath "C:/Apache24/conf/httpd.conf" \
  -poolSize 10 \
  -poolTimeout 600
```

**Параметры пула:**
- `-poolSize` - максимальное количество соединений (по умолчанию 10)
- `-poolTimeout` - таймаут простоя соединения в секундах (по умолчанию 600)

### Публикация с указанием порта

Если Apache слушает на нестандартном порту:

```bash
"C:/Program Files/1cv8/8.3.27.1786/bin/webinst.exe" \
  -publish \
  -apache24 \
  -wsdir testbase \
  -dir "C:/Apache24/htdocs/testbase" \
  -connstr "File=\"C:/1CProject/bases/TestBase\";" \
  -confpath "C:/Apache24/conf/httpd.conf" \
  -port 8080
```

## Полезные ссылки

- [Документация 1С по публикации через Apache](https://its.1c.ru/db/v8doc)
- [Apache 2.4 документация](https://httpd.apache.org/docs/2.4/)

## Конфигурация Apache

Основные настройки Apache для 1С (уже применены):

```apache
# Модули
LoadModule headers_module modules/mod_headers.so
LoadModule rewrite_module modules/mod_rewrite.so
LoadModule _1cws_module "C:/Program Files/1cv8/8.3.27.1786/bin/wsap24.dll"

# Базовые настройки
ServerName localhost:80
Timeout 300
KeepAliveTimeout 15
```

---

**Автор:** Command Center 1C Team
**Дата:** 2025-01-24
