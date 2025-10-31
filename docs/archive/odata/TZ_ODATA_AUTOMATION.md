# Техническое задание: Автоматизация настройки OData для 700 баз 1С

**Дата:** 2025-10-25
**Проект:** CommandCenter1C
**Версия:** 1.0
**Статус:** Утверждено

---

## 1. Общие сведения

### 1.1. Цель проекта

Разработать автоматизированное решение для массовой настройки OData публикаций в 700 базах 1С:Бухгалтерия 3.0 с минимальными временными затратами.

### 1.2. Задача

- **Текущая проблема:** OData требует ручной настройки метаданных в каждой базе через Конфигуратор
- **Требуемое решение:** Автоматическая настройка OData на всех 700 базах за 1-2 часа
- **Ограничения:** Файловые базы, типовая конфигурация 1С:Бухгалтерия 3.0 без изменений

### 1.3. Бизнес-требования

- ⚡ Время настройки 700 баз: не более 2 часов
- 🔄 Параллельная обработка: минимум 10 баз одновременно
- 📊 Логирование всех операций
- ✅ Повторяемость процесса для новых баз
- 🔒 Не изменять типовую конфигурацию

---

## 2. Архитектура решения

### 2.1. Компоненты системы

```
┌─────────────────────────────────────────────────────────────┐
│                    PowerShell Master Script                  │
│         (координирует установку на 700 баз)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │  Параллельная обработка │
        │  (10 баз одновременно)  │
        └────────┬───────┬────────┘
                 │       │
    ┌────────────▼───┐ ┌▼────────────┐
    │  1cv8.exe      │ │  1cv8.exe   │  ... × 10
    │  CONFIG        │ │  CONFIG     │
    └────────┬───────┘ └┬────────────┘
             │           │
    ┌────────▼──────┐ ┌─▼────────────┐
    │  База 1С #1   │ │  База 1С #2  │  ... × 700
    │  + CFE        │ │  + CFE       │
    └───────────────┘ └──────────────┘
```

### 2.2. Технологический стек

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| **CFE расширение** | 1С:Предприятие 8.3 | Автоконфигурация OData |
| **Скрипт установки** | PowerShell 7+ | Массовая установка |
| **Платформа 1С** | 1cv8.exe (CONFIG) | Загрузка расширений |
| **Логирование** | PowerShell + CSV | Отчеты об установке |

---

## 3. Компонент 1: CFE расширение "ODataAutoConfig"

### 3.1. Назначение

Расширение конфигурации, которое автоматически настраивает публикацию OData при установке в информационную базу.

### 3.2. Функциональные требования

#### 3.2.1. Настройка метаданных OData

Расширение должно программно:

1. **Создать HTTP-сервис для OData:**
   - Имя сервиса: `standard.odata`
   - Корневой URL: `/odata/standard.odata`
   - Протокол: HTTP/HTTPS

2. **Опубликовать ключевые справочники:**
   - Справочник.Организации
   - Справочник.Контрагенты
   - Справочник.Номенклатура
   - Справочник.Пользователи
   - Справочник.Патенты (если есть)
   - Дополнительные справочники из списка

3. **Опубликовать ключевые документы:**
   - Документ.РеализацияТоваровУслуг
   - Документ.ПоступлениеТоваровУслуг
   - (список дополнить согласно требованиям)

4. **Настроить права доступа:**
   - Создать роль "ODataUser" с правами на чтение/запись
   - Назначить роль пользователю для OData (или всем пользователям)

#### 3.2.2. Регистрация в CommandCenter

После настройки OData расширение должно:

1. Отправить HTTP POST запрос на CommandCenter Orchestrator
2. Эндпоинт: `http://orchestrator:8000/api/v1/databases/register`
3. Данные для регистрации:
   ```json
   {
     "name": "База 1С - {ИмяОрганизации}",
     "odata_url": "http://{host}/{base}/odata/standard.odata",
     "username": "ODataUser",
     "password_encrypted": "...",
     "status": "active",
     "metadata": {
       "version": "3.0.115.30",
       "installation_date": "2025-10-25T12:00:00Z"
     }
   }
   ```

