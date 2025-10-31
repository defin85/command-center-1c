# Получение списка информационных баз через RAC

## Обзор

**RAC** (Remote Administration Client) - утилита командной строки для администрирования кластера серверов 1С:Предприятие 8.3.

**Расположение:** `C:\Program Files\1cv8\8.3.27.1786\bin\rac.exe`

## Базовый синтаксис

```bash
rac <host>:<port> <command> [options] [arguments]
```

По умолчанию: `host:port = localhost:1545` (порт сервера агента кластера)

---

## Последовательность команд для получения списка баз

### Шаг 1: Получить список кластеров

```bash
rac.exe <server>:1545 cluster list
```

**Пример вывода:**
```
cluster                : 635eff68-bf69-4e12-a7c9-2967527fc237
host                   : 1cserver
port                   : 1541
name                   : Кластер 1С
...
```

**Важно:** Сохраните `cluster` UUID для следующих команд.

---

### Шаг 2: Получить краткий список баз

```bash
rac.exe <server>:1545 infobase summary list --cluster=<cluster-uuid>
```

**С аутентификацией кластера:**
```bash
rac.exe <server>:1545 infobase summary list ^
  --cluster=635eff68-bf69-4e12-a7c9-2967527fc237 ^
  --cluster-user=admin ^
  --cluster-pwd=password
```

**Пример вывода:**
```
infobase               : e1092854-3660-11e7-6b9e-d017c292ea7a
name                   : BUH
descr                  : Бухгалтерия предприятия

infobase               : f2193965-4771-11e7-7c0f-e128d383fb8b
name                   : TRADE
descr                  : Торговля и склад
...
```

---

### Шаг 3: Получить полную информацию о конкретной базе

```bash
rac.exe <server>:1545 infobase info ^
  --cluster=<cluster-uuid> ^
  --infobase=<infobase-uuid> ^
  --cluster-user=admin ^
  --cluster-pwd=password
```

**Пример вывода:**
```
infobase               : e1092854-3660-11e7-6b9e-d017c292ea7a
name                   : BUH
descr                  : Бухгалтерия предприятия
dbms                   : MSSQLServer
db-server              : sql-server\instance
db-name                : BUH_DB
db-user                : sa
security-level         : 0
locale                 : ru
date-offset            : 2000
permission-code        :
scheduled-jobs-deny    : off
license-distribution   : allow
...
```

**Ключевые поля:**
- `infobase` - UUID базы
- `name` - имя базы
- `dbms` - тип СУБД (MSSQLServer, PostgreSQL, IBMDb2)
- `db-server` - адрес SQL сервера
- `db-name` - имя базы данных в SQL
- `security-level` - уровень безопасности

---

## Полный пример скрипта PowerShell

```powershell
# Путь к rac.exe
$racPath = "C:\Program Files\1cv8\8.3.27.1786\bin\rac.exe"
$server = "1cserver:1545"

# Учётные данные администратора кластера
$clusterUser = "admin"
$clusterPwd = "password"

# Шаг 1: Получить ID кластера
Write-Host "Getting cluster list..."
$clusterOutput = & $racPath $server cluster list

# Парсинг UUID кластера (первый кластер)
$clusterUuid = ($clusterOutput | Select-String -Pattern "cluster\s+:\s+(.+)").Matches[0].Groups[1].Value
Write-Host "Cluster UUID: $clusterUuid"

# Шаг 2: Получить список баз
Write-Host "`nGetting infobase list..."
$infobaseList = & $racPath $server infobase summary list `
    --cluster=$clusterUuid `
    --cluster-user=$clusterUser `
    --cluster-pwd=$clusterPwd

# Парсинг списка баз
$infobases = @()
$currentInfobase = @{}

foreach ($line in $infobaseList) {
    if ($line -match "^infobase\s+:\s+(.+)$") {
        if ($currentInfobase.Count -gt 0) {
            $infobases += [PSCustomObject]$currentInfobase
        }
        $currentInfobase = @{
            uuid = $matches[1].Trim()
        }
    }
    elseif ($line -match "^name\s+:\s+(.+)$") {
        $currentInfobase.name = $matches[1].Trim()
    }
    elseif ($line -match "^descr\s+:\s+(.*)$") {
        $currentInfobase.description = $matches[1].Trim()
    }
}

# Добавить последнюю базу
if ($currentInfobase.Count -gt 0) {
    $infobases += [PSCustomObject]$currentInfobase
}

# Вывести результат
Write-Host "`nFound $($infobases.Count) infobases:"
$infobases | Format-Table -AutoSize

# Шаг 3: Получить детальную информацию для первой базы (пример)
if ($infobases.Count -gt 0) {
    $firstInfobase = $infobases[0]
    Write-Host "`nGetting detailed info for: $($firstInfobase.name)"

    & $racPath $server infobase info `
        --cluster=$clusterUuid `
        --infobase=$firstInfobase.uuid `
        --cluster-user=$clusterUser `
        --cluster-pwd=$clusterPwd
}
```

---

## Интеграция с Go (для Installation Service)

### Структура для хранения информации о базе

```go
package onec

