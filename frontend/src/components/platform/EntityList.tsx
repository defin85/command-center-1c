import { ProCard } from '@ant-design/pro-components'
import { List, Spin } from 'antd'
import type { ListProps } from 'antd'
import type { ReactNode } from 'react'

import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'

type EntityListProps<T> = {
  title: ReactNode
  extra?: ReactNode
  toolbar?: ReactNode
  error?: string | null
  loading?: boolean
  emptyDescription?: ReactNode
  dataSource: T[]
  renderItem: NonNullable<ListProps<T>['renderItem']>
  size?: ListProps<T>['size']
}

export function EntityList<T>({
  title,
  extra,
  toolbar,
  error,
  loading = false,
  emptyDescription,
  dataSource,
  renderItem,
  size = 'small',
}: EntityListProps<T>) {
  return (
    <ProCard title={title} extra={extra}>
      {toolbar}
      {error ? (
        <ErrorState message={error} />
      ) : loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
          <Spin />
        </div>
      ) : dataSource.length === 0 ? (
        <EmptyState description={emptyDescription} />
      ) : (
        <List
          size={size}
          dataSource={dataSource}
          renderItem={renderItem}
        />
      )}
    </ProCard>
  )
}
