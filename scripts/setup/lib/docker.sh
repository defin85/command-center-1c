#!/bin/bash

##############################################################################
# CommandCenter1C - Docker Installation Module
##############################################################################
#
# Платформо-зависимая установка Docker и Docker Compose.
# Используется из install.sh через source.
#
# Поддерживаемые платформы:
#   - WSL (любой дистрибутив) - проверка Docker Desktop
#   - Ubuntu/Debian (apt)
#   - Arch Linux (pacman)
#   - Fedora (dnf)
#   - macOS (Docker Desktop)
#
##############################################################################

# Предотвращение повторного sourcing
if [[ -n "$DOCKER_MODULE_LOADED" ]]; then
    return 0
fi
DOCKER_MODULE_LOADED=true

##############################################################################
# MAIN ENTRY POINT
##############################################################################

_install_docker_for_platform() {
    local platform=$(detect_platform)

    # Проверка: уже установлен и работает?
    if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
        log_success "Docker уже установлен: $(docker --version)"
        log_info "Docker Compose: $(docker compose version 2>/dev/null | head -1)"

        # Проверка daemon (не для WSL)
        if ! is_wsl && ! docker info &>/dev/null 2>&1; then
            log_warning "Docker daemon не запущен"
            _start_docker_daemon
        fi
        return 0
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет установлен Docker для платформы: $platform"
        return 0
    fi

    case "$platform" in
        wsl|wsl-pacman|wsl-apt)
            _install_docker_wsl
            ;;
        linux-apt)
            _install_docker_apt
            ;;
        linux-pacman)
            _install_docker_pacman
            ;;
        linux-dnf)
            _install_docker_dnf
            ;;
        macos)
            _install_docker_macos
            ;;
        *)
            log_error "Неподдерживаемая платформа: $platform"
            log_info "Установите Docker вручную: https://docs.docker.com/engine/install/"
            return 1
            ;;
    esac

    # Post-install конфигурация (не для WSL и macOS)
    if [[ "$platform" != wsl* && "$platform" != "macos" ]]; then
        _configure_docker_group
        _start_docker_daemon
    fi

    # Финальная проверка
    if command -v docker &>/dev/null; then
        log_success "Docker установлен: $(docker --version)"
    else
        log_error "Docker не найден после установки"
        return 1
    fi
}

##############################################################################
# WSL - Docker Desktop Integration
##############################################################################

_install_docker_wsl() {
    log_info "Обнаружен WSL"

    if command -v docker &>/dev/null; then
        log_success "Docker Desktop уже интегрирован с WSL"
        return 0
    fi

    echo ""
    log_warning "В WSL используйте Docker Desktop для Windows"
    echo ""
    echo "Инструкция по установке:"
    echo ""
    echo "  1. Скачайте Docker Desktop:"
    echo "     https://docs.docker.com/desktop/install/windows-install/"
    echo ""
    echo "  2. Установите и запустите Docker Desktop"
    echo ""
    echo "  3. Включите WSL integration:"
    echo "     Settings → Resources → WSL Integration → Enable для вашего дистрибутива"
    echo ""
    echo "  4. Перезапустите WSL:"
    echo "     wsl --shutdown (в PowerShell)"
    echo ""

    return 1
}

##############################################################################
# Ubuntu/Debian (apt)
##############################################################################

_install_docker_apt() {
    log_info "Установка Docker через apt (официальный репозиторий)..."

    # Удаление старых версий
    sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

    # Установка зависимостей
    sudo apt-get update
    sudo apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # Добавление GPG ключа Docker
    sudo install -m 0755 -d /etc/apt/keyrings

    # Определение дистрибутива (ubuntu или debian) - безопасный парсинг
    local distro="ubuntu"
    local codename=""
    if [[ -f /etc/os-release ]]; then
        # Безопасный парсинг без source
        local os_id
        os_id=$(grep -E "^ID=" /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1)
        [[ "$os_id" == "debian" ]] && distro="debian"
        codename=$(grep -E "^VERSION_CODENAME=" /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1)
    fi

    curl -fsSL "https://download.docker.com/linux/${distro}/gpg" | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    # Добавление репозитория
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/${distro} \
        ${codename} stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Установка Docker
    sudo apt-get update
    sudo apt-get install -y \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

    log_success "Docker установлен через apt"
}