#### 3.2.3. Логирование

- Записывать в журнал регистрации 1С все операции настройки
- Сохранять информацию об ошибках в отдельный лог-файл в базе

### 3.3. Нефункциональные требования

- **Производительность:** Установка и настройка < 60 секунд на базу
- **Надежность:** Откат изменений при ошибке
- **Совместимость:** 1С:Бухгалтерия 3.0 версии 3.0.100+
- **Размер:** Расширение < 1 МБ

### 3.4. Структура расширения

```
ODataAutoConfig.cfe
├── Конфигурация
│   ├── HTTPСервисы
│   │   └── standard_odata
│   ├── ОбщиеМодули
│   │   ├── ОбработчикПриУстановкеРасширения
│   │   ├── НастройкаOData
│   │   └── РегистрацияВCommandCenter
│   └── Роли
│       └── ODataUser
└── Справочная информация.txt
```

### 3.5. Пример кода модуля установки

```bsl
// ОбщийМодуль.ОбработчикПриУстановкеРасширения

Процедура ПриУстановкеРасширения() Экспорт

    Попытка
        // 1. Настройка OData
        НастройкаOData.СоздатьHTTPСервис();
        НастройкаOData.ОпубликоватьСправочники();
        НастройкаOData.НастроитьПраваДоступа();

        // 2. Регистрация в CommandCenter
        РегистрацияВCommandCenter.ЗарегистрироватьБазу();

        // 3. Логирование успеха
        ЗаписьЖурналаРегистрации(
            "ODataAutoConfig.Установка",
            Уровень.Информация,
            ,
            ,
            "Расширение успешно установлено и настроено"
        );

    Исключение
        // Откат изменений
        ОтменитьТранзакцию();

        ЗаписьЖурналаРегистрации(
            "ODataAutoConfig.Ошибка",
            Уровень.Ошибка,
            ,
            ,
            ПодробноеПредставлениеОшибки(ИнформацияОбОшибке())
        );

        ВызватьИсключение;
    КонецПопытки;

КонецПроцедуры

// ОбщийМодуль.НастройкаOData

Процедура СоздатьHTTPСервис() Экспорт

    // Программное создание HTTP-сервиса OData
    МетаданныеHTTPСервиса = Метаданные.HTTPСервисы.standard_odata;

    // Настройка параметров публикации
    // (детальная реализация зависит от API платформы)

КонецПроцедуры

Процедура ОпубликоватьСправочники() Экспорт

    МассивСправочников = Новый Массив;
    МассивСправочников.Добавить("Организации");
    МассивСправочников.Добавить("Контрагенты");
    МассивСправочников.Добавить("Номенклатура");
    // ... и т.д.

    Для Каждого ИмяСправочника Из МассивСправочников Цикл
        ОпубликоватьОбъектВOData("Справочник", ИмяСправочника);
    КонецЦикла;

КонецПроцедуры

// ОбщийМодуль.РегистрацияВCommandCenter

Процедура ЗарегистрироватьБазу() Экспорт

    // Получить параметры текущей базы
    ПараметрыБазы = ПолучитьПараметрыТекущейБазы();

    // Подготовить JSON для отправки
    ДанныеJSON = ПодготовитьДанныеРегистрации(ПараметрыБазы);

    // Отправить HTTP POST запрос
    HTTPСоединение = Новый HTTPСоединение(
        "orchestrator", // или IP адрес
        8000,
        ,
        ,
        ,
        30 // таймаут
    );

    Запрос = Новый HTTPЗапрос("/api/v1/databases/register");
    Запрос.УстановитьТелоИзСтроки(ДанныеJSON, КодировкаТекста.UTF8);

    Ответ = HTTPСоединение.ОтправитьДляОбработки(Запрос);

    Если Ответ.КодСостояния <> 200 И Ответ.КодСостояния <> 201 Тогда
        ВызватьИсключение "Ошибка регистрации в CommandCenter: " + Ответ.ПолучитьТелоКакСтроку();
    КонецЕсли;

КонецПроцедуры
```

---

## 4. Компонент 2: PowerShell скрипт массовой установки

