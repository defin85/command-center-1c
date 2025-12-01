#!/bin/bash

##############################################################################
# CommandCenter1C - User Prompts Library
##############################################################################
#
# Функции для взаимодействия с пользователем: подтверждения, выбор опций.
#
# Usage:
#   source scripts/lib/prompts.sh
#
# Dependencies:
#   - scripts/lib/core.sh
#
# Exports:
#   Prompts: confirm_action, select_option, prompt_input
#   Progress: show_spinner, hide_spinner, show_progress
#
# Version: 1.0.0
##############################################################################

# Проверка зависимостей
if [[ -z "${CC1C_LIB_CORE_LOADED:-}" ]]; then
    echo "ERROR: prompts.sh requires core.sh to be loaded first" >&2
    return 1
fi

# Предотвращение повторного sourcing
if [[ -n "${CC1C_LIB_PROMPTS_LOADED:-}" ]]; then
    return 0
fi
CC1C_LIB_PROMPTS_LOADED=true

##############################################################################
# CONFIRMATION PROMPTS
##############################################################################

# confirm_action - запрос подтверждения действия
# Usage:
#   confirm_action "Удалить все файлы?" "n"  # default: no
#   confirm_action "Продолжить?" "y"         # default: yes
# Returns: 0 if confirmed, 1 otherwise
confirm_action() {
    local message=$1
    local default=${2:-n}  # default: no

    # Пропуск в режиме --force
    if [[ "${FORCE:-false}" == "true" ]]; then
        return 0
    fi

    # Пропуск в non-interactive mode
    if [[ ! -t 0 ]]; then
        log_warning "Non-interactive mode: using default ($default)"
        [[ "$default" == "y" ]]
        return $?
    fi

    local prompt
    if [[ "$default" == "y" ]]; then
        prompt="[Y/n]"
    else
        prompt="[y/N]"
    fi

    echo ""
    local response
    read -p "$(echo -e "${YELLOW}$message${NC} $prompt: ")" response
    response=${response:-$default}
    [[ "$response" =~ ^[Yy]$ ]]
}