##############################################################################
# Arch Linux (pacman)
##############################################################################

_install_docker_pacman() {
    log_info "Установка Docker через pacman..."

    # Установка Docker и docker-compose
    sudo pacman -Syu --noconfirm --needed docker docker-compose

    log_success "Docker установлен через pacman"
}

##############################################################################
# Fedora (dnf)
##############################################################################

_install_docker_dnf() {
    log_info "Установка Docker через dnf (официальный репозиторий)..."

    # Удаление старых версий
    sudo dnf remove -y docker \
        docker-client \
        docker-client-latest \
        docker-common \
        docker-latest \
        docker-latest-logrotate \
        docker-logrotate \
        docker-selinux \
        docker-engine-selinux \
        docker-engine 2>/dev/null || true

    # Добавление репозитория
    sudo dnf config-manager --add-repo \
        https://download.docker.com/linux/fedora/docker-ce.repo

    # Установка Docker
    sudo dnf install -y \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

    log_success "Docker установлен через dnf"
}

##############################################################################
# macOS (Docker Desktop)
##############################################################################

_install_docker_macos() {
    log_info "macOS: установка Docker Desktop..."

    if command -v brew &>/dev/null; then
        log_info "Установка через Homebrew Cask..."
        brew install --cask docker

        echo ""
        log_warning "Docker Desktop установлен"
        log_info "Запустите Docker Desktop из Applications для завершения установки"
        echo ""
    else
        echo ""
        log_warning "Homebrew не установлен"
        echo ""
        echo "Варианты установки Docker Desktop на macOS:"
        echo ""
        echo "  1. Установите Homebrew и повторите:"
        echo "     /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo "     brew install --cask docker"
        echo ""
        echo "  2. Скачайте напрямую:"
        echo "     https://docs.docker.com/desktop/install/mac-install/"
        echo ""
        return 1
    fi
}

##############################################################################
# POST-INSTALL CONFIGURATION
##############################################################################

_configure_docker_group() {
    # Проверка: пользователь уже в группе docker?
    if groups | grep -q '\bdocker\b'; then
        log_info "Пользователь уже в группе docker"
        return 0
    fi

    log_info "Добавление пользователя в группу docker..."

    # Создать группу docker если не существует
    if ! getent group docker &>/dev/null; then
        sudo groupadd docker
    fi

    # Добавить текущего пользователя
    sudo usermod -aG docker "$USER"

    log_success "Пользователь $USER добавлен в группу docker"
    echo ""
    log_warning "ВАЖНО: Для применения изменений необходимо:"
    echo "  1. Выйти из системы и войти снова, ИЛИ"
    echo "  2. Выполнить: newgrp docker"
    echo ""
}

_start_docker_daemon() {
    log_info "Запуск Docker daemon..."

    if command -v systemctl &>/dev/null; then
        # systemd (большинство современных дистрибутивов)
        sudo systemctl start docker
        sudo systemctl enable docker
        log_success "Docker daemon запущен и добавлен в автозагрузку"
    elif command -v service &>/dev/null; then
        # SysV init
        sudo service docker start
        log_success "Docker daemon запущен"
        log_warning "Добавьте Docker в автозагрузку вручную"
    else
        log_warning "Не удалось запустить Docker daemon автоматически"
        log_info "Запустите Docker daemon вручную"
    fi
}

##############################################################################
# UTILITY FUNCTIONS
##############################################################################

# Проверка работоспособности Docker
_check_docker_working() {
    if ! command -v docker &>/dev/null; then
        return 1
    fi

    if ! docker info &>/dev/null 2>&1; then
        return 1
    fi

    if ! docker compose version &>/dev/null 2>&1; then
        return 1
    fi

    return 0
}

# Вывод информации о Docker
_print_docker_info() {
    echo ""
    echo "Docker информация:"
    echo "  Version: $(docker --version 2>/dev/null || echo 'N/A')"
    echo "  Compose: $(docker compose version 2>/dev/null || echo 'N/A')"

    if docker info &>/dev/null 2>&1; then
        echo "  Daemon:  запущен"
    else
        echo "  Daemon:  не запущен"
    fi
    echo ""
}