### 4.1. Назначение

Автоматизация установки CFE расширения на 700 баз 1С с параллельной обработкой.

### 4.2. Функциональные требования

#### 4.2.1. Конфигурация

Скрипт должен читать конфигурацию из JSON файла:

```json
{
  "extension": {
    "path": "C:\\Extensions\\ODataAutoConfig.cfe",
    "name": "ODataAutoConfig"
  },
  "platform": {
    "path": "C:\\Program Files\\1cv8\\8.3.23.1912\\bin\\1cv8.exe"
  },
  "databases": [
    {
      "path": "D:\\1CBases\\Base001",
      "user": "Администратор",
      "password": ""
    },
    {
      "path": "D:\\1CBases\\Base002",
      "user": "Администратор",
      "password": ""
    }
    // ... еще 698 баз
  ],
  "parallel": {
    "throttle_limit": 10,
    "timeout_seconds": 300
  },
  "logging": {
    "log_file": "C:\\Logs\\odata_installation.log",
    "csv_report": "C:\\Logs\\odata_installation_report.csv"
  }
}
```

#### 4.2.2. Основные операции

1. **Загрузка расширения в базу:**
   ```powershell
   & $1cPath CONFIG /F"$dbPath" /N"$user" /P"$password" `
     /LoadCfg "$extensionPath" -Extension "$extensionName"
   ```

2. **Обновление конфигурации БД (применение расширения):**
   ```powershell
   & $1cPath CONFIG /F"$dbPath" /N"$user" /P"$password" `
     /UpdateDBCfg -Extension "$extensionName"
   ```

3. **Проверка успешности установки:**
   - Проверить exit code процесса 1cv8.exe
   - Проверить доступность OData endpoint (HTTP GET)

#### 4.2.3. Параллельная обработка

- Использовать `ForEach-Object -Parallel -ThrottleLimit 10`
- Контроль timeout для каждой базы (по умолчанию 300 сек)
- Обработка ошибок и повтор неудачных установок

#### 4.2.4. Логирование и отчетность

**Лог-файл (текстовый):**
```
[2025-10-25 12:00:00] INFO: Starting installation for 700 databases
[2025-10-25 12:00:01] INFO: Processing batch 1/70 (10 databases)
[2025-10-25 12:01:15] SUCCESS: Base001 - Extension installed successfully
[2025-10-25 12:01:16] ERROR: Base002 - Timeout exceeded
[2025-10-25 12:01:17] SUCCESS: Base003 - Extension installed successfully
...
[2025-10-25 13:30:00] INFO: Installation completed. Success: 695, Failed: 5
```

**CSV отчет:**
```csv
DatabasePath,Status,Duration,ErrorMessage,Timestamp
D:\1CBases\Base001,Success,45,,"2025-10-25 12:01:15"
D:\1CBases\Base002,Failed,300,Timeout exceeded,"2025-10-25 12:01:16"
D:\1CBases\Base003,Success,38,,"2025-10-25 12:01:17"
...
```

### 4.3. Пример реализации скрипта

