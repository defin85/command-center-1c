export const normalizeInternalReturnTo = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  if (!normalized.startsWith('/')) {
    return null
  }
  if (normalized.startsWith('//')) {
    return null
  }
  return normalized
}

export const buildRelativeHref = (pathname: string, searchParams: URLSearchParams): string => {
  const query = searchParams.toString()
  return query ? `${pathname}?${query}` : pathname
}

