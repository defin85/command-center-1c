# CommandCenter1C Claude Skills

Коллекция специализированных Skills для работы с проектом CommandCenter1C.

## 📚 Доступные Skills

### 1. cc1c-navigator
**Назначение:** Навигация по monorepo структуре и архитектуре

**Подробности:** См. `.claude/skills/cc1c-navigator/SKILL.md`

---

### 2. cc1c-service-builder
**Назначение:** Создание новых компонентов по шаблонам (Go, Django, React)

**Подробности:** См. `.claude/skills/cc1c-service-builder/SKILL.md`

**Шаблоны:**
- `templates/go-service.go.template`
- `templates/django-app.py.template`
- `templates/react-component.tsx.template`

---

### 3. cc1c-odata-integration
**Назначение:** Работа с 1С через OData протокол

**Подробности:** См. `.claude/skills/cc1c-odata-integration/SKILL.md`

**⚠️ КРИТИЧНО:** Транзакции 1С < 15 секунд!

**Примеры:** `odata-examples.py` - 15 примеров работы с OData

---

### 4. cc1c-devops
**Назначение:** DevOps операции и deployment

**Подробности:** См. `.claude/skills/cc1c-devops/SKILL.md`

**Основные команды:**
- `make dev`, `make logs`, `make test`, `make stop`

---

### 5. cc1c-sprint-guide
**Назначение:** Гайд по текущему спринту и roadmap

**Подробности:** См. `.claude/skills/cc1c-sprint-guide/SKILL.md`

**⭐ Важно:** Проект реализуется по варианту **Balanced** (16 weeks, 5 phases)

---

### 6. cc1c-test-runner
**Назначение:** Запуск и отладка тестов

**Подробности:** См. `.claude/skills/cc1c-test-runner/SKILL.md`

**⚠️ Требование:** Coverage > 70% обязательно!

---

## 🎯 Как использовать Skills

### Автоматическая активация

Claude автоматически выбирает нужный skill на основе:
1. Контекста вашего вопроса
2. Ключевых слов (триггеров)
3. Типа задачи

**Примеры:**

```
Вопрос: "Где находится OData adapter?"
→ Активируется: cc1c-navigator

Вопрос: "Создай новый Django app для управления шаблонами"
→ Активируется: cc1c-service-builder

Вопрос: "Как сделать batch операцию для 1С?"
→ Активируется: cc1c-odata-integration

Вопрос: "Запусти все сервисы"
→ Активируется: cc1c-devops

Вопрос: "Где мы сейчас в roadmap?"
→ Активируется: cc1c-sprint-guide

Вопрос: "Запусти тесты для Django"
→ Активируется: cc1c-test-runner
```

### Явная активация

Можно явно указать skill:

```
@cc1c-navigator где находится Worker pool?
@cc1c-devops покажи логи orchestrator
@cc1c-sprint-guide что делать дальше?
```

## 📖 Структура Skill

Каждый skill содержит:

### SKILL.md (обязательно)
```markdown
---
name: skill-name
description: "Detailed description with WHEN to use"
allowed-tools: ["Tool1", "Tool2"]
---

# Skill Name

## Purpose
## When to Use
## Instructions
## Examples
## References
```

### Дополнительные файлы (опционально)

**Шаблоны кода:**
- `cc1c-service-builder/templates/*.template`

**Примеры кода:**
- `cc1c-odata-integration/odata-examples.py`

## 🛠️ Разработка новых Skills

### Создание нового Skill

1. Создай директорию в `.claude/skills/`
```bash
mkdir .claude/skills/your-skill-name
```

2. Создай `SKILL.md` с YAML frontmatter
```markdown
---
name: your-skill-name
description: "Clear description with WHEN trigger words"
allowed-tools: ["Tool1", "Tool2"]
---

# Your Skill Name
...
```

3. Добавь шаблоны/примеры если нужно

4. Протестируй skill

### Best Practices

1. **Description должен быть триггер-ориентированным**
   - Включай ключевые слова которые активируют skill
   - Объясни КОГДА использовать

2. **Используй конкретные примеры**
   - Реальный код
   - Реальные команды
   - Реальные use cases

3. **Ссылайся на существующие файлы проекта**
   - CLAUDE.md
   - ROADMAP.md
   - Другие документы

4. **Соблюдай структуру проекта**
   - Следуй соглашениям
   - Используй правильные пути
   - Проверяй что примеры работают

## 📊 Статистика Skills

```
Общее количество Skills: 6
Общее количество строк:   5,526
Шаблонов кода:            3
Файлов с примерами:       1

Распределение по размеру (строки):
1. cc1c-test-runner       887
2. cc1c-service-builder   822
3. cc1c-odata-integration 709
4. cc1c-devops            656
5. cc1c-sprint-guide      541
6. cc1c-navigator         372
```

## 🔗 Ссылки

- **Главная документация:** `CLAUDE.md` (root)
- **Roadmap:** `docs/ROADMAP.md`
- **Quick Start:** `docs/START_HERE.md`
- **Project README:** `README.md`

## 💡 Tips

1. **Не знаешь какой skill нужен?** Просто задай вопрос - Claude выберет сам
2. **Skill не активируется?** Используй явный вызов: `@skill-name`
3. **Хочешь создать свой skill?** Следуй структуре существующих
4. **Нужна помощь?** Спроси `@cc1c-navigator` про структуру проекта

---

**Версия:** 1.0
**Дата создания:** 2025-01-17
**Автор:** AI Architect Team
**Проект:** CommandCenter1C
