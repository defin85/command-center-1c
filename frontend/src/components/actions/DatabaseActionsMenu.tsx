import React from 'react';
import { Dropdown, Button } from 'antd';
import type { MenuProps } from 'antd';
import {
  LockOutlined,
  UnlockOutlined,
  StopOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MoreOutlined,
  EllipsisOutlined,
} from '@ant-design/icons';
import { RAS_OPERATIONS, type RASOperationKey } from './constants';

export type DatabaseActionKey = RASOperationKey | 'more';

export interface DatabaseActionsMenuProps {
  databaseId?: string;
  databaseStatus?: string;
  onAction: (action: DatabaseActionKey) => void;
  disabled?: boolean;
}

const icons: Record<string, React.ReactNode> = {
  lock_scheduled_jobs: <LockOutlined />,
  unlock_scheduled_jobs: <UnlockOutlined />,
  block_sessions: <StopOutlined />,
  unblock_sessions: <CheckCircleOutlined />,
  terminate_sessions: <CloseCircleOutlined />,
};

const menuItems: MenuProps['items'] = [
  ...Object.values(RAS_OPERATIONS).map((op) => ({
    key: op.key,
    icon: icons[op.key],
    label: op.label,
    danger: op.danger,
  })),
  { type: 'divider' as const },
  { key: 'more', icon: <MoreOutlined />, label: 'More Operations\u2026' },
];

export const DatabaseActionsMenu: React.FC<DatabaseActionsMenuProps> = ({
  databaseId: _databaseId,
  databaseStatus,
  onAction,
  disabled = false,
}) => {
  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    onAction(key as DatabaseActionKey);
  };

  const isDisabled = disabled || Boolean(databaseStatus && databaseStatus !== 'active');

  return (
    <Dropdown
      menu={{ items: menuItems, onClick: handleMenuClick }}
      trigger={['click']}
      disabled={isDisabled}
    >
      <Button icon={<EllipsisOutlined />} size="small" aria-label="Database actions" />
    </Dropdown>
  );
};

export default DatabaseActionsMenu;
