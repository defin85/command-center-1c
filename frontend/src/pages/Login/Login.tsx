import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, App } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import axios from 'axios'
import { getApiBaseUrl } from '../../api/baseUrl'
import { setAuthToken } from '../../api/client'
import { notifyAuthChanged } from '../../lib/authState'
import { resetQueryClient } from '../../lib/queryClient'

const { Title } = Typography

interface LoginForm {
    username: string
    password: string
}

export const Login = () => {
    const [loading, setLoading] = useState(false)
    const navigate = useNavigate()
    const { message } = App.useApp()

    const onFinish = async (values: LoginForm) => {
        setLoading(true)
        try {
            // Auth endpoint is public (no JWT required), uses /api/token
            // Extract base URL without /api/* suffix
            // Port 8180 - outside Windows reserved range (8013-8112)
            const baseUrl = getApiBaseUrl()
                .replace(/\/api\/v\d+\/?$/, '')
                .replace(/\/api\/?$/, '')
            const response = await axios.post(`${baseUrl}/api/token`, {
                username: values.username,
                password: values.password,
            })

            const { access, refresh } = response.data

            // Сохраняем токены
            localStorage.setItem('auth_token', access)
            localStorage.setItem('refresh_token', refresh)
            setAuthToken(access)
            resetQueryClient()
            notifyAuthChanged()

            message.success('Успешная авторизация!')

            // Перенаправляем на главную
            navigate('/')
        } catch (error: unknown) {
            console.error('Login error:', error)
            const status = (error as { response?: { status?: number } } | null)?.response?.status
            if (status === 401) {
                message.error('Неверный логин или пароль')
            } else {
                message.error('Ошибка авторизации')
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '100vh',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        }}>
            <Card style={{ width: 400, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
                <div style={{ textAlign: 'center', marginBottom: 24 }}>
                    <Title level={2} style={{ marginBottom: 8 }}>
                        CommandCenter1C
                    </Title>
                    <p style={{ color: '#666' }}>Вход в систему управления</p>
                </div>

                <Form
                    name="login"
                    initialValues={{ remember: true }}
                    onFinish={onFinish}
                    size="large"
                >
                    <Form.Item
                        name="username"
                        rules={[{ required: true, message: 'Введите имя пользователя' }]}
                    >
                        <Input
                            id="login-username"
                            prefix={<UserOutlined />}
                            placeholder="Имя пользователя"
                            aria-label="Имя пользователя"
                            autoComplete="username"
                            spellCheck={false}
                        />
                    </Form.Item>

                    <Form.Item
                        name="password"
                        rules={[{ required: true, message: 'Введите пароль' }]}
                    >
                        <Input.Password
                            id="login-password"
                            prefix={<LockOutlined />}
                            placeholder="Пароль"
                            aria-label="Пароль"
                            autoComplete="current-password"
                        />
                    </Form.Item>

                    <Form.Item>
                        <Button
                            type="primary"
                            htmlType="submit"
                            loading={loading}
                            block
                        >
                            Войти
                        </Button>
                    </Form.Item>
                </Form>

                <div style={{ textAlign: 'center', marginTop: 16, color: '#999', fontSize: 12 }}>
                    Для разработки: admin / p-123456
                </div>
            </Card>
        </div>
    )
}
