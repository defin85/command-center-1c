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
import { useDashboardTranslation } from '../../../i18n'

export interface QuickActionsBarProps {
  onNewOperation: () => void
}

/**
 * QuickActionsBar - Action buttons for dashboard
 */
export const QuickActionsBar = ({ onNewOperation }: QuickActionsBarProps) => {
  const navigate = useNavigate()
  const { t } = useDashboardTranslation()

  return (
    <Space>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={onNewOperation}
      >
        {t(($) => $.quickActions.newOperation)}
      </Button>
      <Button
        icon={<UnorderedListOutlined />}
        onClick={() => navigate('/operations')}
      >
        {t(($) => $.quickActions.viewAllOperations)}
      </Button>
      <Button
        icon={<DashboardOutlined />}
        onClick={() => navigate('/system-status')}
      >
        {t(($) => $.quickActions.systemStatus)}
      </Button>
    </Space>
  )
}
