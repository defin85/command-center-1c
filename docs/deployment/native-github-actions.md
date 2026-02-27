# Native Deploy via GitHub Actions

Краткая техническая памятка. Основной deployment-гайд: [README.md](./README.md)

## 1. Server bootstrap

Install server-side deploy helper:

```bash
./scripts/deploy/install-server-deployer.sh --host 80.227.11.62 --port 54545 --user antifriz --ssh-pass '***'
```

This installs:

- `/usr/local/bin/cc1c-deploy`
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

1. Build frontend (`frontend/dist`)
2. Build Go binaries (`cc1c-api-gateway`, `cc1c-worker`)
3. Pack release archive
4. Upload archive to server
5. Run `/usr/local/bin/cc1c-deploy <archive> <sha>`

## 4. Notes

- Current server mode is configured for no-domain/no-TLS startup.
- When domain and TLS are ready, update Django settings in `/etc/command-center-1c/env.production`.
