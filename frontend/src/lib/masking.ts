const MASK = '***'

const SENSITIVE_KEYS = new Set([
  'db_password',
  'db_pwd',
  'target_db_password',
  'password',
  'secret',
  'token',
  'api_key',
  'access_key',
  'secret_key',
  'stdin',
  'args_text',
])

const SENSITIVE_FLAG_PREFIXES = [
  '--db-pwd',
  '--db-password',
  '--password',
  '--target-database-password',
  '--target-db-password',
  '--target-db-pwd',
  '--secret',
  '--token',
  '--api-key',
]

export const isSensitiveKey = (key: string): boolean => {
  const normalized = String(key || '').trim().toLowerCase()
  if (!normalized) return false
  return (
    SENSITIVE_KEYS.has(normalized)
    || normalized.endsWith('_password')
    || normalized.endsWith('_pwd')
  )
}

export const maskArgv = (argv: string[]): string[] => {
  if (!Array.isArray(argv) || argv.length === 0) return []

  const masked: string[] = []
  let idx = 0

  while (idx < argv.length) {
    const token = String(argv[idx] ?? '').trim()
    const lowered = token.toLowerCase()

    let matchedPrefix: string | null = null
    for (const prefix of SENSITIVE_FLAG_PREFIXES) {
      if (lowered === prefix || lowered.startsWith(`${prefix}=`)) {
        matchedPrefix = prefix
        break
      }
    }

    if (matchedPrefix !== null) {
      if (token.includes('=')) {
        masked.push(`${token.split('=', 1)[0]}=${MASK}`)
        idx += 1
        continue
      }

      masked.push(token)
      if (idx + 1 < argv.length) {
        masked.push(MASK)
        idx += 2
        continue
      }
      idx += 1
      continue
    }

    if (token.startsWith('/P') && token !== '/P***' && token.length > 2) {
      masked.push('/P***')
      idx += 1
      continue
    }

    masked.push(token)
    idx += 1
  }

  return masked
}

export const maskArgvTextLines = (value: string | undefined): string => {
  if (typeof value !== 'string' || value.trim().length === 0) return ''
  const lines = value
    .split('\n')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
  return maskArgv(lines).join('\n')
}

export const maskDeep = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map((item) => maskDeep(item))
  }

  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {}
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (isSensitiveKey(key)) {
        out[key] = MASK
        continue
      }

      if ((key === 'argv' || key === 'args' || key === 'resolved_args') && Array.isArray(item) && item.every((x) => typeof x === 'string')) {
        out[key] = maskArgv(item)
        continue
      }

      out[key] = maskDeep(item)
    }
    return out
  }

  return value
}

