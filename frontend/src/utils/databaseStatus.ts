type TagMeta = {
  label: string
  color: string
}

type Severity = 0 | 1 | 2 | 3

const statusMap: Record<string, TagMeta> = {
  active: { label: 'Active', color: 'green' },
  inactive: { label: 'Inactive', color: 'default' },
  maintenance: { label: 'Maintenance', color: 'orange' },
  error: { label: 'Error', color: 'red' },
}

const healthMap: Record<string, TagMeta> = {
  ok: { label: 'OK', color: 'green' },
  degraded: { label: 'Degraded', color: 'orange' },
  down: { label: 'Down', color: 'red' },
  unknown: { label: 'Unknown', color: 'default' },
}

const statusSeverity: Record<string, Severity> = {
  active: 0,
  inactive: 1,
  maintenance: 2,
  error: 3,
}

const healthSeverity: Record<string, Severity> = {
  ok: 0,
  unknown: 1,
  degraded: 2,
  down: 3,
}

const severityColor: Record<Severity, string> = {
  0: 'green',
  1: 'default',
  2: 'orange',
  3: 'red',
}

export const getStatusTag = (status?: string | null): TagMeta => {
  if (!status) return { label: 'Unknown', color: 'default' }
  return statusMap[status] ?? { label: 'Unknown', color: 'default' }
}

export const getHealthTag = (health?: string | null): TagMeta => {
  if (!health) return { label: 'Unknown', color: 'default' }
  return healthMap[health] ?? { label: 'Unknown', color: 'default' }
}

export const getSummaryTag = (status?: string | null, health?: string | null): TagMeta => {
  const statusTag = getStatusTag(status)
  const healthTag = getHealthTag(health)
  const statusLevel = status ? statusSeverity[status] ?? 1 : 1
  const healthLevel = health ? healthSeverity[health] ?? 1 : 1
  const severity = Math.max(statusLevel, healthLevel) as Severity

  return {
    label: `${statusTag.label} / ${healthTag.label}`,
    color: severityColor[severity],
  }
}