import (
    "bufio"
    "bytes"
    "fmt"
    "os/exec"
    "regexp"
    "strings"
)

type InfobaseInfo struct {
    UUID             string
    Name             string
    Description      string
    DBMS             string
    DBServer         string
    DBName           string
    DBUser           string
    SecurityLevel    int
    ConnectionString string // для 1cv8.exe
}

type ClusterManager struct {
    racPath      string
    serverAddr   string
    clusterUser  string
    clusterPwd   string
}

func NewClusterManager(racPath, serverAddr, clusterUser, clusterPwd string) *ClusterManager {
    return &ClusterManager{
        racPath:     racPath,
        serverAddr:  serverAddr,
        clusterUser: clusterUser,
        clusterPwd:  clusterPwd,
    }
}

// GetClusterUUID получает UUID первого доступного кластера
func (cm *ClusterManager) GetClusterUUID() (string, error) {
    cmd := exec.Command(cm.racPath, cm.serverAddr, "cluster", "list")

    output, err := cmd.CombinedOutput()
    if err != nil {
        return "", fmt.Errorf("failed to get cluster list: %w", err)
    }

    // Парсинг UUID кластера
    re := regexp.MustCompile(`cluster\s+:\s+([a-f0-9-]+)`)
    matches := re.FindSubmatch(output)
    if len(matches) < 2 {
        return "", fmt.Errorf("cluster UUID not found in output")
    }

    return string(matches[1]), nil
}

// GetInfobaseList получает список всех информационных баз кластера
func (cm *ClusterManager) GetInfobaseList() ([]InfobaseInfo, error) {
    // Шаг 1: Получить UUID кластера
    clusterUUID, err := cm.GetClusterUUID()
    if err != nil {
        return nil, err
    }

    // Шаг 2: Получить краткий список баз
    args := []string{
        cm.serverAddr,
        "infobase",
        "summary",
        "list",
        fmt.Sprintf("--cluster=%s", clusterUUID),
    }

    if cm.clusterUser != "" {
        args = append(args, fmt.Sprintf("--cluster-user=%s", cm.clusterUser))
        args = append(args, fmt.Sprintf("--cluster-pwd=%s", cm.clusterPwd))
    }

    cmd := exec.Command(cm.racPath, args...)
    output, err := cmd.CombinedOutput()
    if err != nil {
        return nil, fmt.Errorf("failed to get infobase list: %w", err)
    }

    // Парсинг списка баз
    infobases := cm.parseInfobaseList(output)

    // Шаг 3: Получить детальную информацию для каждой базы
    for i := range infobases {
        detailedInfo, err := cm.GetInfobaseDetails(clusterUUID, infobases[i].UUID)
        if err != nil {
            // Логируем ошибку, но продолжаем
            fmt.Printf("Warning: failed to get details for %s: %v\n", infobases[i].Name, err)
            continue
        }

        // Обновляем информацию
        infobases[i] = detailedInfo
    }

    return infobases, nil
}

// parseInfobaseList парсит вывод команды "infobase summary list"
func (cm *ClusterManager) parseInfobaseList(output []byte) []InfobaseInfo {
    var infobases []InfobaseInfo
    var current InfobaseInfo

    scanner := bufio.NewScanner(bytes.NewReader(output))

    for scanner.Scan() {
        line := strings.TrimSpace(scanner.Text())

        if strings.HasPrefix(line, "infobase") {
            // Сохранить предыдущую базу
            if current.UUID != "" {
                infobases = append(infobases, current)
            }

            // Начать новую базу
            parts := strings.SplitN(line, ":", 2)
            if len(parts) == 2 {
                current = InfobaseInfo{
                    UUID: strings.TrimSpace(parts[1]),
                }
            }
        } else if strings.HasPrefix(line, "name") {
            parts := strings.SplitN(line, ":", 2)
            if len(parts) == 2 {
                current.Name = strings.TrimSpace(parts[1])
            }
        } else if strings.HasPrefix(line, "descr") {
            parts := strings.SplitN(line, ":", 2)
            if len(parts) == 2 {
                current.Description = strings.TrimSpace(parts[1])
            }
        }
    }

    // Добавить последнюю базу
    if current.UUID != "" {
        infobases = append(infobases, current)
    }

    return infobases
}

// GetInfobaseDetails получает детальную информацию о базе
func (cm *ClusterManager) GetInfobaseDetails(clusterUUID, infobaseUUID string) (InfobaseInfo, error) {
    args := []string{
        cm.serverAddr,
        "infobase",
        "info",
        fmt.Sprintf("--cluster=%s", clusterUUID),
        fmt.Sprintf("--infobase=%s", infobaseUUID),
    }

    if cm.clusterUser != "" {
        args = append(args, fmt.Sprintf("--cluster-user=%s", cm.clusterUser))
        args = append(args, fmt.Sprintf("--cluster-pwd=%s", cm.clusterPwd))
    }

    cmd := exec.Command(cm.racPath, args...)
    output, err := cmd.CombinedOutput()
    if err != nil {
        return InfobaseInfo{}, fmt.Errorf("failed to get infobase details: %w", err)
    }

    return cm.parseInfobaseDetails(output), nil
}

