import { Empty } from 'antd'
import type { CSSProperties, ReactNode } from 'react'

type EmptyStateProps = {
  description?: ReactNode
  image?: ReactNode
  style?: CSSProperties
}

export function EmptyState({
  description = 'No data available.',
  image = Empty.PRESENTED_IMAGE_SIMPLE,
  style,
}: EmptyStateProps) {
  return (
    <Empty
      description={description}
      image={image}
      style={style}
    />
  )
}
