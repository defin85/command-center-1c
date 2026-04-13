import { Empty } from 'antd'
import type { CSSProperties, ReactNode } from 'react'
import { usePlatformTranslation } from '@/i18n'

type EmptyStateProps = {
  description?: ReactNode
  image?: ReactNode
  style?: CSSProperties
}

export function EmptyState({
  description,
  image = Empty.PRESENTED_IMAGE_SIMPLE,
  style,
}: EmptyStateProps) {
  const { t } = usePlatformTranslation()

  return (
    <Empty
      description={description ?? t(($) => $.emptyState.noDataAvailable)}
      image={image}
      style={style}
    />
  )
}
