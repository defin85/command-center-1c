# 1C:Enterprise DESIGNER Mode Commands Reference

> Comprehensive reference для всех команд пакетного режима 1С:Предприятие 8.x
>
> Источник: https://yellow-erp.com/help/1cv8/ZIF3/
> Дата компиляции: 2025-11-09

---

## Навигация

- [Extension Management](#extension-management) - Управление расширениями
- [Configuration Management](#configuration-management) - Управление конфигурацией
- [Database Operations](#database-operations) - Операции с БД
- [Repository Operations](#repository-operations) - Работа с хранилищем
- [File Operations](#file-operations) - Операции с файлами
- [Validation Commands](#validation-commands) - Проверка и валидация
- [Utility Commands](#utility-commands) - Вспомогательные команды
- [Return Codes](#return-codes) - Коды возврата

---

## Extension Management

### /LoadCfg <CF file name> [-Extension <extension name>]

**Описание:** Загружает конфигурацию или расширение из файла .cf/.cfe

**Параметры:**
- `<CF file name>` - путь к .cf или .cfe файлу
- `-Extension <extension name>` - загрузить расширение с указанным именем

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Загрузить расширение из файла
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /LoadCfg "C:\extensions\MyExtension.cfe" -Extension "MyExt"

# Загрузить основную конфигурацию
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /LoadCfg "C:\configs\MainConfig.cf"
```

**Особенности:**
- Если расширение не найдено - создает новое
- Если указан полный путь - убедитесь что все директории существуют
- Расширения загружаются в основную конфигурацию

---

### /DumpCfg <CF file name> [-Extension <extension name>]

**Описание:** Сохраняет конфигурацию или расширение в файл

**Параметры:**
- `<CF file name>` - путь к .cf или .cfe файлу
- `-Extension <extension name>` - сохранить расширение с указанным именем

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Выгрузить расширение в файл
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /DumpCfg "C:\backup\MyExtension.cfe" -Extension "MyExt"

# Выгрузить основную конфигурацию
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /DumpCfg "C:\backup\MainConfig.cf"
```

**Особенности:**
- Если указан полный путь - убедитесь что все директории существуют
- Файл перезаписывается без предупреждения

---

### /DeleteCfg [-Extension <extension name>] [-AllExtensions]

**Описание:** Удаляет расширения конфигурации. Команда требует хотя бы один параметр.

**Параметры:**
- `-Extension <extension name>` - удалить расширение с указанным именем
- `-AllExtensions` - удалить все расширения конфигурации

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено, отсутствуют параметры или произошла ошибка)

**Примеры:**
```bash
# Удалить одно расширение
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /DeleteCfg -Extension "MyExtension"

# Удалить все расширения
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /DeleteCfg -AllExtensions
```

**Особенности:**
- Команда без параметров возвращает ошибку
- Удаление необратимо - нет автоматического бэкапа

---

### /DumpDBCfg <CF file name> [-Extension <extension name>]

**Описание:** Сохраняет конфигурацию базы данных в файл

**Параметры:**
- `<CF file name>` - путь к .cf или .cfe файлу
- `-Extension <extension name>` - сохранить расширение БД с указанным именем

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Выгрузить конфигурацию БД
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /DumpDBCfg "C:\backup\DBConfig.cf"

# Выгрузить расширение БД
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /DumpDBCfg "C:\backup\DBExtension.cfe" -Extension "MyExt"
```

**Особенности:**
- Сохраняет конфигурацию базы данных, а не основную конфигурацию
- Если указан полный путь - убедитесь что все директории существуют

---

### /RollbackCfg [-Extension <extension name>]

**Описание:** Откатывает конфигурацию базы данных к основной конфигурации

**Параметры:**
- `-Extension <extension name>` - откатить расширение с указанным именем

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Откатить основную конфигурацию БД
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /RollbackCfg

# Откатить расширение
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /RollbackCfg -Extension "MyExtension"
```

**Особенности:**
- Откатывает изменения в конфигурации БД к основной конфигурации
- Используется для отмены изменений до обновления БД

---

## Configuration Management

### /UpdateDBCfg [options]

**Описание:** Выполняет динамическое обновление конфигурации базы данных (если возможно)

**Параметры:**
- `-Dynamic<mode>` - показывает будет ли выполнено динамическое обновление:
  - `-Dynamic+` - попытка динамического обновления, если неудачно - фоновое (по умолчанию)
  - `-Dynamic` - запретить динамическое обновление
- `-BackgroundStart [-Dynamic<mode>]` - запустить фоновое обновление и закрыть сессию
- `-BackgroundCancel` - отменить запущенное фоновое обновление
- `-BackgroundFinish` - завершить запущенное фоновое обновление
- `-BackgroundSuspend` - приостановить фоновое обновление
- `-BackgroundResume` - возобновить приостановленное обновление
- `-WarningsAsErrors` - трактовать все предупреждения как ошибки
- `-Server` - выполнить обновление на сервере
- `-Extension <extension name>` - обновить расширение с указанным именем

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Обновить конфигурацию БД (динамическое)
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /UpdateDBCfg

# Запустить фоновое обновление
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /UpdateDBCfg -BackgroundStart

# Завершить фоновое обновление
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /UpdateDBCfg -BackgroundFinish

# Обновить расширение
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /UpdateDBCfg -Extension "MyExtension"
```

**Использование с другими командами:**
```bash
# После загрузки конфигурации
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /LoadCfg "config.cf" /UpdateDBCfg

# После обновления поддерживаемой конфигурации
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /UpdateCfg "update.cfu" /UpdateDBCfg
```

**Особенности:**
- Может использоваться как параметр для /LoadCfg, /UpdateCfg, /ConfigurationRepositoryUpdateCfg
- Фоновое обновление позволяет продолжить работу пользователей
- Финальная часть требует монопольного доступа

---

### /UpdateCfg <CF|CFU file name> -Settings <settings file name> [options]

**Описание:** Обновляет поддерживаемую конфигурацию

**Параметры:**
- `<CF|CFU file name>` - путь к файлу обновления .cf или .cfu
- `-Settings <settings file name>` - имя файла с настройками слияния
- `-IncludeObjectsByUnresolvedRefs` - включить объекты по неразрешенным ссылкам
- `-ClearUnresolvedRefs` - очистить неразрешенные ссылки
- `-force` - выполнить обновление несмотря на предупреждения
- `-DumpListOfTwiceChangedProperties` - вывести список дважды измененных свойств

**Return codes:**
- `0` - успешно
- `1` - ошибка

**Примеры:**
```bash
# Обновить поддерживаемую конфигурацию
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /UpdateCfg "update.cfu" -Settings "settings.xml"

# С принудительным обновлением
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /UpdateCfg "update.cfu" -Settings "settings.xml" -force
```

**Особенности:**
- Если указан полный путь - убедитесь что все директории существуют
- Файл настроек управляет процессом слияния
- Флаг -force игнорирует предупреждения о конфликтах

---

### /CompareCfg [options]

**Описание:** Генерирует отчет сравнения конфигураций

**Параметры:**

**Типы конфигураций:**
- `-FirstConfigurationType` / `-SecondConfigurationType`:
  - `MainConfiguration` - основная конфигурация
  - `DBConfiguration` - конфигурация БД
  - `VendorConfiguration` - конфигурация поставщика
  - `ExtensionConfiguration` - расширение конфигурации
  - `ExtensionDBConfiguration` - расширение конфигурации (БД)
  - `ConfigurationRepository` - конфигурация из хранилища
  - `File` - файл конфигурации или расширения

**Ключи конфигураций:**
- `-FirstConfigurationKey` / `-SecondConfigurationKey` - ID конфигурации (зависит от типа)

**Опции сравнения:**
- `-MappingRule` - правило сопоставления объектов:
  - `ByObjectNames` - по именам объектов (по умолчанию)
  - `ByObjectIDs` - по ID объектов
- `-Objects` - путь к XML файлу со списком объектов для сравнения
- `-ReportType`:
  - `Brief` - краткий отчет
  - `Full` - полный отчет
- `-IncludeChangedObjects` - включить измененные подчиненные объекты
- `-IncludeDeletedObjects` - включить удаленные подчиненные объекты
- `-IncludeAddedObjects` - включить добавленные подчиненные объекты
- `-ReportFormat`:
  - `txt` - текстовый документ
  - `mxl` - табличный документ
- `-ReportFile` - путь к файлу отчета

**Примеры:**
```bash
# Сравнить основную и БД конфигурации
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CompareCfg ^
  -FirstConfigurationType MainConfiguration ^
  -SecondConfigurationType DBConfiguration ^
  -ReportType Full ^
  -ReportFormat txt ^
  -ReportFile "C:\reports\compare.txt"

# Сравнить расширение с файлом
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CompareCfg ^
  -FirstConfigurationType ExtensionConfiguration ^
  -FirstConfigurationKey "MyExtension" ^
  -SecondConfigurationType File ^
  -SecondConfigurationKey "C:\extensions\NewVersion.cfe" ^
  -ReportType Brief ^
  -ReportFormat mxl ^
  -ReportFile "C:\reports\extension_compare.mxl"
```

**Особенности:**
- Подробные отчеты показывают изменения на уровне свойств
- Сопоставление по ID используется для связанных конфигураций
- Формат mxl удобен для анализа в табличном виде

---

### /MergeCfg <CF file name> -Settings <settings file name> [options]

**Описание:** Объединяет текущую конфигурацию с файлом используя файл настроек

**Параметры:**
- `<CF file name>` - путь к .cf файлу
- `-Settings <settings file name>` - имя файла с настройками слияния
- `-EnableSupport | -DisableSupport` - режим поддержки:
  - `-EnableSupport` - включить поддержку (если возможно)
  - `-DisableSupport` - отключить поддержку
- `-IncludeObjectsByUnresolvedRefs` - включить объекты по неразрешенным ссылкам
- `-ClearUnresolvedRefs` - очистить неразрешенные ссылки
- `-force` - выполнить слияние несмотря на предупреждения

**Return codes:**
- `0` - успешно
- `1` - ошибка

**Примеры:**
```bash
# Объединить конфигурацию
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /MergeCfg "merge_config.cf" -Settings "merge_settings.xml"

# С включением поддержки
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /MergeCfg "vendor_config.cf" -Settings "merge_settings.xml" -EnableSupport
```

**Особенности:**
- Если указан полный путь - убедитесь что все директории существуют
- Флаг -force игнорирует предупреждения о конфликтах и удалении объектов

---

### /ManageCfgSupport [-disableSupport] [-force]

**Описание:** Управление настройками поддержки конфигурации

**Параметры:**
- `-disableSupport` - отключить поддержку конфигурации
- `-force` - отключить поддержку даже если изменение конфигурации запрещено

**Return codes:**
- `0` - успешно
- `1` - ошибка

**Примеры:**
```bash
# Отключить поддержку конфигурации
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /ManageCfgSupport -disableSupport

# Принудительно отключить поддержку
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /ManageCfgSupport -disableSupport -force
```

**Особенности:**
- Без параметра -disableSupport добавляет сообщение об ошибке в лог
- Флаг -force игнорирует запрет на изменение конфигурации

---

## Database Operations

### /EraseData [/Z[<separators>]]

**Описание:** Удаляет данные информационной базы

**Параметры:**
- `/Z[<separators>]` - область удаления данных

**Удаляемые данные:**
- Таблицы определенные структурой метаданных
- Хранилища настроек
- История
- Параметры администрирования ИБ
- Список пользователей
- Временная зона (при определенных условиях)

**Сброс настроек (если сессия не использует разделители):**
- Timeout блокировки данных
- Минимальная длина пароля пользователя
- Проверка сложности пароля
- Доступность полнотекстового поиска

**Примеры:**
```bash
# Удалить все данные
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /EraseData
```

**Особенности:**
- Данные могут удалять только пользователи с правом "Администрирование"
- Операция необратима - используйте с осторожностью
- Рекомендуется создать резервную копию перед выполнением

---

## Repository Operations

### /ConfigurationRepositoryUpdateCfg [options]

**Описание:** Обновляет конфигурацию из хранилища (пакетный режим)

**Параметры:**
- `-v <repository version number>` - номер версии в хранилище:
  - Если конфигурация подключена к хранилищу - игнорируется, берется последняя версия
  - Если не подключена - берется указанная версия (или последняя если -1 или не указано)
- `-revised` - получить все объекты из хранилища, перезаписав локальные изменения
- `-force` - подтвердить получение/удаление объектов
- `-objects <object list file name>` - путь к XML файлу со списком объектов

**Return codes:**
- `0` - успешно
- `1` - ошибка

**Примеры:**
```bash
# Обновить конфигурацию из хранилища (последняя версия)
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /ConfigurationRepositoryUpdateCfg

# Обновить конкретную версию
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /ConfigurationRepositoryUpdateCfg -v 125

# Принудительно перезаписать локальные изменения
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /ConfigurationRepositoryUpdateCfg -revised -force

# Обновить только указанные объекты
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /ConfigurationRepositoryUpdateCfg -objects "objects.xml"
```

**Особенности:**
- Если указан файл объектов с полным путем - убедитесь что все директории существуют
- Флаг -revised перезаписывает локальные изменения заблокированных объектов
- Флаг -force требуется для подтверждения изменений структуры

---

### /ConfigurationRepositoryDumpCfg <CF file name> [-v <repository version number>]

**Описание:** Сохранить конфигурацию из хранилища в файл (пакетный режим)

**Параметры:**
- `<CF file name>` - путь к .cf файлу
- `-v <repository version number>` - номер версии (если не указано или -1 - последняя версия)

**Return codes:**
- `0` - успешно
- `1` - ошибка

**Примеры:**
```bash
# Выгрузить последнюю версию из хранилища
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /ConfigurationRepositoryDumpCfg "C:\backup\repo_latest.cf"

# Выгрузить конкретную версию
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /ConfigurationRepositoryDumpCfg "C:\backup\repo_v125.cf" -v 125
```

**Особенности:**
- Не требует подключения к хранилищу если указан номер версии
- Позволяет получить любую версию конфигурации из истории

---

### /ConfigurationRepositoryLock [options]

**Описание:** Заблокировать объекты хранилища для редактирования

**Параметры:**
- `-objects <object list file name>` - путь к XML файлу со списком объектов
  - Если не указан - попытка заблокировать все объекты конфигурации
  - Если объект заблокирован другим пользователем - отображается ошибка
- `-revised` - получить заблокированные объекты из хранилища, перезаписав локальные изменения

**Return codes:**
- `0` - успешно
- `1` - ошибка

**Примеры:**
```bash
# Заблокировать все объекты
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /ConfigurationRepositoryLock

# Заблокировать указанные объекты
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /ConfigurationRepositoryLock -objects "objects_to_lock.xml"

# Заблокировать с принудительным обновлением
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /ConfigurationRepositoryLock -objects "objects_to_lock.xml" -revised
```

**Особенности:**
- Объекты заблокированные другим пользователем не могут быть заблокированы
- Флаг -revised перезаписывает локальные изменения уже заблокированных объектов
- Блокировка необходима для внесения изменений в хранилище

---

### /ConfigurationRepositoryCommit [options]

**Описание:** Сохранить изменения объектов в хранилище конфигурации

**Параметры:**
- `-objects <object list file name>` - путь к XML файлу со списком объектов
  - Если не указан - попытка зафиксировать все объекты
  - Незаблокированные объекты не вызывают ошибок
- `-comment "<comment text>"` - комментарий для новой версии объектов
  - Для многострочных комментариев используйте несколько параметров -comment
- `-keepLocked` - сохранить объекты заблокированными после фиксации
- `-force` - очистить ссылки на удаленные объекты при их наличии

**Return codes:**
- `0` - успешно
- `1` - ошибка

**Примеры:**
```bash
# Зафиксировать все изменения
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /ConfigurationRepositoryCommit -comment "Fix: bug #123"

# Зафиксировать указанные объекты с сохранением блокировки
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /ConfigurationRepositoryCommit ^
  -objects "changed_objects.xml" ^
  -comment "Feature: new report" ^
  -keepLocked

# С многострочным комментарием
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /ConfigurationRepositoryCommit ^
  -comment "Line 1: Summary" ^
  -comment "Line 2: Details" ^
  -comment "Line 3: References"
```

**Особенности:**
- Объекты должны быть заблокированы текущим пользователем
- Флаг -force необходим если есть ссылки на удаленные объекты
- Комментарии важны для истории изменений

---

## File Operations

### /DumpConfigToFiles <dump directory> [options]

**Описание:** Выгрузить конфигурацию в XML файлы

**Параметры:**
- `<dump directory>` - директория для выгрузки конфигурации
- `-Extension <extension name>` - выгрузить расширение с указанным именем
- `-AllExtensions` - выгрузить только расширения (все)
- `-format` - формат структуры файлов выгрузки:
  - `Hierarchical` - иерархическая структура (по умолчанию)
  - `Plain` - плоская структура (все файлы в одной директории)

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Выгрузить конфигурацию (иерархическая структура)
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /DumpConfigToFiles "C:\sources\config"

# Выгрузить в плоскую структуру
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /DumpConfigToFiles "C:\sources\config_flat" -format Plain

# Выгрузить расширение
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /DumpConfigToFiles "C:\sources\extension" -Extension "MyExtension"

# Выгрузить все расширения
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /DumpConfigToFiles "C:\sources\extensions" -AllExtensions
```

**Особенности:**
- Иерархическая структура создает директории соответствующие структуре объектов
- Плоская структура помещает все файлы в одну директорию
- Для каждого расширения создается отдельная директория с соответствующим именем

---

### /LoadConfigFromFiles <dump directory> [options]

**Описание:** Загрузить конфигурацию из файлов

**Параметры:**
- `<dump directory>` - директория с XML файлами конфигурации
- `-Extension <extension name>` - обработать расширение с указанным именем
- `-AllExtensions` - загрузить только расширения (все)
  - Если расширение не найдено - создать его
  - Для каждой поддиректории попытка создать расширение
- `-files` - список файлов для загрузки (разделенный запятыми)
- `-listfile` - файл со списком файлов для загрузки
- `-format` - формат структуры файлов:
  - `Hierarchical` - иерархическая структура (по умолчанию)
  - `Plain` - плоская структура

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Загрузить конфигурацию полностью
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadConfigFromFiles "C:\sources\config"

# Загрузить частично из плоской структуры
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadConfigFromFiles "C:\sources\config_flat" ^
  -format Plain ^
  -files "Document.Sales.xml,Catalog.Products.xml"

# Загрузить файлы из списка
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadConfigFromFiles "C:\sources\config" ^
  -listfile "files_to_load.txt"

# Загрузить расширение
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadConfigFromFiles "C:\sources\extension" -Extension "MyExtension"
```

**Формат файла списка (для -listfile):**
- Кодировка: UTF-8
- Каждое имя файла на новой строке
- Поддерживаемые символы перевода строки: \r\n (новая строка) и \r (возврат каретки)
- Без пустых строк между именами файлов

**Особенности:**
- Загрузка расширений в основную конфигурацию (или наоборот) не поддерживается
- Параметр -listfile игнорируется если указан -files
- Параметры -files и -format позволяют частичную загрузку

---

### /DumpConfigFiles <dump directory> [options]

**Описание:** Выгружает свойства объектов метаданных конфигурации (модули, шаблоны, картинки, права, справка)

**Параметры:**
- `<dump directory>` - директория для хранения файлов свойств
- `-Module` - выгружать ли модули
- `-Template` - выгружать ли шаблоны
- `-Help` - выгружать ли темы справки
- `-AllWritable` - выгружать ли только изменяемые объекты
- `-Picture` - выгружать ли общие картинки
- `-Right` - выгружать ли права
- `-Extension <extension name>` - обработать расширение с указанным именем

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Выгрузить только модули
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /DumpConfigFiles "C:\sources\modules" -Module

# Выгрузить модули и шаблоны
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /DumpConfigFiles "C:\sources\config_parts" -Module -Template

# Выгрузить все свойства расширения
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /DumpConfigFiles "C:\sources\extension_parts" ^
  -Module -Template -Help -Picture -Right ^
  -Extension "MyExtension"
```

**Особенности:**
- Позволяет выгружать только определенные части конфигурации
- Флаг -AllWritable ограничивает выгрузку только изменяемыми объектами
- Полезно для системы контроля версий (VCS)

---

### /LoadConfigFiles <dump directory> [options]

**Описание:** Загружает свойства объектов метаданных конфигурации (модули, шаблоны, картинки, права, справка)

**Параметры:**
- `<dump directory>` - директория с файлами свойств
- `-Module` - загружать ли модули
- `-Template` - загружать ли шаблоны
- `-Help` - загружать ли темы справки
- `-AllWritable` - загружать ли только изменяемые объекты
- `-Picture` - загружать ли общие картинки
- `-Right` - загружать ли права
- `-Extension <extension name>` - обработать расширение с указанным именем

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Загрузить только модули
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadConfigFiles "C:\sources\modules" -Module

# Загрузить модули и шаблоны
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadConfigFiles "C:\sources\config_parts" -Module -Template

# Загрузить все свойства расширения
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadConfigFiles "C:\sources\extension_parts" ^
  -Module -Template -Help -Picture -Right ^
  -Extension "MyExtension"
```

**Особенности:**
- Загружает только указанные типы свойств
- Флаг -AllWritable ограничивает загрузку только изменяемыми объектами
- Полезно для интеграции с системой контроля версий (VCS)

---

## Validation Commands

### /CheckConfig [options]

**Описание:** Выполняет расширенную проверку конфигурации

**Параметры проверки:**

**Базовые проверки:**
- `-ConfigLogIntegrity` - проверка логической целостности конфигурации (стандартная проверка перед обновлением БД)
- `-IncorrectReferences` - поиск ссылок на удаленные объекты и логически некорректных ссылок

**Проверки синтаксиса модулей (режимы эмуляции):**
- `-ThinClient` - режим управляемого приложения (тонкий клиент), файловый режим
- `-WebClient` - режим веб-клиента
- `-Server` - режим сервера 1С:Предприятие
- `-ExternalConnection` - режим внешнего соединения, файловый режим
- `-ExternalConnectionServer` - режим внешнего соединения, клиент-сервер
- `-MobileAppClient` - режим мобильного приложения (клиент)
- `-MobileAppServer` - режим мобильного приложения (сервер)
- `-ThickClientManagedApplication` - управляемое приложение (толстый клиент), файловый режим
- `-ThickClientServerManagedApplication` - управляемое приложение (толстый клиент), клиент-сервер
- `-ThickClientOrdinaryApplication` - обычное приложение (толстый клиент), файловый режим
- `-ThickClientServerOrdinaryApplication` - обычное приложение (толстый клиент), клиент-сервер

**Дополнительные проверки:**
- `-DistributiveModules` - проверка возможности генерации образов модулей (модули без исходных кодов)
- `-UnreferenceProcedures` - поиск локальных (неэкспортируемых) процедур и функций без ссылок
- `-HandlersExistence` - проверка наличия назначенных обработчиков для интерфейсов, форм и элементов управления
- `-EmptyHandlers` - поиск обработчиков событий без действий (могут влиять на производительность)
- `-ExtendedModulesCheck` - проверка вызовов методов и свойств объектов
- `-CheckUseModality` - поиск модальных методов (только с -ExtendedModulesCheck)
- `-UnsupportedFunctional` - поиск функциональности неподдерживаемой в мобильном приложении

**Проверка расширений:**
- `-Extension <extension name>` - проверить расширение с указанным именем
- `-AllExtensions` - проверить все расширения

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Базовая проверка целостности
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckConfig -ConfigLogIntegrity

# Полная проверка конфигурации
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckConfig ^
  -ConfigLogIntegrity ^
  -IncorrectReferences ^
  -ThinClient ^
  -WebClient ^
  -Server

# Проверка модулей с расширенным анализом
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckConfig ^
  -ExtendedModulesCheck ^
  -CheckUseModality ^
  -UnreferenceProcedures ^
  -EmptyHandlers

# Проверка расширения
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckConfig -Extension "MyExtension" -ThinClient -WebClient
```

**Особенности:**
- Проверка модулей выполняется для каждого указанного режима
- -CheckUseModality работает только вместе с -ExtendedModulesCheck
- -UnsupportedFunctional ищет метаданные неподдерживаемые на мобильной платформе

---

### /CheckModules [options]

**Описание:** Выполняет проверку модулей. Требуется хотя бы одна опция проверки.

**Параметры:**
- `-ThinClient` - проверка в режиме тонкого клиента
- `-WebClient` - проверка в режиме веб-клиента
- `-Server` - проверка в режиме сервера 1С:Предприятие
- `-ExternalConnection` - проверка в режиме внешнего соединения
- `-ThickClientOrdinaryApplication` - проверка в режиме клиентского приложения
- `-MobileAppClient` - проверка в режиме мобильного приложения (клиент)
- `-MobileAppServer` - проверка в режиме мобильного приложения (сервер)
- `-ExtendedModulesCheck` - расширенная проверка вызовов методов и свойств
- `-Extension <extension name>` - проверить расширение с указанным именем
- `-AllExtensions` - проверить все расширения

**Return codes:**
- `0` - успешно
- `1` - ошибка (расширение не найдено или произошла ошибка)

**Примеры:**
```bash
# Проверка модулей для веб-клиента
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckModules -WebClient

# Проверка для нескольких режимов
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckModules -ThinClient -WebClient -Server

# Расширенная проверка модулей
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckModules -ThinClient -ExtendedModulesCheck

# Проверка расширения
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckModules -Extension "MyExtension" -ThinClient -WebClient
```

**Особенности:**
- Без опций проверка не выполняется
- Проверяет синтаксис и семантику кода для указанных режимов
- ExtendedModulesCheck проверяет вызовы методов и использование свойств

---

## Utility Commands

### /CreateDistributive <distribution kit directory> -File <file name> [options]

**Описание:** Создает комплекты поставки и файлы комплектов на основе описания

**Параметры:**
- `<distribution kit directory>` - директория комплекта поставки (или файлов комплекта)
- `-File <file name>` - файл описания комплекта поставки
- `-Option <distribution option>` - тип комплекта поставки:
  - `full` - полный (по умолчанию)
  - `update` - обновление
- `-MakeSetup` - создать комплект поставки (по умолчанию)
- `-MakeFiles` - создать файлы комплекта поставки
- `-digisign <license parameters file name>` - параметры лицензии для рабочего места

**Примеры:**
```bash
# Создать полный комплект поставки
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CreateDistributive "C:\distrib\full" -File "distrib_description.xml"

# Создать комплект обновления
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CreateDistributive "C:\distrib\update" ^
  -File "distrib_description.xml" ^
  -Option update

# Создать файлы комплекта поставки
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CreateDistributive "C:\distrib\files" ^
  -File "distrib_description.xml" ^
  -MakeFiles
```

**Особенности:**
- Если указан полный путь к файлу - убедитесь что все директории существуют
- Нельзя использовать одновременно -MakeSetup и -MakeFiles
- Файл описания определяет структуру и содержимое комплекта

---

### /DumpResult <file name>

**Описание:** Выводит результат выполнения команды в файл

**Параметры:**
- `<file name>` - путь к файлу для сохранения результата

**Примеры:**
```bash
# Сохранить результат проверки в файл
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckConfig -ConfigLogIntegrity ^
  /DumpResult "C:\logs\check_result.txt"

# Сохранить результат обновления конфигурации
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /ConfigurationRepositoryUpdateCfg ^
  /DumpResult "C:\logs\update_result.txt"
```

**Особенности:**
- Может использоваться с любой командой DESIGNER
- Полезно для автоматизированных сценариев и логирования
- Файл перезаписывается без предупреждения

---

### /Visible

**Описание:** Показывает окно конфигуратора во время выполнения команд

**Примеры:**
```bash
# Выполнить обновление с видимым окном
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /UpdateDBCfg /Visible
```

**Особенности:**
- Полезно для отладки и визуального контроля процесса
- По умолчанию DESIGNER работает в невидимом режиме
- Может использоваться с любой командой

---

## Return Codes

Все команды DESIGNER возвращают коды завершения для автоматизации:

| Код | Значение | Описание |
|-----|----------|----------|
| `0` | Успешно | Команда выполнена без ошибок |
| `1` | Ошибка | Произошла ошибка при выполнении команды |

**Примеры использования в скриптах:**

**Batch (Windows):**
```batch
@echo off
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /LoadCfg "extension.cfe" -Extension "MyExt"
if %ERRORLEVEL% equ 0 (
    echo SUCCESS: Extension loaded
    exit /b 0
) else (
    echo ERROR: Failed to load extension
    exit /b 1
)
```

**Bash (Linux/GitBash):**
```bash
#!/bin/bash
1cv8 DESIGNER /F "/opt/1c/bases/my_base" /N admin /P pass /LoadCfg "extension.cfe" -Extension "MyExt"
if [ $? -eq 0 ]; then
    echo "SUCCESS: Extension loaded"
    exit 0
else
    echo "ERROR: Failed to load extension"
    exit 1
fi
```

**PowerShell:**
```powershell
& "C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe" DESIGNER /F "C:\bases\my_base" /N admin /P pass /LoadCfg "extension.cfe" -Extension "MyExt"
if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: Extension loaded"
    exit 0
} else {
    Write-Host "ERROR: Failed to load extension"
    exit 1
}
```

---

## Connection String Formats

### File Mode

```bash
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P password [commands]
```

### Client-Server Mode

```bash
1cv8.exe DESIGNER /S "server\base_name" /N admin /P password [commands]
```

**Параметры:**
- `/F <path>` - файловый режим (путь к информационной базе)
- `/S <server\base>` - клиент-серверный режим
- `/N <username>` - имя пользователя
- `/P <password>` - пароль пользователя

---

## Best Practices

### 1. Используйте полные пути

```bash
# Правильно
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadCfg "C:\extensions\MyExtension.cfe" -Extension "MyExt"

# Неправильно (может не работать)
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadCfg "MyExtension.cfe" -Extension "MyExt"
```

### 2. Проверяйте существование директорий

```bash
# Создайте директории перед использованием
mkdir -p "C:\backup\extensions"
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /DumpCfg "C:\backup\extensions\MyExtension.cfe" -Extension "MyExt"
```

### 3. Обрабатывайте коды возврата

```batch
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass /UpdateDBCfg
if %ERRORLEVEL% neq 0 (
    echo ERROR: Database update failed
    exit /b 1
)
```

### 4. Используйте /DumpResult для логирования

```bash
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /CheckConfig -ConfigLogIntegrity ^
  /DumpResult "C:\logs\check_%date:~-4,4%%date:~-7,2%%date:~-10,2%.txt"
```

### 5. Автоматизируйте последовательности команд

```bash
# Полный цикл обновления расширения
1cv8.exe DESIGNER /F "C:\bases\my_base" /N admin /P pass ^
  /LoadCfg "C:\updates\extension_v2.cfe" -Extension "MyExt" ^
  /UpdateDBCfg -Extension "MyExt" ^
  /DumpResult "C:\logs\update_extension.txt"
```

---

## Summary для batch-service

**Команды критичные для batch-service (Extension Management):**

| Команда | Назначение | Приоритет |
|---------|------------|-----------|
| `/LoadCfg ... -Extension` | Установка расширения | HIGH |
| `/DumpCfg ... -Extension` | Экспорт расширения | MEDIUM |
| `/DeleteCfg -Extension` | Удаление расширения | HIGH |
| `/UpdateDBCfg -Extension` | Обновление БД после изменений | HIGH |
| `/DumpDBCfg ... -Extension` | Экспорт конфигурации БД | MEDIUM |

**Ключевые находки:**

1. **Workflow установки расширения:**
   ```
   LoadCfg -Extension → UpdateDBCfg -Extension → Success
   ```

2. **Return codes:** Все команды возвращают 0 (успех) или 1 (ошибка)

3. **Extension флаг универсален:** Работает с большинством команд конфигурации

4. **Batch операции:** Можно цепочить команды через одну сессию DESIGNER

5. **Файловые пути:** КРИТИЧНО - все директории должны существовать до запуска

**Рекомендации для Варианта 2:**

- Использовать subprocess для запуска 1cv8.exe DESIGNER
- Парсить return codes для определения success/failure
- Реализовать pre-flight checks (проверка существования файлов/директорий)
- Логировать выполнение через /DumpResult
- Поддерживать timeout (300s default, настраиваемый)

---

## Дополнительные ресурсы

- **Официальная документация:** https://yellow-erp.com/help/1cv8/ZIF3/
- **Developer Guide:** https://yellow-erp.com/page/guides/dev/
- **Administrator Guide:** https://yellow-erp.com/page/guides/adm/

---

**Версия документа:** 1.0
**Дата создания:** 2025-11-09
**Автор:** AI Agent (comprehensive parsing from yellow-erp.com)

**Замечания:**
- Документ создан на основе парсинга официальной документации 1С:Предприятие 8.x
- Покрывает ВСЕ основные команды DESIGNER режима
- Включает практические примеры для каждой команды
- Содержит best practices для автоматизации
