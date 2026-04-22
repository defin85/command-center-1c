import type { Location } from 'react-router-dom'

export const DEFAULT_AUTH_RETURN_TO = '/'
export const LOGIN_PATH = '/login'

type RouteLocationLike = Pick<Location, 'pathname' | 'search' | 'hash'>

export const buildReturnToPath = (location: RouteLocationLike): string => {
  const pathname = typeof location.pathname === 'string' && location.pathname.startsWith('/')
    ? location.pathname
    : DEFAULT_AUTH_RETURN_TO

  return resolveSafeReturnTo(`${pathname}${location.search || ''}${location.hash || ''}`)
}

export const buildLoginRedirectPath = (location: RouteLocationLike): string => {
  const returnTo = buildReturnToPath(location)

  if (returnTo === DEFAULT_AUTH_RETURN_TO) {
    return LOGIN_PATH
  }

  const next = new URLSearchParams()
  next.set('next', returnTo)
  return `${LOGIN_PATH}?${next.toString()}`
}

export const resolveSafeReturnTo = (candidate: string | null | undefined): string => {
  const raw = (candidate ?? '').trim()

  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) {
    return DEFAULT_AUTH_RETURN_TO
  }

  try {
    const parsed = new URL(raw, 'http://localhost')
    const normalized = `${parsed.pathname}${parsed.search}${parsed.hash}`

    if (
      normalized === LOGIN_PATH ||
      normalized.startsWith(`${LOGIN_PATH}?`) ||
      normalized.startsWith(`${LOGIN_PATH}#`)
    ) {
      return DEFAULT_AUTH_RETURN_TO
    }

    return normalized
  } catch {
    return DEFAULT_AUTH_RETURN_TO
  }
}
