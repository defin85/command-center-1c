export const formatDateTime = (value: string | null | undefined): string => {
  if (!value) {
    return '—'
  }
  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) {
    return value
  }
  return new Date(timestamp).toLocaleString()
}
