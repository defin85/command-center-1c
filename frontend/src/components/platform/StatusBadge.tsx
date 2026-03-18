import { Tag } from 'antd'

type StatusBadgeProps = {
  status: string
  colorMap?: Record<string, string>
}

const DEFAULT_COLORS: Record<string, string> = {
  active: 'green',
  compatible: 'green',
  published: 'green',
  deactivated: 'default',
  inactive: 'default',
  warning: 'gold',
  incompatible: 'volcano',
  error: 'red',
}

export function StatusBadge({ status, colorMap }: StatusBadgeProps) {
  const color = colorMap?.[status] ?? DEFAULT_COLORS[status] ?? 'blue'

  return <Tag color={color}>{status}</Tag>
}