```powershell
# Install-ODataExtension.ps1
# Массовая установка CFE расширения ODataAutoConfig на базы 1С

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$ConfigFile = "config.json"
)

# Чтение конфигурации
$config = Get-Content $ConfigFile | ConvertFrom-Json

# Инициализация логирования
$logFile = $config.logging.log_file
$csvReport = $config.logging.csv_report

function Write-Log {
    param([string]$Level, [string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Level: $Message"
    Write-Host $logEntry
    Add-Content -Path $logFile -Value $logEntry
}

function Install-ExtensionToDatabase {
    param(
        [string]$DbPath,
        [string]$User,
        [string]$Password,
        [string]$ExtensionPath,
        [string]$ExtensionName,
        [string]$PlatformPath
    )

    $startTime = Get-Date
    $status = "Success"
    $errorMessage = ""

    try {
        Write-Log "INFO" "Installing extension to: $DbPath"

        # Шаг 1: Загрузка расширения
        $loadArgs = @(
            "CONFIG",
            "/F`"$DbPath`"",
            "/N`"$User`"",
            "/P`"$Password`"",
            "/LoadCfg `"$ExtensionPath`"",
            "-Extension `"$ExtensionName`""
        )

        $process = Start-Process -FilePath $PlatformPath `
            -ArgumentList $loadArgs `
            -Wait -PassThru -NoNewWindow `
            -RedirectStandardOutput "nul" `
            -RedirectStandardError "nul"

        if ($process.ExitCode -ne 0) {
            throw "LoadCfg failed with exit code: $($process.ExitCode)"
        }

        # Шаг 2: Обновление конфигурации БД
        $updateArgs = @(
            "CONFIG",
            "/F`"$DbPath`"",
            "/N`"$User`"",
            "/P`"$Password`"",
            "/UpdateDBCfg",
            "-Extension `"$ExtensionName`""
        )

        $process = Start-Process -FilePath $PlatformPath `
            -ArgumentList $updateArgs `
            -Wait -PassThru -NoNewWindow `
            -RedirectStandardOutput "nul" `
            -RedirectStandardError "nul"

        if ($process.ExitCode -ne 0) {
            throw "UpdateDBCfg failed with exit code: $($process.ExitCode)"
        }

        # Шаг 3: Проверка доступности OData (опционально)
        # TODO: Добавить HTTP проверку endpoint

        Write-Log "SUCCESS" "Extension installed successfully: $DbPath"

    } catch {
        $status = "Failed"
        $errorMessage = $_.Exception.Message
        Write-Log "ERROR" "Failed to install extension to $DbPath : $errorMessage"
    }

    $duration = ((Get-Date) - $startTime).TotalSeconds

    return @{
        DatabasePath = $DbPath
        Status = $status
        Duration = [math]::Round($duration, 2)
        ErrorMessage = $errorMessage
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
}

# Главная логика
Write-Log "INFO" "Starting installation for $($config.databases.Count) databases"
Write-Log "INFO" "Parallel processing: $($config.parallel.throttle_limit) databases at once"

$results = @()

$config.databases | ForEach-Object -Parallel {

    # Импорт функций в параллельный scope
    $localConfig = $using:config
    $logFile = $using:logFile

    . $using:MyInvocation.MyCommand.Path

    $result = Install-ExtensionToDatabase `
        -DbPath $_.path `
        -User $_.user `
        -Password $_.password `
        -ExtensionPath $localConfig.extension.path `
        -ExtensionName $localConfig.extension.name `
        -PlatformPath $localConfig.platform.path

    return $result

} -ThrottleLimit $config.parallel.throttle_limit | ForEach-Object {
    $results += $_
}

# Сохранение отчета в CSV
$results | Export-Csv -Path $csvReport -NoTypeInformation -Encoding UTF8

# Итоговая статистика
$successCount = ($results | Where-Object { $_.Status -eq "Success" }).Count
$failedCount = ($results | Where-Object { $_.Status -eq "Failed" }).Count

Write-Log "INFO" "==================== FINAL REPORT ===================="
Write-Log "INFO" "Total databases: $($config.databases.Count)"
Write-Log "INFO" "Successfully installed: $successCount"
Write-Log "INFO" "Failed: $failedCount"
Write-Log "INFO" "Report saved to: $csvReport"

