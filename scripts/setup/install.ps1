<#
.SYNOPSIS
    CommandCenter1C - Development Environment Setup for Windows

.DESCRIPTION
    Автоматическая установка зависимостей для разработки на Windows.
    Определяет требуемые версии из файлов проекта и устанавливает компоненты.

.PARAMETER DryRun
    Показать что будет установлено без изменений

.PARAMETER OnlyGo
    Установить только Go

.PARAMETER OnlyPython
    Установить только Python

.PARAMETER OnlyNodeJS
    Установить только Node.js

.PARAMETER OnlyDocker
    Установить только Docker Desktop

.PARAMETER OnlyDeps
    Установить только зависимости проекта (pip, npm, go mod)

.PARAMETER SkipDocker
    Пропустить установку Docker

.PARAMETER SkipDeps
    Пропустить установку зависимостей проекта

.PARAMETER Force
    Принудительная переустановка

.EXAMPLE
    .\install.ps1
    Полная установка всех компонентов

.EXAMPLE
    .\install.ps1 -DryRun
    Показать план установки без изменений

.EXAMPLE
    .\install.ps1 -OnlyGo -OnlyPython
    Установить только Go и Python
#>

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$OnlyGo,
    [switch]$OnlyPython,
    [switch]$OnlyNodeJS,
    [switch]$OnlyDocker,
    [switch]$OnlyDeps,
    [switch]$SkipDocker,
    [switch]$SkipDeps,
    [switch]$Force
)

# Strict mode
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Определить директории
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Get-Item "$ScriptDir\..\..").FullName

##############################################################################
# LOGGING FUNCTIONS
##############################################################################

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host ("=" * 70) -ForegroundColor Blue
    Write-Host ""
}

function Write-Section {
    param([string]$Message)
    Write-Host ""
    Write-Host "-- $Message --" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] " -ForegroundColor Blue -NoNewline
    Write-Host $Message
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

##############################################################################
# VERSION PARSING
##############################################################################

function Get-RequiredGoVersion {
    # Приоритет 1: .tool-versions
    $toolVersions = Join-Path $ProjectRoot ".tool-versions"
    if (Test-Path $toolVersions) {
        $line = Get-Content $toolVersions | Where-Object { $_ -match "^go\s+" }
        if ($line) {
            return ($line -split "\s+")[1]
        }
    }

    # Приоритет 2: go.mod файлы
    $goMods = Get-ChildItem -Path "$ProjectRoot\go-services" -Filter "go.mod" -Recurse
    $maxVersion = [version]"0.0.0"

    foreach ($mod in $goMods) {
        $content = Get-Content $mod.FullName
        $goLine = $content | Where-Object { $_ -match "^go\s+\d" }
        if ($goLine) {
            $verStr = ($goLine -split "\s+")[1]
            # Нормализовать версию
            if ($verStr -match "^\d+\.\d+$") {
                $verStr = "$verStr.0"
            }
            try {
                $ver = [version]$verStr
                if ($ver -gt $maxVersion) {
                    $maxVersion = $ver
                }
            } catch {}
        }
    }

    if ($maxVersion -gt [version]"0.0.0") {
        return $maxVersion.ToString()
    }

    return "1.21.0"
}

function Get-RequiredPythonVersion {
    # Приоритет 1: .tool-versions
    $toolVersions = Join-Path $ProjectRoot ".tool-versions"
    if (Test-Path $toolVersions) {
        $line = Get-Content $toolVersions | Where-Object { $_ -match "^python\s+" }
        if ($line) {
            return ($line -split "\s+")[1]
        }
    }

    # Приоритет 2: По версии Django
    $requirements = Join-Path $ProjectRoot "orchestrator\requirements.txt"
    if (Test-Path $requirements) {
        $djangoLine = Get-Content $requirements | Where-Object { $_ -match "^Django==" }
        if ($djangoLine -match "Django==(\d+)\.") {
            $djangoMajor = $Matches[1]
            switch ($djangoMajor) {
                "5" { return "3.12" }
                "4" { return "3.11" }
                default { return "3.11" }
            }
        }
    }

    return "3.11"
}

