import { Space, Typography } from 'antd'
import type { CSSProperties, ReactNode } from 'react'

const { Text, Paragraph } = Typography

type JsonBlockProps = {
  title: ReactNode
  value: unknown
  height?: number
  dataTestId?: string
  emptyLabel?: string
  style?: CSSProperties
}

const formatValue = (value: unknown) => {
  if (typeof value === 'string') {
    return value.trim() ? value : '{}'
  }

  return JSON.stringify(value ?? {}, null, 2)
}

export function JsonBlock({
  title,
  value,
  height = 220,
  dataTestId,
  emptyLabel = '{}',
  style,
}: JsonBlockProps) {
  const formatted = formatValue(value)

  return (
    <Space direction="vertical" size={8} style={{ width: '100%', ...style }}>
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <Text strong>{title}</Text>
        <Paragraph copyable={{ text: formatted }} style={{ marginBottom: 0 }}>
          <Text type="secondary">Copy JSON</Text>
        </Paragraph>
      </Space>
      <pre
        data-testid={dataTestId}
        style={{
          margin: 0,
          padding: 12,
          minHeight: 80,
          maxHeight: height,
          overflow: 'auto',
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          background: '#fafafa',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontSize: 12,
          lineHeight: 1.5,
        }}
      >
        {formatted || emptyLabel}
      </pre>
    </Space>
  )
}
