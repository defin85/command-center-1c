#!/bin/bash

##############################################################################
# CommandCenter1C - Library Initialization
##############################################################################
#
# Единая точка входа для подключения всех библиотек.
# Загружает библиотеки в правильном порядке с учетом зависимостей.
#
# Usage:
#   source scripts/lib/init.sh
#   # или из любого места:
#   source "$(dirname "${BASH_SOURCE[0]}")/../lib/init.sh"
#
# Options (export перед source):
#   CC1C_LIB_SKIP_PROMPTS=1    # Не загружать prompts.sh
#   CC1C_LIB_SKIP_SERVICES=1   # Не загружать services.sh
#   CC1C_LIB_SKIP_BUILD=1      # Не загружать build.sh
#   CC1C_LIB_SKIP_PACKAGES=1   # Не загружать packages.sh
#   CC1C_LIB_SKIP_LIFECYCLE=1  # Не загружать lifecycle.sh
#   CC1C_LIB_MINIMAL=1         # Только core.sh + platform.sh
#
# После загрузки доступны:
#   - core.sh:     Цвета, логирование, guards
#   - platform.sh: Определение ОС, платформы
#   - packages.sh: Кросс-платформенный пакетный менеджер
#   - prompts.sh:  Взаимодействие с пользователем
#   - files.sh:    Работа с файлами
#   - services.sh:  Порты, процессы, health checks
#   - build.sh:     Сборка Go сервисов
#   - lifecycle.sh: Управление жизненным циклом сервисов
#
# Version: 1.1.0
##############################################################################

# Определить директорию библиотеки
CC1C_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

##############################################################################
# MISE ACTIVATION (автоактивация если не активен)
##############################################################################

# Активируем mise если он установлен но не активирован
# Это нужно для non-interactive shells (CI, cron, subshells)
if command -v mise &>/dev/null; then
    # Добавляем shims в PATH (быстрый способ без полной активации)
    MISE_SHIMS="$HOME/.local/share/mise/shims"
    if [[ -d "$MISE_SHIMS" ]] && [[ ":$PATH:" != *":$MISE_SHIMS:"* ]]; then
        export PATH="$MISE_SHIMS:$PATH"
    fi

    # Полная активация если ещё не активирован
    if [[ -z "${MISE_SHELL:-}" ]]; then
        eval "$(mise activate bash 2>/dev/null)" || true
    fi
fi

##############################################################################
# LOAD CORE (обязательно)
##############################################################################

if [[ ! -f "$CC1C_LIB_DIR/core.sh" ]]; then
    echo "FATAL: core.sh not found in $CC1C_LIB_DIR" >&2
    exit 1
fi

# shellcheck source=core.sh
source "$CC1C_LIB_DIR/core.sh"

##############################################################################
# LOAD PLATFORM (обязательно)
##############################################################################

if [[ ! -f "$CC1C_LIB_DIR/platform.sh" ]]; then
    log_error "platform.sh not found in $CC1C_LIB_DIR"
    exit 1
fi

# shellcheck source=platform.sh
source "$CC1C_LIB_DIR/platform.sh"

##############################################################################
# MINIMAL MODE - только core + platform
##############################################################################

if [[ "${CC1C_LIB_MINIMAL:-}" == "1" ]]; then
    log_debug "Minimal mode: only core.sh and platform.sh loaded"
    return 0
fi

##############################################################################
# LOAD PACKAGES (опционально)
##############################################################################

if [[ "${CC1C_LIB_SKIP_PACKAGES:-}" != "1" ]]; then
    if [[ -f "$CC1C_LIB_DIR/packages.sh" ]]; then
        # shellcheck source=packages.sh
        source "$CC1C_LIB_DIR/packages.sh"
    else
        log_debug "packages.sh not found, skipping"
    fi
fi

##############################################################################
# LOAD FILES
##############################################################################

if [[ -f "$CC1C_LIB_DIR/files.sh" ]]; then
    # shellcheck source=files.sh
    source "$CC1C_LIB_DIR/files.sh"
else
    log_warning "files.sh not found, skipping"
fi

##############################################################################
# LOAD PROMPTS (опционально)
##############################################################################

if [[ "${CC1C_LIB_SKIP_PROMPTS:-}" != "1" ]]; then
    if [[ -f "$CC1C_LIB_DIR/prompts.sh" ]]; then
        # shellcheck source=prompts.sh
        source "$CC1C_LIB_DIR/prompts.sh"
    else
        log_warning "prompts.sh not found, skipping"
    fi
fi

##############################################################################
# LOAD SERVICES (опционально)
##############################################################################

if [[ "${CC1C_LIB_SKIP_SERVICES:-}" != "1" ]]; then
    if [[ -f "$CC1C_LIB_DIR/services.sh" ]]; then
        # shellcheck source=services.sh
        source "$CC1C_LIB_DIR/services.sh"
    else
        log_warning "services.sh not found, skipping"
    fi
fi

##############################################################################
# LOAD BUILD (опционально)
##############################################################################

if [[ "${CC1C_LIB_SKIP_BUILD:-}" != "1" ]]; then
    if [[ -f "$CC1C_LIB_DIR/build.sh" ]]; then
        # shellcheck source=build.sh
        source "$CC1C_LIB_DIR/build.sh"
    else
        log_debug "build.sh not found, skipping"
    fi
fi

##############################################################################
# LOAD LIFECYCLE (опционально)
##############################################################################

if [[ "${CC1C_LIB_SKIP_LIFECYCLE:-}" != "1" ]]; then
    if [[ -f "$CC1C_LIB_DIR/lifecycle.sh" ]]; then
        # shellcheck source=lifecycle.sh
        source "$CC1C_LIB_DIR/lifecycle.sh"
    else
        log_debug "lifecycle.sh not found, skipping"
    fi
fi

##############################################################################
# EXPORT LIB_DIR for scripts that need it
##############################################################################

export CC1C_LIB_DIR

log_debug "CC1C libraries loaded from $CC1C_LIB_DIR"

##############################################################################
# End of init.sh
##############################################################################
