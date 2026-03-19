import { Tag } from 'antd'
import type { ReactNode } from 'react'

type StatusBadgeProps = {
  status: string
  label?: ReactNode
  colorMap?: Record<string, string>
}

const DEFAULT_COLORS: Record<string, string> = {
  active: 'green',
  compatible: 'green',
  published: 'green',
  deactivated: 'default',
  inactive: 'default',
  pinned: 'gold',
  unknown: 'default',
  warning: 'gold',
  incompatible: 'volcano',
  error: 'red',
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

export function StatusBadge({ status, label, colorMap }: StatusBadgeProps) {
  const color = colorMap?.[status] ?? DEFAULT_COLORS[status] ?? 'blue'
  const style = DEFAULT_STYLES[status] ?? DEFAULT_STYLES.unknown

  if (colorMap?.[status]) {
    return <Tag color={color}>{label ?? status}</Tag>
  }

  return (
    <Tag
      style={{
        backgroundColor: style.backgroundColor,
        borderColor: style.borderColor,
        color: style.color,
      }}
    >
      {label ?? status}
    </Tag>
  )
}
