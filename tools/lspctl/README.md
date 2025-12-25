# lspctl

CLI helper for LSP JSON-RPC over stdio with JSON output.

## Requirements

- gopls
- typescript-language-server
- pyright-langserver
- rust-analyzer

## Examples

```bash
python tools/lspctl/lspctl.py definition --file go-services/api-gateway/main.go --line 10 --col 5
python tools/lspctl/lspctl.py references --file frontend/src/main.tsx --line 5 --col 10
python tools/lspctl/lspctl.py hover --file orchestrator/manage.py --line 1 --col 1
python tools/lspctl/lspctl.py diagnostics --file frontend/src/main.tsx
python tools/lspctl/lspctl.py rename --file go-services/api-gateway/main.go --line 10 --col 5 --new-name NewName
python tools/lspctl/lspctl.py documentSymbol --file frontend/src/main.tsx
python tools/lspctl/lspctl.py workspaceSymbol --query "CreateUser" --lang go
```

## Usage

All commands return JSON to stdout: `{"result": ...}` or `{"error": "..."}`.

### One-shot mode

Starts a new LSP server for each call (no cache).

```bash
python tools/lspctl/lspctl.py definition --file path/to/file.go --line 10 --col 5
```

### Daemon mode (recommended)

Keeps LSP servers alive and reuses their caches.

```bash
python tools/lspctl/lspctl.py serve --socket /tmp/lspctl.sock
python tools/lspctl/lspctl.py call hover --file path/to/file.go --line 10 --col 5 --socket /tmp/lspctl.sock
python tools/lspctl/lspctl.py shutdown --socket /tmp/lspctl.sock
```

## Daemon mode

```bash
python tools/lspctl/lspctl.py serve --socket /tmp/lspctl.sock

python tools/lspctl/lspctl.py call definition --file go-services/api-gateway/main.go --line 10 --col 5 --socket /tmp/lspctl.sock
python tools/lspctl/lspctl.py call workspaceSymbol --query "CreateUser" --lang go --socket /tmp/lspctl.sock
python tools/lspctl/lspctl.py shutdown --socket /tmp/lspctl.sock
```

## Options

- `--lang` to force language (go, python, typescript, javascript)
- `--venv` explicit venv path for Python
- `--server-cmd` to override server command
- `--root` to set workspace root (default: cwd)
- `--timeout` response timeout
- `--socket` path to daemon socket (serve/call/shutdown only)

Python venv auto-detection:
- Searches for `.venv` or `venv` from the file directory up to workspace root.
- When found, `pyright-langserver` starts with `VIRTUAL_ENV` and updated `PATH`.
