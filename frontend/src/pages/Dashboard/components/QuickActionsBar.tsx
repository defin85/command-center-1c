/**
 * Quick actions bar component for Dashboard.
 *
 * Provides quick access to common operations.
 */

import { Space, Button } from 'antd'
import {
  PlusOutlined,
  UnorderedListOutlined,
  DashboardOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

export interface QuickActionsBarProps {
  onNewOperation: () => void
}

/**
 * QuickActionsBar - Action buttons for dashboard
 */
export const QuickActionsBar = ({ onNewOperation }: QuickActionsBarProps) => {
  const navigate = useNavigate()

  return (
    <Space>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={onNewOperation}
      >
        New Operation
      </Button>
      <Button
        icon={<UnorderedListOutlined />}
        onClick={() => navigate('/operations')}
      >
        View All Operations
      </Button>
      <Button
        icon={<DashboardOutlined />}
        onClick={() => navigate('/system-status')}
      >
        System Status
      </Button>
    </Space>
  )
}
