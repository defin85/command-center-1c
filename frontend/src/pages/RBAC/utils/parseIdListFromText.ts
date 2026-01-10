export function parseIdListFromText(value: unknown): string[] {
  if (typeof value !== 'string') return []
  const parts = value
    .split(/[\n\r\t ,;]+/)
    .map((part) => part.trim())
    .filter(Boolean)

  const seen = new Set<string>()
  const out: string[] = []
  for (const part of parts) {
    if (seen.has(part)) continue
    seen.add(part)
    out.push(part)
  }
  return out
}

