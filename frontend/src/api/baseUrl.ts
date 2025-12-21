const DEFAULT_API_PORT = 8180

const normalizeHost = (host: string): string => {
  if (host.startsWith('localhost')) {
    return `127.0.0.1${host.slice('localhost'.length)}`
  }
  return host
}

const resolveBaseHost = (): string => {
  const envHost = import.meta.env.VITE_BASE_HOST
  if (envHost) {
    return envHost
  }
  const envApiUrl = import.meta.env.VITE_API_URL
  if (envApiUrl) {
    try {
      return new URL(envApiUrl).hostname
    } catch {
      // ignore invalid URL and fallback
    }
  }
  return window.location.hostname
}

export const getBaseHost = (): string => {
  return resolveBaseHost()
}

export const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_URL
  if (envUrl) {
    return envUrl
      .replace(/\/api\/v\d+\/?$/, '')
      .replace(/\/api\/?$/, '')
  }

  const baseHost = resolveBaseHost()
  return `http://${baseHost}:${DEFAULT_API_PORT}`
}

export const getWsHost = (): string => {
  const envHost = import.meta.env.VITE_WS_HOST
  if (envHost) {
    return normalizeHost(envHost)
  }

  try {
    return normalizeHost(new URL(getApiBaseUrl()).host)
  } catch {
    const baseHost = getBaseHost()
    return normalizeHost(`${baseHost}:${DEFAULT_API_PORT}`)
  }
}
