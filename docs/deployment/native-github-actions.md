# Native Deploy via GitHub Actions

Краткая техническая памятка. Основной deployment-гайд: [README.md](./README.md)

## 1. Server bootstrap

Install server-side deploy helper:

```bash
./scripts/deploy/install-server-deployer.sh --host 80.227.11.62 --port 54545 --user antifriz --ssh-pass '***'
```

This installs:

- `/usr/local/bin/cc1c-deploy`
- `/usr/local/bin/cc1c-upload-release`
- repo-managed disk/log guard config for `journald`, `rsyslog`, `logrotate` and `clickhouse-server`
- `/etc/sudoers.d/cc1c-deploy` (passwordless run of deploy helper for deploy user)

## 2. GitHub repository secrets

Set these repository secrets:

- `DEPLOY_HOST` - server IP or hostname
- `DEPLOY_PORT` - SSH port
- `DEPLOY_USER` - SSH user for deploy
- `DEPLOY_SSH_KEY` - private SSH key in OpenSSH format

## 3. Workflow

Workflow file:

- `.github/workflows/deploy-native.yml`

Trigger:

- `workflow_dispatch`
- push to `main` or `master`

Pipeline steps:

1. Build frontend release assets (`frontend/dist`)
2. Build Python wheelhouse for `orchestrator/requirements.txt`
3. Build Go binaries (`cc1c-api-gateway`, `cc1c-worker`)
4. Pack release archive
5. Upload archive to server
6. Run `/usr/local/bin/cc1c-deploy <archive> <sha>`

Separate workflow:

- `.github/workflows/validate-ui-platform.yml`
- runs full `frontend` gate (`lint + vitest + playwright + build`) on frontend/contracts changes
- deploy workflow no longer waits for the full UI gate on every push to `master`

## 4. Notes

- Current server mode is configured for no-domain/no-TLS startup via `config.settings.native`.
- When domain and TLS are ready, update Django settings in `/etc/command-center-1c/env.production`.
- `cc1c-deploy` now prefers bundled `orchestrator/wheelhouse` and reuses a shared venv under `/opt/command-center-1c/shared/venvs/<requirements-hash>` when requirements do not change.
