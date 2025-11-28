import { Component, ErrorInfo, ReactNode } from 'react'
import { Result, Button, Typography, Space } from 'antd'
import { BugOutlined, ReloadOutlined, HomeOutlined } from '@ant-design/icons'

const { Text, Paragraph } = Typography

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

/**
 * Error Boundary component for catching React rendering errors.
 *
 * Usage:
 * ```tsx
 * <ErrorBoundary>
 *   <YourComponent />
 * </ErrorBoundary>
 * ```
 *
 * Or with custom fallback:
 * ```tsx
 * <ErrorBoundary fallback={<CustomErrorUI />}>
 *   <YourComponent />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error to console in development
    console.error('ErrorBoundary caught an error:', error, errorInfo)

    this.setState({ errorInfo })

    // TODO: Send error to monitoring service (Sentry, LogRocket, etc.)
    // Example: Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } })
  }

  handleReload = () => {
    window.location.reload()
  }

  handleGoHome = () => {
    window.location.href = '/'
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError) {
      // Custom fallback provided
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default error UI
      const isDev = import.meta.env.DEV

      return (
        <Result
          status="error"
          icon={<BugOutlined />}
          title="Произошла ошибка"
          subTitle="Что-то пошло не так при отображении этой страницы."
          extra={
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space>
                <Button type="primary" icon={<ReloadOutlined />} onClick={this.handleReload}>
                  Перезагрузить страницу
                </Button>
                <Button icon={<HomeOutlined />} onClick={this.handleGoHome}>
                  На главную
                </Button>
                <Button onClick={this.handleRetry}>
                  Попробовать снова
                </Button>
              </Space>

              {isDev && this.state.error && (
                <div style={{
                  textAlign: 'left',
                  background: '#fff1f0',
                  border: '1px solid #ffa39e',
                  borderRadius: 8,
                  padding: 16,
                  maxWidth: 800,
                  margin: '0 auto'
                }}>
                  <Text strong style={{ color: '#cf1322' }}>
                    {this.state.error.name}: {this.state.error.message}
                  </Text>
                  {this.state.errorInfo && (
                    <Paragraph
                      style={{
                        marginTop: 12,
                        fontSize: 12,
                        fontFamily: 'monospace',
                        whiteSpace: 'pre-wrap',
                        maxHeight: 300,
                        overflow: 'auto',
                        background: '#fff',
                        padding: 8,
                        borderRadius: 4,
                      }}
                    >
                      {this.state.errorInfo.componentStack}
                    </Paragraph>
                  )}
                </div>
              )}
            </Space>
          }
        />
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
