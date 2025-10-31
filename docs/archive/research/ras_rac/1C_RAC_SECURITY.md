# RAC CLI Security Considerations

## Overview

RAC (Remote Administration Client) - утилита командной строки 1C:Enterprise для администрирования кластеров.

## Fundamental Limitation

**ВАЖНО:** RAC CLI принимает пароли **ТОЛЬКО через параметры командной строки**:
- `--cluster-pwd=<password>` - пароль администратора кластера
- `--infobase-pwd=<password>` - пароль администратора информационной базы

**НЕ поддерживается:**
- ❌ Environment variables
- ❌ STDIN для паролей
- ❌ Config files

Это фундаментальное ограничение платформы 1C, не нашей реализации.

## Security Implications

### Risk: Process List Visibility

Пароли видны в списке процессов:
- Windows Task Manager
- `ps` / `Get-Process` commands
- Логи операционной системы

### Mitigation Measures

**1. Network Isolation**
- installation-service работает локально на Windows Server с 1C
- RAC CLI вызывается локально (localhost → localhost)
- Минимальный риск удаленного доступа к process list

**2. Short Process Lifetime**
- RAC процессы живут секунды (пока выполняется команда)
- Минимальное окно для potential leak

**3. Access Control**
- Ограничить доступ к Windows Server
- Только доверенные администраторы имеют доступ к серверу
- Firewall rules для installation-service API

**4. HTTPS для Django → installation-service**
- Шифрование транспорта при передаче паролей через HTTP
- Рекомендуется для production deployment

**5. Authentication для installation-service API**
- API key или JWT для вызовов API
- Rate limiting для защиты от brute force

**6. Audit Logging**
- Логировать кто и когда вызывал RAC (без паролей)
- Мониторинг подозрительной активности

## Best Practices

1. **Минимальные права кластера**: Используй учетные записи с минимальными правами для RAC операций
2. **Rotate credentials**: Регулярно меняй пароли администраторов кластера
3. **Monitor access**: Отслеживай кто имеет доступ к Windows Server
4. **Network segmentation**: Изолируй 1C серверы в защищенной сети

## Implementation in CommandCenter1C

### Architecture

```
┌──────────────────┐
│ Django           │  HTTP (with password in params)
│ Orchestrator     ├────────────────────────┐
│ (Linux Docker)   │                        │
└──────────────────┘                        ▼
                                 ┌──────────────────────┐
                                 │ installation-service │
                                 │ (Windows Go)         │
                                 └──────────┬───────────┘
                                            │
                                            │ RAC CLI
                                            │ (password in command line)
                                            ▼
                                 ┌──────────────────────┐
                                 │ 1C RAS               │
                                 │ (localhost:1545)     │
                                 └──────────────────────┘
```

### Security Measures Applied

1. **Password Masking in Logs**
   - Django client masks passwords before logging
   - Go service does NOT log RAC commands with passwords
   - All error logs use safe params without passwords

2. **Process Isolation**
   - RAC processes are short-lived (2-3 seconds per call)
   - Worker pool limits concurrent RAC calls (max 10)
   - Each process terminates after command execution

3. **Network Isolation**
   - installation-service accessible only from Django (internal network)
   - RAC connects to localhost:1545 (local RAS)
   - No external exposure of RAC CLI

4. **Session Cleanup**
   - Django clears session data after import
   - 30-minute timeout for stale sessions
   - Automatic cleanup on errors

## Risk Assessment

**Risk Level:** Medium-Low

**Justification:**
- Passwords visible in process list for 2-3 seconds only
- Access to Windows Server restricted to administrators
- Local network isolation (no remote access)
- Short-lived processes minimize exposure window

**Residual Risk:**
- Administrators with access to Windows Server CAN see passwords during RAC execution
- Process monitoring tools MAY capture passwords
- OS audit logs MAY contain command lines

**Mitigation:**
- Restrict Windows Server access to trusted administrators only
- Use minimal privilege accounts for cluster operations
- Implement audit logging and monitoring
- Rotate credentials regularly

## References

- RAC CLI Documentation: checked via `rac.exe help infobase`
- 1C Platform: 8.3.27.1786
- Security Assessment Date: 2025-01-17
- Implementation: CommandCenter1C project
