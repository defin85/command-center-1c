import { Space, Typography } from 'antd'
import type { ReactNode } from 'react'

const { Title, Text } = Typography

type PageHeaderProps = {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 16,
      }}
    >
      <Space direction="vertical" size={4}>
        <Title level={2} style={{ marginBottom: 0 }}>
          {title}
        </Title>
        {subtitle ? <Text type="secondary">{subtitle}</Text> : null}
      </Space>
      {actions ? <div>{actions}</div> : null}
    </div>
  )
}