function Get-RequiredNodeJSVersion {
    # Приоритет 1: .tool-versions
    $toolVersions = Join-Path $ProjectRoot ".tool-versions"
    if (Test-Path $toolVersions) {
        $line = Get-Content $toolVersions | Where-Object { $_ -match "^nodejs\s+" }
        if ($line) {
            return ($line -split "\s+")[1]
        }
    }

    # Приоритет 2: package.json engines
    $packageJson = Join-Path $ProjectRoot "frontend\package.json"
    if (Test-Path $packageJson) {
        $json = Get-Content $packageJson -Raw | ConvertFrom-Json
        if ($json.engines -and $json.engines.node) {
            if ($json.engines.node -match "(\d+)") {
                return $Matches[1]
            }
        }

        # Приоритет 3: По версии Vite
        if ($json.devDependencies -and $json.devDependencies.vite) {
            $viteVer = $json.devDependencies.vite -replace "[^\d.]", ""
            if ($viteVer -match "^(\d+)") {
                switch ($Matches[1]) {
                    "6" { return "22" }
                    "5" { return "20" }
                    "4" { return "18" }
                    default { return "20" }
                }
            }
        }
    }

    return "20"
}

##############################################################################
# VERSION CHECK
##############################################################################

function Get-InstalledVersion {
    param([string]$Command, [string]$Pattern)

    try {
        switch ($Command) {
            "go" {
                $output = & go version 2>$null
                if ($output -match "go(\d+\.\d+(\.\d+)?)") {
                    return $Matches[1]
                }
            }
            "python" {
                $output = & python --version 2>$null
                if ($output -match "(\d+\.\d+\.\d+)") {
                    return $Matches[1]
                }
            }
            "node" {
                $output = & node --version 2>$null
                if ($output -match "v?(\d+\.\d+\.\d+)") {
                    return $Matches[1]
                }
            }
            "docker" {
                $output = & docker --version 2>$null
                if ($output -match "(\d+\.\d+\.\d+)") {
                    return $Matches[1]
                }
            }
        }
    } catch {
        return $null
    }

    return $null
}

function Compare-Versions {
    param([string]$Version1, [string]$Version2)

    try {
        $v1 = [version]($Version1 -replace "[^\d.]", "")
        $v2 = [version]($Version2 -replace "[^\d.]", "")
        return $v1.CompareTo($v2)
    } catch {
        return -1
    }
}

##############################################################################
# PACKAGE MANAGER DETECTION
##############################################################################

function Get-PackageManager {
    # Проверяем winget
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        return "winget"
    }

    # Проверяем chocolatey
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        return "choco"
    }

    return $null
}

