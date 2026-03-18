import { Alert } from 'antd'
import type { ReactNode } from 'react'

type ErrorStateProps = {
  message: ReactNode
  description?: ReactNode
  action?: ReactNode
  type?: 'error' | 'warning'
}

export function ErrorState({
  message,
  description,
  action,
  type = 'error',
}: ErrorStateProps) {
  return (
    <Alert
      type={type}
      showIcon
      message={message}
      description={description}
      action={action}
    />
  )
}
