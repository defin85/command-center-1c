import { Button, Result } from 'antd'
import { useNavigate } from 'react-router-dom'

export function ForbiddenPage() {
  const navigate = useNavigate()

  return (
    <Result
      status="403"
      title="Нет доступа"
      subTitle="У вас нет прав для просмотра этой страницы."
      extra={[
        <Button type="primary" key="home" onClick={() => navigate('/')}>
          На главную
        </Button>,
        <Button key="back" onClick={() => navigate(-1)}>
          Назад
        </Button>,
      ]}
    />
  )
}
