export function getEffectiveAccessSourceTagColor(source: string): 'blue' | 'purple' | 'gold' {
  if (source === 'direct') return 'blue'
  if (source === 'group') return 'purple'
  return 'gold'
}

