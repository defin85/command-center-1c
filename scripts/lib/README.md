# CommandCenter1C - Unified Shell Library

Единая библиотека bash-функций для всех скриптов проекта.

## Быстрый старт

```bash
# Подключить все библиотеки
source scripts/lib/init.sh

# Использовать функции
log_info "Привет!"
platform=$(detect_platform)
```

## Структура

```
scripts/lib/
├── init.sh       # Entry point - загружает все библиотеки
├── core.sh       # Цвета, логирование, guards
├── platform.sh   # Определение ОС и платформы
├── prompts.sh    # Взаимодействие с пользователем
├── files.sh      # Работа с файлами
├── services.sh   # Порты, процессы, health checks
└── README.md     # Эта документация
```

## Библиотеки

### core.sh

Базовые функции - должна загружаться первой.

```bash
# Цвета (автоматически отключаются в non-TTY)
echo -e "${RED}Ошибка${NC}"
echo -e "${GREEN}Успех${NC}"
echo -e "${YELLOW}Предупреждение${NC}"
echo -e "${BLUE}Информация${NC}"

# Логирование
log_info "Информация"
log_success "Успех"
log_warning "Предупреждение"
log_error "Ошибка"
log_step "Шаг процесса"
log_verbose "Подробно (только если VERBOSE=true)"
log_debug "Отладка (только если DEBUG=true)"

# Print helpers
print_header "Заголовок секции"
print_status "success" "Сообщение"
print_separator "-" 60

# Guards
require_bash_version 4 3              # bash 4.3+
require_var "PROJECT_ROOT" "Error"    # переменная установлена
require_command "docker" "Error"      # команда доступна
require_file "/path" "Error"          # файл существует
require_dir "/path" "Error"           # директория существует

# Утилиты
is_true "$FLAG"                       # true/1/yes/y
is_false "$FLAG"                      # false/0/no/n/empty
result=$(trim "  text  ")             # "text"
parse_version "mise 2024.1.0"         # "2024.1.0"
version_gte "1.2.3" "1.2.0"           # true
```

### platform.sh

Определение операционной системы и окружения.

```bash
# Определение ОС
os=$(detect_os)           # windows | wsl | linux | macos
platform=$(detect_platform)  # wsl-pacman | linux-apt | macos | etc.

# Информация о дистрибутиве
distro=$(get_distro_id)      # ubuntu | arch | fedora
codename=$(get_distro_codename)  # jammy | bookworm
version=$(get_distro_version)    # 22.04 | 12

# Boolean проверки
is_wsl && echo "Running in WSL"
is_macos && echo "Running on macOS"
is_linux && echo "Running on Linux"
is_arch && echo "Arch Linux (pacman)"
is_debian_based && echo "Debian/Ubuntu (apt)"

# Shell config
config=$(get_shell_config)   # ~/.bashrc | ~/.zshrc
has_in_shell_config "mise"   # проверка наличия строки

# Переменные окружения (автоматически устанавливаются)
echo $OS_TYPE        # wsl | linux | macos | windows
echo $BIN_EXT        # .exe (Windows) или пусто
echo $VENV_BIN_DIR   # Scripts (Windows) или bin

# Пакетный менеджер
pm=$(get_package_manager)    # pacman | apt | dnf | brew
install_package git curl     # установка пакетов
check_sudo_available         # проверка sudo
```

### prompts.sh

Взаимодействие с пользователем.

```bash
# Подтверждение
confirm_action "Продолжить?" "y"   # default: yes
confirm_action "Удалить?" "n"      # default: no
confirm_destructive "Это опасно!"  # требует ввод YES

# Выбор опции
choice=$(select_option "Выберите:" "A" "B" "C")
choices=$(select_multiple "Выберите:" "A" "B" "C")

# Ввод
name=$(prompt_input "Имя" "default")
password=$(prompt_password "Пароль")

# Прогресс
show_spinner "Загрузка..."
# ... долгая операция ...
hide_spinner "success"

show_progress 50 100 "Обработка"

# Ожидание
wait_for_keypress "Нажмите клавишу..."
countdown 5 "Запуск через"
```

### files.sh

Работа с файлами.

```bash
# Безопасное удаление (защита от rm /)
safe_rm "/path/to/dir"
safe_rm "/path/to/dir" "true"  # force

# Кросс-платформенный sed -i
sed_inplace "s/old/new/g" "/path/to/file"

# Директории
ensure_dir "/path/to/dir"
copy_with_backup "/source" "/dest"

# Backup
backup=$(backup_file "/path/to/file")
backup_dir=$(create_backup_dir "prefix")
cleanup_old_backups "$HOME/.backups" 7

# Размер
format_size 1073741824   # "1 GB"
size=$(get_dir_size "/path")
human=$(get_dir_size_human "/path")

# Время модификации
mtime=$(get_file_mtime "/path")
newest=$(find_newest_file "/dir" "*.go")
is_file_newer "/a" "/b"
is_file_older "/a" "/b"

# Временные файлы
tmp=$(create_temp_file "prefix")
tmpdir=$(create_temp_dir "prefix")

# Пути
path=$(normalize_path "/foo//bar/../baz")
rel=$(get_relative_path "/base" "/base/sub/file")
```

### services.sh

Сервисы, порты, процессы.

```bash
# Порты
check_port_listening 8080
pid=$(get_pid_on_port 8080)
kill_process_on_port 8080 "api-gateway"
wait_for_port 8080 "used" 30   # ждать занятия
wait_for_port 8080 "free" 10   # ждать освобождения

# Процессы
is_process_running 12345
pid=$(get_process_by_name "api-gateway")
stop_process 12345 "api-gateway" 10

# Python venv
activate_venv "/path/to/venv"
is_venv_active
version=$(get_python_version)

# Go сервисы
path=$(get_binary_path "api-gateway")
status=$(detect_go_service_changes "api-gateway")
# Returns: REBUILD_NEEDED | UP_TO_DATE | NO_SOURCES

# Health checks
check_health_endpoint "http://localhost:8080/health"
wait_for_service "http://localhost:8080/health" 30 "api"
status=$(check_service_status 8080 "http://localhost:8080/health")
# Returns: running | unhealthy | stopped

# Docker
is_docker_installed
is_docker_running
wait_for_docker 60
is_container_running "postgres"
wait_for_container "postgres" 30

# mise
is_mise_installed
dir=$(get_mise_data_dir)
dir=$(get_mise_config_dir)
```

## Опции загрузки

```bash
# Минимальный режим (только core + platform)
CC1C_LIB_MINIMAL=1 source scripts/lib/init.sh

# Без prompts.sh
CC1C_LIB_SKIP_PROMPTS=1 source scripts/lib/init.sh

# Без services.sh
CC1C_LIB_SKIP_SERVICES=1 source scripts/lib/init.sh
```

## Миграция

Для перехода с `scripts/setup/lib/common.sh` или `scripts/dev/common-functions.sh`:

```bash
# Было
source "$PROJECT_ROOT/scripts/setup/lib/common.sh"
source "$SCRIPT_DIR/common-functions.sh"

# Стало
source "$PROJECT_ROOT/scripts/lib/init.sh"
```

Основные изменения в именах функций:
- `verbose_log` -> `log_verbose`
- `print_status "success"` -> без изменений (совместимо)
