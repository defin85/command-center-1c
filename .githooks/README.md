# Git Hooks для OpenAPI Contract Validation

Этот проект использует кастомные git hooks для автоматической валидации OpenAPI спецификаций.

## Установка

Для активации git hooks выполните команду:

```bash
git config core.hooksPath .githooks
```

Эта команда настраивает Git использовать директорию `.githooks` вместо стандартной `.git/hooks`.

## Проверка установки

Убедитесь, что hooks активированы:

```bash
git config core.hooksPath
# Должно вывести: .githooks
```

## Доступные Hooks

### pre-commit

Запускается **перед каждым коммитом** и выполняет:

1. **Валидацию OpenAPI спецификаций** (если изменились `contracts/**/*.yaml`)
   - Проверяет синтаксис YAML
   - Проверяет корректность OpenAPI схемы
   - Блокирует коммит при ошибках

2. **Проверка Breaking Changes**
   - Сравнивает с предыдущей версией спецификации
   - **НЕ блокирует коммит**, только предупреждает
   - Требует подтверждения пользователя при breaking changes

3. **Автоматическая регенерация клиентов**
   - Генерирует Go server types
   - Генерирует Python client
   - Добавляет сгенерированные файлы в коммит

## Отключение Hooks (если необходимо)

Временно отключить все hooks для конкретного коммита:

```bash
git commit --no-verify -m "message"
```

Полностью отключить hooks:

```bash
git config --unset core.hooksPath
```

## Troubleshooting

### Hook не запускается

Проверьте права доступа:

```bash
chmod +x .githooks/pre-commit
```

### Ошибки валидации

Запустите валидацию вручную для диагностики:

```bash
./contracts/scripts/validate-specs.sh
```

### Проблемы с breaking changes

Проверьте вручную:

```bash
./contracts/scripts/check-breaking-changes.sh
```

## Рекомендации

- **ВСЕГДА** активируйте hooks после клонирования репозитория
- **НЕ** используйте `--no-verify` без крайней необходимости
- При breaking changes **ОБЯЗАТЕЛЬНО** обновите версию API и документацию
