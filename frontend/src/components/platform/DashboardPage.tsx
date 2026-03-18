import { Space } from 'antd'
import type { ReactNode } from 'react'

import { WorkspacePage } from './WorkspacePage'

type DashboardPageProps = {
  header?: ReactNode
  children: ReactNode
}

export function DashboardPage({ header, children }: DashboardPageProps) {
  return (
    <WorkspacePage header={header}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {children}
      </Space>
    </WorkspacePage>
  )
}
