import { ProCard } from '@ant-design/pro-components'
import { Spin } from 'antd'
import type { ReactNode } from 'react'

import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'

type EntityDetailsProps = {
  title: ReactNode
  extra?: ReactNode
  error?: string | null
  loading?: boolean
  empty?: boolean
  emptyDescription?: ReactNode
  children?: ReactNode
}

export function EntityDetails({
  title,
  extra,
  error,
  loading = false,
  empty = false,
  emptyDescription,
  children,
}: EntityDetailsProps) {
  return (
    <ProCard title={title} extra={extra} style={{ minWidth: 0 }}>
      {error ? (
        <ErrorState message={error} />
      ) : loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
          <Spin />
        </div>
      ) : empty ? (
        <EmptyState description={emptyDescription} />
      ) : (
        children
      )}
    </ProCard>
  )
}