// parseInfobaseDetails парсит вывод команды "infobase info"
func (cm *ClusterManager) parseInfobaseDetails(output []byte) InfobaseInfo {
    info := InfobaseInfo{}

    scanner := bufio.NewScanner(bytes.NewReader(output))

    for scanner.Scan() {
        line := strings.TrimSpace(scanner.Text())
        parts := strings.SplitN(line, ":", 2)

        if len(parts) != 2 {
            continue
        }

        key := strings.TrimSpace(parts[0])
        value := strings.TrimSpace(parts[1])

        switch key {
        case "infobase":
            info.UUID = value
        case "name":
            info.Name = value
        case "descr":
            info.Description = value
        case "dbms":
            info.DBMS = value
        case "db-server":
            info.DBServer = value
        case "db-name":
            info.DBName = value
        case "db-user":
            info.DBUser = value
        }
    }

    // Генерируем connection string для 1cv8.exe
    if info.DBServer != "" && info.DBName != "" {
        info.ConnectionString = fmt.Sprintf("/S\"%s\\%s\"", info.DBServer, info.DBName)
    }

    return info
}
```

### Использование в коде

```go
func main() {
    // Инициализация менеджера кластера
    cm := onec.NewClusterManager(
        "C:\\Program Files\\1cv8\\8.3.27.1786\\bin\\rac.exe",
        "1cserver:1545",
        "admin",
        "password",
    )

    // Получить список всех баз
    infobases, err := cm.GetInfobaseList()
    if err != nil {
        log.Fatalf("Failed to get infobase list: %v", err)
    }

    fmt.Printf("Found %d infobases:\n", len(infobases))
    for _, ib := range infobases {
        fmt.Printf("- %s (%s) - %s\n", ib.Name, ib.UUID, ib.ConnectionString)
    }
}
```

---

## Интеграция с Django (синхронизация баз)

### Management Command для синхронизации

```python
# orchestrator/apps/databases/management/commands/sync_infobases.py

from django.core.management.base import BaseCommand
from apps.databases.services import ClusterService

class Command(BaseCommand):
    help = 'Синхронизирует список баз из кластера 1С в базу данных Django'

    def add_arguments(self, parser):
        parser.add_argument(
            '--server',
            default='1cserver:1545',
            help='Адрес сервера агента кластера (default: 1cserver:1545)'
        )
        parser.add_argument(
            '--cluster-user',
            default='admin',
            help='Имя пользователя кластера'
        )
        parser.add_argument(
            '--cluster-pwd',
            required=True,
            help='Пароль администратора кластера'
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting infobase synchronization...')

        service = ClusterService(
            server=options['server'],
            cluster_user=options['cluster_user'],
            cluster_pwd=options['cluster_pwd']
        )

        # Получить список баз из кластера
        infobases = service.get_infobase_list()

        self.stdout.write(f'Found {len(infobases)} infobases in cluster')

        # Синхронизировать с Django БД
        created, updated, errors = service.sync_to_database(infobases)

        self.stdout.write(self.style.SUCCESS(
            f'Sync completed: {created} created, {updated} updated, {errors} errors'
        ))
```

---

## Важные замечания

### 1. Требования к доступу

- Утилита `rac.exe` должна быть доступна на сервере, где запускается команда
- Требуется сетевой доступ к серверу агента кластера (порт 1545)
- Для команд `infobase info` может требоваться аутентификация администратора кластера

### 2. Безопасность

- **НЕ храните пароли в открытом виде** в скриптах
- Используйте переменные окружения или secure vault
- Логируйте команды БЕЗ паролей

### 3. Производительность

- Команда `infobase summary list` быстрая (получает только UUID и имена)
- Команда `infobase info` медленная для каждой базы (детальная информация)
- Для 700 баз: рекомендуется кэшировать результаты и обновлять периодически

### 4. Кодировка вывода

- Вывод `rac.exe` в кодировке Windows-1251
- В Go используйте `golang.org/x/text/encoding/charmap` для декодирования
- В PowerShell обычно работает корректно

---

## Следующие шаги

1. **Тестирование на реальном кластере**: Запустить команды на Windows Server с доступом к кластеру
2. **Реализация Go-модуля**: Создать `cluster_manager.go` с парсингом вывода rac.exe
3. **Интеграция с Django**: Создать Celery задачу для периодической синхронизации списка баз
4. **Автообнаружение**: Настроить автоматическое обнаружение новых баз (например, каждые 24 часа)

---

## Полезные ссылки

- [Официальная документация 1С по администрированию кластера](https://its.1c.ru/db/v8310doc#bookmark:adm:TI000000455)
- [GitHub: irac - OSCript обёртка для rac](https://github.com/arkuznetsov/irac)
- [Habr: Библиотека для администрирования 1С через RAS/RAC на PHP](https://habr.com/ru/articles/932918/)
