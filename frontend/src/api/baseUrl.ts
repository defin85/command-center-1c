const DEFAULT_API_PORT = 8180

type EnvKey = 'VITE_BASE_HOST' | 'VITE_API_URL' | 'VITE_WS_HOST'
type EnvRecord = Partial<Record<EnvKey, string>>

const readEnv = (): EnvRecord => {
  if (typeof globalThis === 'undefined') {
    return {}
  }
  const env = (globalThis as { __CC1C_ENV__?: EnvRecord }).__CC1C_ENV__
  return env ?? {}
}

const normalizeEnvValue = (value?: string | null): string | undefined => {
  if (!value) return undefined
  const trimmed = value.trim()
  if (!trimmed || trimmed.startsWith('%VITE_')) {
    return undefined
  }
  return trimmed
}

const getEnvValue = (key: EnvKey): string | undefined => {
  const env = readEnv()
  return normalizeEnvValue(env[key])
}

const normalizeHost = (host: string): string => {
  if (host.startsWith('localhost')) {
    return `127.0.0.1${host.slice('localhost'.length)}`
  }
  return host
}

const resolveBaseHost = (): string => {
  const envHost = getEnvValue('VITE_BASE_HOST')
  if (envHost) {
    return envHost
  }
  const envApiUrl = getEnvValue('VITE_API_URL')
  if (envApiUrl) {
    try {
      return new URL(envApiUrl).hostname
    } catch {
      // ignore invalid URL and fallback
    }
  }
  if (typeof window === 'undefined') {
    return 'localhost'
  }
  return window.location.hostname || 'localhost'
}

export const getBaseHost = (): string => {
  return resolveBaseHost()
}

export const getApiBaseUrl = (): string => {
  const envUrl = getEnvValue('VITE_API_URL')
  if (envUrl) {
    // Allow specifying a full URL (prod-like) or a relative API prefix (dev/proxy).
    // Relative prefixes map to the current origin (browser will resolve against window.location).
    if (envUrl.startsWith('/')) {
      if (typeof window === 'undefined') {
        return ''
      }
      return window.location.origin
    }
    return envUrl
      .replace(/\/api\/v\d+\/?$/, '')
      .replace(/\/api\/?$/, '')
  }

  // Default: same-origin (dev via Vite proxy, prod via reverse proxy).
  if (typeof window !== 'undefined') {
    return window.location.origin
  }

  // Fallback for non-browser usage (tests, tooling).
  const baseHost = resolveBaseHost()
  return `http://${baseHost}:${DEFAULT_API_PORT}`
}

export const getWsHost = (): string => {
  const envHost = getEnvValue('VITE_WS_HOST')
  if (envHost) {
    return normalizeHost(envHost)
  }

  // Default: same-origin WebSocket endpoint (proxied to API Gateway).
  if (typeof window !== 'undefined') {
    return window.location.host
  }

  try {
    return normalizeHost(new URL(getApiBaseUrl()).host)
  } catch {
    const baseHost = getBaseHost()
    return normalizeHost(`${baseHost}:${DEFAULT_API_PORT}`)
  }
}
