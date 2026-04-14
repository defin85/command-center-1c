import { Tag } from 'antd'
import type { ReactNode } from 'react'
import { usePlatformTranslation } from '@/i18n'

type StatusBadgeProps = {
  status: string
  label?: ReactNode
}

const DEFAULT_STYLES: Record<string, { backgroundColor: string, borderColor: string, color: string }> = {
  active: {
    backgroundColor: '#dcfce7',
    borderColor: '#86efac',
    color: '#166534',
  },
  compatible: {
    backgroundColor: '#dcfce7',
    borderColor: '#86efac',
    color: '#166534',
  },
  published: {
    backgroundColor: '#dcfce7',
    borderColor: '#86efac',
    color: '#166534',
  },
  deactivated: {
    backgroundColor: '#f3f4f6',
    borderColor: '#d1d5db',
    color: '#374151',
  },
  inactive: {
    backgroundColor: '#f3f4f6',
    borderColor: '#d1d5db',
    color: '#374151',
  },
  pinned: {
    backgroundColor: '#fef3c7',
    borderColor: '#fcd34d',
    color: '#92400e',
  },
  unknown: {
    backgroundColor: '#dbeafe',
    borderColor: '#93c5fd',
    color: '#1d4ed8',
  },
  warning: {
    backgroundColor: '#fef3c7',
    borderColor: '#fcd34d',
    color: '#92400e',
  },
  incompatible: {
    backgroundColor: '#ffedd5',
    borderColor: '#fdba74',
    color: '#9a3412',
  },
  error: {
    backgroundColor: '#fee2e2',
    borderColor: '#fca5a5',
    color: '#b91c1c',
  },
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const { t } = usePlatformTranslation()
  const style = DEFAULT_STYLES[status] ?? DEFAULT_STYLES.unknown
  const resolvedLabel = label ?? (() => {
    switch (status) {
      case 'active':
        return t(($) => $.statusBadge.active)
      case 'compatible':
        return t(($) => $.statusBadge.compatible)
      case 'published':
        return t(($) => $.statusBadge.published)
      case 'deactivated':
        return t(($) => $.statusBadge.deactivated)
      case 'inactive':
        return t(($) => $.statusBadge.inactive)
      case 'pinned':
        return t(($) => $.statusBadge.pinned)
      case 'warning':
        return t(($) => $.statusBadge.warning)
      case 'incompatible':
        return t(($) => $.statusBadge.incompatible)
      case 'error':
        return t(($) => $.statusBadge.error)
      case 'unknown':
        return t(($) => $.statusBadge.unknown)
      default:
        return status
    }
  })()

  return (
    <Tag
      style={{
        backgroundColor: style.backgroundColor,
        borderColor: style.borderColor,
        color: style.color,
      }}
    >
      {resolvedLabel}
    </Tag>
  )
}
