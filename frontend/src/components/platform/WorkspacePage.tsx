import { Space } from 'antd'
import type { ReactNode } from 'react'

type WorkspacePageProps = {
  header?: ReactNode
  children: ReactNode
}

export function WorkspacePage({ header, children }: WorkspacePageProps) {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {header}
      {children}
    </Space>
  )
}
