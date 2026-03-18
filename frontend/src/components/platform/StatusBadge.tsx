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

export function StatusBadge({ status, label, colorMap }: StatusBadgeProps) {
  const color = colorMap?.[status] ?? DEFAULT_COLORS[status] ?? 'blue'

  return <Tag color={color}>{label ?? status}</Tag>
}
