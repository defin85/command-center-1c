# Offline Bundle

Эта директория содержит offline bundle для установки окружения разработки без интернета.

## Структура

```
offline-bundle/
├── manifest.json           # Метаданные и версии
├── checksums.sha256        # SHA256 для верификации
├── mise/
│   └── mise-linux-*        # mise binary
├── runtimes/
│   ├── go*.tar.gz          # Go runtime (~150MB)
│   ├── cpython-*.tar.*     # Python prebuilt (~50MB)
│   └── node-*.tar.gz       # Node.js runtime (~50MB)
├── python-deps/
│   └── *.whl               # Python wheels (~100MB)
└── npm-deps/
    └── *.tgz               # npm tarballs (~150MB)
```

## Подготовка bundle (требует интернет)

```bash
# На машине с интернетом
source scripts/setup/lib/offline.sh
prepare_offline_bundle

# Или с указанием платформы
prepare_offline_bundle linux-arm64 ./offline-bundle-arm64
```

## Установка из bundle (offline)

```bash
# На целевой машине без интернета
# 1. Скопируйте директорию offline-bundle/
# 2. Запустите установку:

source scripts/setup/lib/offline.sh
install_from_offline_bundle

# Или пропустить верификацию:
install_from_offline_bundle ./offline-bundle --skip-verify
```

## Размер

Примерный размер bundle: **~500MB**

Можно уменьшить, исключив зависимости:
- Без Python deps: ~400MB
- Без npm deps: ~350MB
- Только runtime'ы: ~250MB

## Поддерживаемые платформы

- `linux-amd64` (x86_64)
- `linux-arm64` (aarch64)
- `macos-amd64` (Intel Mac)
- `macos-arm64` (Apple Silicon)