function Test-AdminRights {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

##############################################################################
# INSTALLATION FUNCTIONS
##############################################################################

function Install-Go {
    $requiredVersion = Get-RequiredGoVersion
    $currentVersion = Get-InstalledVersion "go"
    $action = "SKIP"

    Write-Section "Go"

    if (-not $currentVersion) {
        $action = "INSTALL"
    } elseif ((Compare-Versions $currentVersion $requiredVersion) -lt 0) {
        $action = "UPGRADE"
    } elseif ($Force) {
        $action = "REINSTALL"
    }

    Write-Info "Требуется: $requiredVersion"
    Write-Info "Текущая:   $($currentVersion ?? 'не установлен')"
    Write-Info "Действие:  $action"

    if ($action -eq "SKIP") {
        Write-Success "Go $currentVersion уже установлен"
        return
    }

    if ($DryRun) {
        Write-Info "[DRY-RUN] Будет установлен Go $requiredVersion"
        return
    }

    $pkgManager = Get-PackageManager

    switch ($pkgManager) {
        "winget" {
            Write-Info "Установка через winget..."
            winget install GoLang.Go --accept-source-agreements --accept-package-agreements
        }
        "choco" {
            Write-Info "Установка через chocolatey..."
            choco install golang -y
        }
        default {
            Write-Warn "Установите Go вручную: https://go.dev/dl/"
            Write-Info "Или установите winget/chocolatey для автоматической установки"
            return
        }
    }

    # Обновить PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    Write-Success "Go установлен"
}

function Install-Python {
    $requiredVersion = Get-RequiredPythonVersion
    $currentVersion = Get-InstalledVersion "python"
    $action = "SKIP"

    Write-Section "Python"

    if (-not $currentVersion) {
        $action = "INSTALL"
    } elseif ((Compare-Versions $currentVersion $requiredVersion) -lt 0) {
        $action = "UPGRADE"
    } elseif ($Force) {
        $action = "REINSTALL"
    }

    Write-Info "Требуется: $requiredVersion+"
    Write-Info "Текущая:   $($currentVersion ?? 'не установлен')"
    Write-Info "Действие:  $action"

    if ($action -eq "SKIP") {
        Write-Success "Python $currentVersion уже установлен"
        return
    }

    if ($DryRun) {
        Write-Info "[DRY-RUN] Будет установлен Python $requiredVersion"
        return
    }

    $pkgManager = Get-PackageManager

    switch ($pkgManager) {
        "winget" {
            Write-Info "Установка через winget..."
            winget install Python.Python.$requiredVersion --accept-source-agreements --accept-package-agreements
        }
        "choco" {
            Write-Info "Установка через chocolatey..."
            choco install python --version=$requiredVersion -y
        }
        default {
            Write-Warn "Установите Python вручную: https://www.python.org/downloads/"
            return
        }
    }

    # Обновить PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    Write-Success "Python установлен"
}

function Install-NodeJS {
    $requiredVersion = Get-RequiredNodeJSVersion
    $currentVersion = Get-InstalledVersion "node"
    $action = "SKIP"

    Write-Section "Node.js"

    if (-not $currentVersion) {
        $action = "INSTALL"
    } else {
        $currentMajor = ($currentVersion -split "\.")[0]
        if ([int]$currentMajor -lt [int]$requiredVersion) {
            $action = "UPGRADE"
        } elseif ($Force) {
            $action = "REINSTALL"
        }
    }

    Write-Info "Требуется: $requiredVersion+"
    Write-Info "Текущая:   $($currentVersion ?? 'не установлен')"
    Write-Info "Действие:  $action"

    if ($action -eq "SKIP") {
        Write-Success "Node.js $currentVersion уже установлен"
        return
    }

    if ($DryRun) {
        Write-Info "[DRY-RUN] Будет установлен Node.js $requiredVersion"
        return
    }

    $pkgManager = Get-PackageManager

    switch ($pkgManager) {
        "winget" {
            Write-Info "Установка через winget..."
            winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
        }
        "choco" {
            Write-Info "Установка через chocolatey..."
            choco install nodejs-lts -y
        }
        default {
            Write-Warn "Установите Node.js вручную: https://nodejs.org/"
            return
        }
    }

    # Обновить PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    Write-Success "Node.js установлен"
}

function Install-Docker {
    Write-Section "Docker Desktop"

    $currentVersion = Get-InstalledVersion "docker"

    Write-Info "Текущая версия: $($currentVersion ?? 'не установлен')"

    if ($currentVersion -and -not $Force) {
        Write-Success "Docker $currentVersion уже установлен"
        return
    }

    if ($DryRun) {
        Write-Info "[DRY-RUN] Будет установлен Docker Desktop"
        return
    }

    $pkgManager = Get-PackageManager

    switch ($pkgManager) {
        "winget" {
            Write-Info "Установка через winget..."
            winget install Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
        }
        "choco" {
            Write-Info "Установка через chocolatey..."
            choco install docker-desktop -y
        }
        default {
            Write-Warn "Установите Docker Desktop вручную:"
            Write-Info "  https://www.docker.com/products/docker-desktop/"
            return
        }
    }

    Write-Success "Docker Desktop установлен"
    Write-Warn "Перезагрузите компьютер и включите WSL 2 в настройках Docker Desktop"
}

##############################################################################
# PROJECT DEPENDENCIES
##############################################################################

function Install-PythonDeps {
    Write-Section "Python зависимости"

    $venvDir = Join-Path $ProjectRoot "orchestrator\venv"
    $requirements = Join-Path $ProjectRoot "orchestrator\requirements.txt"

    if ($DryRun) {
        Write-Info "[DRY-RUN] Будет создан venv и установлены зависимости из requirements.txt"
        return
    }

    # Создать venv
    if (-not (Test-Path $venvDir)) {
        Write-Info "Создание виртуального окружения..."
        Push-Location (Join-Path $ProjectRoot "orchestrator")
        python -m venv venv
        Pop-Location
    }

    # Активировать и установить
    $activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        Write-Info "Установка зависимостей..."
        & $activateScript
        pip install --upgrade pip -q
        pip install -r $requirements -q
        deactivate

        Write-Success "Python зависимости установлены"
    } else {
        Write-Err "Не удалось активировать venv"
    }
}

