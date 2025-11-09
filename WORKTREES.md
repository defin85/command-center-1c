# 🌲 Git Worktrees - Параллельная разработка

> **Список активных worktrees для параллельной работы над треками**

## Активные Worktrees

| Worktree | Ветка | Путь | Track | Статус |
|----------|-------|------|-------|--------|
| **Main** | `master` | `C:/1CProject/command-center-1c` | - | ✅ Active |
| **Track 0** | `feature/track0-batch-service-deadlock-fix` | `C:/1CProject/command-center-1c-track0` | Deadlock Fix | ✅ Ready |

## Быстрые команды

### Просмотр всех worktrees

```bash
git worktree list
```

### Переключение между worktrees

```bash
# В Track 0
cd /c/1CProject/command-center-1c-track0

# Обратно в main
cd /c/1CProject/command-center-1c
```

### Создать новый worktree (для других треков)

```bash
# Track 1: Template Engine
git worktree add ../command-center-1c-track1 -b feature/track1-template-engine

# Track 2A: Celery Producer
git worktree add ../command-center-1c-track2a -b feature/track2a-celery-producer

# Track 2B: Redis Consumer
git worktree add ../command-center-1c-track2b -b feature/track2b-redis-consumer

# Track 3: Real Operations
git worktree add ../command-center-1c-track3 -b feature/track3-real-operations

# Track 4: Frontend
git worktree add ../command-center-1c-track4 -b feature/track4-frontend-improvements
```

### Удалить worktree (после merge PR)

```bash
git worktree remove ../command-center-1c-track0
git branch -d feature/track0-batch-service-deadlock-fix
```

## Преимущества worktrees

✅ **Параллельная работа** - несколько треков одновременно
✅ **Изоляция** - изменения в одном worktree не влияют на другие
✅ **Быстрое переключение** - без git checkout и потери uncommitted changes
✅ **Независимое тестирование** - можно запускать тесты в разных треках параллельно

## Важные замечания

⚠️ **Не коммитить в master из worktree** - только в feature ветках
⚠️ **Синхронизация** - периодически делать `git fetch` во всех worktrees
⚠️ **Cleanup** - удалять worktrees после merge PR

## Структура проекта с worktrees

```
C:/1CProject/
├── command-center-1c/              ← Main worktree (master)
├── command-center-1c-track0/       ← Track 0 worktree
├── command-center-1c-track1/       ← Track 1 worktree (future)
├── command-center-1c-track2a/      ← Track 2A worktree (future)
├── command-center-1c-track2b/      ← Track 2B worktree (future)
└── ras-grpc-gw/                    ← External repo
```

## См. также

- **Parallel Work Plan:** `docs/PARALLEL_WORK_PLAN.md`
- **Track 0 README:** `../command-center-1c-track0/WORKTREE_README.md`