# confirm_destructive - подтверждение опасного действия (требует ввод YES)
# Usage: confirm_destructive "Это удалит ВСЕ данные. Вы уверены?"
# Returns: 0 if confirmed, 1 otherwise
confirm_destructive() {
    local message=$1

    # В --force режиме требуем явного подтверждения
    if [[ "${FORCE:-false}" == "true" ]]; then
        log_warning "Опасная операция пропущена в --force режиме"
        log_info "Используйте интерактивный режим для подтверждения"
        return 1
    fi

    # Пропуск в non-interactive mode
    if [[ ! -t 0 ]]; then
        log_error "Опасная операция требует интерактивного режима"
        return 1
    fi

    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  ПРЕДУПРЕЖДЕНИЕ: ОПАСНАЯ ОПЕРАЦИЯ${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "$message"
    echo ""
    echo -e "Для подтверждения введите ${BOLD}YES${NC}:"

    local response
    read -p "> " response
    [[ "$response" == "YES" ]]
}

##############################################################################
# SELECTION PROMPTS
##############################################################################

# select_option - выбор одного варианта из списка
# Usage:
#   choice=$(select_option "Выберите действие:" "Удалить" "Сохранить" "Отмена")
#   echo "Выбрано: $choice"
# Returns: выбранный вариант (строка)
select_option() {
    local prompt=$1
    shift
    local options=("$@")

    # Пропуск в non-interactive mode
    if [[ ! -t 0 ]]; then
        log_warning "Non-interactive mode: using first option"
        echo "${options[0]}"
        return 0
    fi

    echo ""
    echo -e "${YELLOW}$prompt${NC}"
    local i=1
    for opt in "${options[@]}"; do
        echo "  $i) $opt"
        ((i++))
    done

    while true; do
        local choice
        read -p "Выбор [1-${#options[@]}]: " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#options[@]} )); then
            echo "${options[$((choice-1))]}"
            return 0
        fi
        echo "Неверный выбор. Попробуйте снова."
    done
}

# select_multiple - выбор нескольких вариантов из списка
# Usage:
#   choices=$(select_multiple "Выберите сервисы:" "api-gateway" "worker" "orchestrator")
#   echo "Выбрано: $choices"
# Returns: выбранные варианты через пробел
select_multiple() {
    local prompt=$1
    shift
    local options=("$@")
    local selected=()

    # Пропуск в non-interactive mode
    if [[ ! -t 0 ]]; then
        log_warning "Non-interactive mode: using all options"
        echo "${options[*]}"
        return 0
    fi

    echo ""
    echo -e "${YELLOW}$prompt${NC}"
    echo "  (введите номера через пробел, или 'all' для всех, 'done' для завершения)"
    echo ""

    local i=1
    for opt in "${options[@]}"; do
        echo "  $i) $opt"
        ((i++))
    done

    while true; do
        echo ""
        echo "Выбрано: ${selected[*]:-ничего}"
        local input
        read -p "Добавить [1-${#options[@]}/all/done]: " input

        if [[ "$input" == "done" ]]; then
            break
        elif [[ "$input" == "all" ]]; then
            selected=("${options[@]}")
            break
        else
            for num in $input; do
                if [[ "$num" =~ ^[0-9]+$ ]] && (( num >= 1 && num <= ${#options[@]} )); then
                    local opt="${options[$((num-1))]}"
                    # Добавить если еще нет в списке
                    if [[ ! " ${selected[*]} " =~ " ${opt} " ]]; then
                        selected+=("$opt")
                    fi
                fi
            done
        fi
    done

    echo "${selected[*]}"
}

##############################################################################
# INPUT PROMPTS
##############################################################################

# prompt_input - запрос текстового ввода с default значением
# Usage:
#   name=$(prompt_input "Введите имя" "default_name")
# Returns: введенное значение или default
prompt_input() {
    local prompt=$1
    local default=${2:-}

    # Пропуск в non-interactive mode
    if [[ ! -t 0 ]]; then
        if [[ -n "$default" ]]; then
            echo "$default"
            return 0
        else
            log_error "Ввод требуется в non-interactive mode без default значения"
            return 1
        fi
    fi

    local display_default=""
    if [[ -n "$default" ]]; then
        display_default=" [${default}]"
    fi

    local value
    read -p "$(echo -e "${BLUE}$prompt${NC}${display_default}: ")" value
    echo "${value:-$default}"
}

# prompt_password - запрос пароля (без эха)
# Usage:
#   password=$(prompt_password "Введите пароль")
# Returns: введенный пароль
prompt_password() {
    local prompt=$1

    # Пропуск в non-interactive mode
    if [[ ! -t 0 ]]; then
        log_error "Ввод пароля требует интерактивного режима"
        return 1
    fi

    local password
    read -s -p "$(echo -e "${BLUE}$prompt${NC}: ")" password
    echo ""  # Новая строка после ввода
    echo "$password"
}

##############################################################################
# PROGRESS INDICATORS
##############################################################################

# Глобальная переменная для PID спиннера
_SPINNER_PID=""

# show_spinner - показать спиннер во время выполнения команды
# Usage:
#   show_spinner "Загрузка..."
#   long_command
#   hide_spinner
show_spinner() {
    local message=${1:-"Загрузка..."}
    local delay=0.1
    local spinchars='|/-\'

    # Не показывать в non-interactive mode
    if [[ ! -t 1 ]]; then
        echo "$message"
        return 0
    fi

    # Запуск спиннера в фоне
    (
        while true; do
            for (( i=0; i<${#spinchars}; i++ )); do
                printf "\r${BLUE}[%c]${NC} %s" "${spinchars:$i:1}" "$message"
                sleep "$delay"
            done
        done
    ) &
    _SPINNER_PID=$!
    disown "$_SPINNER_PID" 2>/dev/null
}

# hide_spinner - скрыть спиннер
# Usage: hide_spinner [success|error]
hide_spinner() {
    local status=${1:-success}

    if [[ -n "$_SPINNER_PID" ]]; then
        kill "$_SPINNER_PID" 2>/dev/null || true
        wait "$_SPINNER_PID" 2>/dev/null || true
        _SPINNER_PID=""
    fi

    # Очистить строку
    printf "\r%*s\r" 80 ""

    # Показать финальный статус
    case "$status" in
        success)
            printf "${GREEN}[✓]${NC} Готово\n"
            ;;
        error)
            printf "${RED}[✗]${NC} Ошибка\n"
            ;;
    esac
}

# show_progress - показать прогресс-бар
# Usage: show_progress 50 100 "Обработка файлов"
show_progress() {
    local current=$1
    local total=$2
    local message=${3:-"Progress"}
    local width=40

    # Пропуск в non-interactive mode
    if [[ ! -t 1 ]]; then
        echo "$message: $current/$total"
        return 0
    fi

    local percent=$((current * 100 / total))
    local filled=$((width * current / total))
    local empty=$((width - filled))

    printf "\r${BLUE}[${NC}"
    printf "%${filled}s" '' | tr ' ' '='
    printf "%${empty}s" '' | tr ' ' ' '
    printf "${BLUE}]${NC} %3d%% %s" "$percent" "$message"

    # Новая строка когда завершено
    if [[ $current -eq $total ]]; then
        echo ""
    fi
}

##############################################################################
# WAIT UTILITIES
##############################################################################

# wait_for_keypress - ожидание нажатия клавиши
# Usage: wait_for_keypress "Нажмите любую клавишу для продолжения..."
wait_for_keypress() {
    local message=${1:-"Нажмите любую клавишу для продолжения..."}

    # Пропуск в non-interactive mode
    if [[ ! -t 0 ]]; then
        return 0
    fi

    echo ""
    read -n 1 -s -r -p "$(echo -e "${DIM}$message${NC}")"
    echo ""
}

# countdown - обратный отсчет перед действием
# Usage: countdown 5 "Запуск через"
countdown() {
    local seconds=${1:-5}
    local message=${2:-"Продолжение через"}

    # Пропуск в non-interactive mode
    if [[ ! -t 1 ]]; then
        return 0
    fi

    for ((i=seconds; i>0; i--)); do
        printf "\r${YELLOW}%s %d секунд...${NC}  " "$message" "$i"
        sleep 1
    done
    printf "\r%*s\r" 60 ""
}

##############################################################################
# End of prompts.sh
##############################################################################