function Install-NodeJSDeps {
    Write-Section "Node.js зависимости"

    $frontendDir = Join-Path $ProjectRoot "frontend"
    $packageJson = Join-Path $frontendDir "package.json"

    if (-not (Test-Path $packageJson)) {
        Write-Warn "package.json не найден"
        return
    }

    if ($DryRun) {
        Write-Info "[DRY-RUN] Будет выполнен npm ci"
        return
    }

    Push-Location $frontendDir

    $packageLock = Join-Path $frontendDir "package-lock.json"
    if (Test-Path $packageLock) {
        Write-Info "Установка через npm ci..."
        npm ci --silent
    } else {
        Write-Info "Установка через npm install..."
        npm install --silent
    }

    Pop-Location

    Write-Success "Node.js зависимости установлены"
}

function Install-GoDeps {
    Write-Section "Go зависимости"

    $goServicesDir = Join-Path $ProjectRoot "go-services"

    if (-not (Test-Path $goServicesDir)) {
        Write-Warn "Директория go-services не найдена"
        return
    }

    if ($DryRun) {
        Write-Info "[DRY-RUN] Будет выполнен go mod download для всех сервисов"
        return
    }

    $services = Get-ChildItem -Path $goServicesDir -Directory
    foreach ($service in $services) {
        $goMod = Join-Path $service.FullName "go.mod"
        if (Test-Path $goMod) {
            Write-Info "go mod download для $($service.Name)..."
            Push-Location $service.FullName
            go mod download
            Pop-Location
        }
    }

    Write-Success "Go модули загружены"
}

function Install-ProjectDeps {
    Write-Header "Зависимости проекта"

    Install-PythonDeps
    Install-NodeJSDeps
    Install-GoDeps
}

##############################################################################
# VERSION CHECK TABLE
##############################################################################

function Show-VersionTable {
    Write-Header "Проверка версий"

    $reqGo = Get-RequiredGoVersion
    $reqPy = Get-RequiredPythonVersion
    $reqNode = Get-RequiredNodeJSVersion

    $curGo = Get-InstalledVersion "go"
    $curPy = Get-InstalledVersion "python"
    $curNode = Get-InstalledVersion "node"
    $curDocker = Get-InstalledVersion "docker"

    Write-Host "+------------+------------+------------+-------------+"
    Write-Host "| Runtime    | Required   | Current    | Action      |"
    Write-Host "+------------+------------+------------+-------------+"

    # Go
    $actGo = if (-not $curGo) { "INSTALL" } elseif ((Compare-Versions $curGo $reqGo) -lt 0) { "UPGRADE" } else { "OK" }
    $actGoColor = if ($actGo -eq "OK") { "Green" } else { "Yellow" }
    Write-Host ("| {0,-10} | {1,-10} | {2,-10} | " -f "Go", $reqGo, ($curGo ?? "not found")) -NoNewline
    Write-Host ("{0,-11} |" -f $actGo) -ForegroundColor $actGoColor

    # Python
    $actPy = if (-not $curPy) { "INSTALL" } elseif ((Compare-Versions $curPy $reqPy) -lt 0) { "UPGRADE" } else { "OK" }
    $actPyColor = if ($actPy -eq "OK") { "Green" } else { "Yellow" }
    Write-Host ("| {0,-10} | {1,-10} | {2,-10} | " -f "Python", "$reqPy+", ($curPy ?? "not found")) -NoNewline
    Write-Host ("{0,-11} |" -f $actPy) -ForegroundColor $actPyColor

    # Node.js
    $curNodeMajor = if ($curNode) { ($curNode -split "\.")[0] } else { "0" }
    $actNode = if (-not $curNode) { "INSTALL" } elseif ([int]$curNodeMajor -lt [int]$reqNode) { "UPGRADE" } else { "OK" }
    $actNodeColor = if ($actNode -eq "OK") { "Green" } else { "Yellow" }
    Write-Host ("| {0,-10} | {1,-10} | {2,-10} | " -f "Node.js", "$reqNode+", ($curNode ?? "not found")) -NoNewline
    Write-Host ("{0,-11} |" -f $actNode) -ForegroundColor $actNodeColor

    # Docker
    $actDocker = if (-not $curDocker) { "INSTALL" } else { "OK" }
    $actDockerColor = if ($actDocker -eq "OK") { "Green" } else { "Yellow" }
    Write-Host ("| {0,-10} | {1,-10} | {2,-10} | " -f "Docker", "20.10+", ($curDocker ?? "not found")) -NoNewline
    Write-Host ("{0,-11} |" -f $actDocker) -ForegroundColor $actDockerColor

    Write-Host "+------------+------------+------------+-------------+"
    Write-Host ""
}