if ($failedCount -gt 0) {
    Write-Log "WARNING" "Some installations failed. Check the report for details."
    exit 1
} else {
    Write-Log "SUCCESS" "All installations completed successfully!"
    exit 0
}
```

---

## 5. Интеграция с CommandCenter1C

### 5.1. API для регистрации баз

Django Orchestrator должен предоставить REST API endpoint:

**POST /api/v1/databases/register**

Тело запроса:
```json
{
  "name": "string",
  "odata_url": "string",
  "username": "string",
  "password_encrypted": "string",
  "status": "active",
  "metadata": {
    "version": "string",
    "installation_date": "datetime"
  }
}
```

Ответ (201 Created):
```json
{
  "id": "uuid",
  "name": "string",
  "status": "active",
  "created_at": "datetime"
}
```

### 5.2. Мониторинг установки

Django должен отслеживать:
- Количество баз с установленным расширением
- Количество баз без расширения (требуют установки)
- Статус последней попытки установки

---

## 6. План реализации

### 6.1. Этапы разработки

| Этап | Задачи | Срок | Ответственный |
|------|--------|------|---------------|
| **1. Проектирование** | Детальная проработка архитектуры CFE | 1 день | Architect |
| **2. Разработка CFE** | Создание расширения ODataAutoConfig | 3-5 дней | Coder + 1С Developer |
| **3. Разработка PowerShell** | Скрипт массовой установки | 1 день | Coder |
| **4. Интеграция API** | Endpoint регистрации в Orchestrator | 1 день | Coder |
| **5. Тестирование** | Тестирование на 10-20 базах | 2 дня | Tester |
| **6. Пилот** | Установка на 50 баз (пилот) | 0.5 дня | DevOps |
| **7. Production** | Установка на все 700 баз | 0.1 дня (1-2 часа) | DevOps |
| **8. Проверка** | Верификация всех установок | 1 день | QA |

**Итого:** 8-10 дней от начала до полного развертывания.

### 6.2. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Ошибки в CFE расширении | Средняя | Высокое | Тщательное тестирование на 10-20 базах |
| Timeout при установке | Низкая | Среднее | Увеличить timeout, повторная установка |
| Блокировка баз пользователями | Высокая | Среднее | Установка в нерабочее время |
| Несовместимость с версиями 1С | Низкая | Высокое | Проверка версий перед установкой |
| Отказ в регистрации (Orchestrator) | Низкая | Низкое | Retry механизм, ручная регистрация |

---

## 7. Критерии приемки

### 7.1. CFE расширение

- ✅ Расширение устанавливается без ошибок на типовую конфигурацию
- ✅ OData endpoint доступен сразу после установки
- ✅ Опубликованы все ключевые справочники и документы
- ✅ База автоматически регистрируется в CommandCenter
- ✅ Время установки < 60 секунд

### 7.2. PowerShell скрипт

- ✅ Скрипт корректно читает конфигурацию из JSON
- ✅ Параллельная обработка работает стабильно
- ✅ Логирование всех операций
- ✅ CSV отчет генерируется корректно
- ✅ Обработка ошибок и timeout

### 7.3. Интеграция

- ✅ API endpoint регистрации работает корректно
- ✅ Базы регистрируются автоматически после установки
- ✅ Django Admin показывает статус установки расширений

### 7.4. Production

- ✅ Успешная установка на ≥ 95% баз (665+ из 700)
- ✅ Время установки на все 700 баз < 3 часов
- ✅ Все зарегистрированные базы доступны через OData

---

## 8. Документация

### 8.1. Документы для разработки

1. **CFE_DEVELOPMENT_GUIDE.md** - Руководство по разработке расширения
2. **POWERSHELL_SCRIPT_GUIDE.md** - Руководство по использованию скрипта
3. **API_INTEGRATION.md** - Описание API интеграции с Orchestrator

### 8.2. Эксплуатационная документация

1. **DEPLOYMENT_MANUAL.md** - Руководство по развертыванию
2. **TROUBLESHOOTING.md** - Руководство по устранению проблем
3. **ROLLBACK_PROCEDURE.md** - Процедура отката изменений

---

## 9. Приложения

### 9.1. Пример config.json

См. раздел 4.2.1

### 9.2. Список справочников для публикации OData

```
Справочники:
- Организации
- Контрагенты
- Номенклатура
- Пользователи
- Склады
- Валюты
- БанковскиеСчета
- ДоговорыКонтрагентов
- СтавкиНДС

Документы:
- РеализацияТоваровУслуг
- ПоступлениеТоваровУслуг
- ПлатежноеПоручение
- ПриходныйКассовыйОрдер
- РасходныйКассовыйОрдер
```

### 9.3. Контакты

- **Architect:** [Имя]
- **Coder (1С):** [Имя]
- **Coder (PowerShell):** [Имя]
- **Tester:** [Имя]
- **Product Owner:** [Имя]

---

**Утверждено:**
[Подпись]
[Дата]
