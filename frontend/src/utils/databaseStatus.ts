type TagMeta = {
  label: string
  color: string
}

type StatusLabelKey = 'active' | 'inactive' | 'maintenance' | 'error' | 'unknown'
type HealthLabelKey = 'ok' | 'degraded' | 'down' | 'unknown'
type StatusLabels = Partial<Record<StatusLabelKey, string>>
type HealthLabels = Partial<Record<HealthLabelKey, string>>

type Severity = 0 | 1 | 2 | 3

const defaultStatusLabels: Record<StatusLabelKey, string> = {
  active: 'Active',
  inactive: 'Inactive',
  maintenance: 'Maintenance',
  error: 'Error',
  unknown: 'Unknown',
}

const defaultHealthLabels: Record<HealthLabelKey, string> = {
  ok: 'OK',
  degraded: 'Degraded',
  down: 'Down',
  unknown: 'Unknown',
}

const statusColors: Record<Exclude<StatusLabelKey, 'unknown'>, string> = {
  active: 'green',
  inactive: 'default',
  maintenance: 'orange',
  error: 'red',
}

const healthColors: Record<Exclude<HealthLabelKey, 'unknown'>, string> = {
  ok: 'green',
  degraded: 'orange',
  down: 'red',
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

const resolveStatusLabel = (status: StatusLabelKey, labels?: StatusLabels) => (
  labels?.[status] ?? defaultStatusLabels[status]
)

const resolveHealthLabel = (health: HealthLabelKey, labels?: HealthLabels) => (
  labels?.[health] ?? defaultHealthLabels[health]
)

export const getStatusTag = (status?: string | null, labels?: StatusLabels): TagMeta => {
  if (!status) {
    return { label: resolveStatusLabel('unknown', labels), color: 'default' }
  }
  if (status === 'active' || status === 'inactive' || status === 'maintenance' || status === 'error') {
    return { label: resolveStatusLabel(status, labels), color: statusColors[status] }
  }
  return { label: resolveStatusLabel('unknown', labels), color: 'default' }
}

export const getHealthTag = (health?: string | null, labels?: HealthLabels): TagMeta => {
  if (!health) {
    return { label: resolveHealthLabel('unknown', labels), color: 'default' }
  }
  if (health === 'ok' || health === 'degraded' || health === 'down') {
    return { label: resolveHealthLabel(health, labels), color: healthColors[health] }
  }
  return { label: resolveHealthLabel('unknown', labels), color: 'default' }
}

export const getSummaryTag = (
  status?: string | null,
  health?: string | null,
  labels?: { status?: StatusLabels; health?: HealthLabels },
): TagMeta => {
  const statusTag = getStatusTag(status, labels?.status)
  const healthTag = getHealthTag(health, labels?.health)
  const statusLevel = status ? statusSeverity[status] ?? 1 : 1
  const healthLevel = health ? healthSeverity[health] ?? 1 : 1
  const severity = Math.max(statusLevel, healthLevel) as Severity

  return {
    label: `${statusTag.label} / ${healthTag.label}`,
    color: severityColor[severity],
  }
}