##############################################################################
# FINAL REPORT
##############################################################################

function Show-FinalReport {
    Write-Header "Установка завершена!"

    Write-Host "Установленные компоненты:"
    Write-Host "  - Go:        $(Get-InstalledVersion 'go')"
    Write-Host "  - Python:    $(Get-InstalledVersion 'python')"
    Write-Host "  - Node.js:   $(Get-InstalledVersion 'node')"
    Write-Host "  - Docker:    $(Get-InstalledVersion 'docker')"
    Write-Host ""

    Write-Info "Следующие шаги:"
    Write-Host ""
    Write-Host "  1. Запустить Docker Desktop"
    Write-Host ""
    Write-Host "  2. Запустить инфраструктуру:"
    Write-Host "     docker compose up -d postgres redis"
    Write-Host ""
    Write-Host "  3. Открыть проект в WSL или Git Bash:"
    Write-Host "     cd /c/path/to/command-center-1c"
    Write-Host "     ./scripts/dev/start-all.sh"
    Write-Host ""
}

##############################################################################
# MAIN
##############################################################################

function Main {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Blue
    Write-Host "  CommandCenter1C - Development Environment Setup (Windows)" -ForegroundColor Blue
    Write-Host ("=" * 70) -ForegroundColor Blue
    Write-Host ""

    # Проверка прав администратора
    if (-not (Test-AdminRights)) {
        Write-Warn "Рекомендуется запуск от имени администратора для установки пакетов"
    }

    # Проверка пакетного менеджера
    $pkgManager = Get-PackageManager
    if (-not $pkgManager) {
        Write-Warn "Не найден winget или chocolatey"
        Write-Info "Установите winget (встроен в Windows 11) или chocolatey:"
        Write-Info "  https://chocolatey.org/install"
    } else {
        Write-Info "Пакетный менеджер: $pkgManager"
    }

    # Показать версии
    Show-VersionTable

    if ($DryRun) {
        Write-Warn "Режим DRY-RUN: изменения НЕ будут применены"
        Write-Host ""
    }

    # Определить что устанавливать
    $hasOnlyFlags = $OnlyGo -or $OnlyPython -or $OnlyNodeJS -or $OnlyDocker -or $OnlyDeps

    # Установка компонентов
    if (-not $hasOnlyFlags -or $OnlyGo) {
        Install-Go
    }

    if (-not $hasOnlyFlags -or $OnlyPython) {
        Install-Python
    }

    if (-not $hasOnlyFlags -or $OnlyNodeJS) {
        Install-NodeJS
    }

    if ((-not $hasOnlyFlags -or $OnlyDocker) -and -not $SkipDocker) {
        Install-Docker
    }

    # Зависимости проекта
    if ((-not $hasOnlyFlags -or $OnlyDeps) -and -not $SkipDeps -and -not $DryRun) {
        Install-ProjectDeps
    }

    # Финальный отчет
    if (-not $DryRun) {
        Show-FinalReport
    }
}

# Запуск
Main
