export type SelectOption = { label: string; value: string }

export function ensureSelectOptionsContain(
  options: SelectOption[],
  selectedIds: Array<string | undefined>,
  labelById: Map<string, string>,
): SelectOption[] {
  const ids = selectedIds
    .map((id) => (typeof id === 'string' ? id.trim() : ''))
    .filter((id) => id.length > 0)

  if (ids.length === 0) return options

  const existing = new Set(options.map((opt) => opt.value))
  const missing = ids.filter((id) => !existing.has(id))
  if (missing.length === 0) return options

  const injected = missing.map((id) => ({ value: id, label: labelById.get(id) ?? id }))
  return [...injected, ...options]
}

