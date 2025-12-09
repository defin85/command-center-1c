import type { MenuProps } from 'antd';

/**
 * RAS Operation configuration
 */
export interface RASOperationConfig {
  key: string;
  label: string;
  description: string;
  icon: string;
  danger?: boolean;
  requiresConfig?: boolean;
}

export const RAS_OPERATIONS: Record<string, RASOperationConfig> = {
  lock_scheduled_jobs: {
    key: 'lock_scheduled_jobs',
    label: 'Lock Scheduled Jobs',
    description: 'Scheduled jobs will be blocked from running.',
    icon: 'LockOutlined',
  },
  unlock_scheduled_jobs: {
    key: 'unlock_scheduled_jobs',
    label: 'Unlock Scheduled Jobs',
    description: 'Scheduled jobs will be allowed to run.',
    icon: 'UnlockOutlined',
  },
  block_sessions: {
    key: 'block_sessions',
    label: 'Block Sessions',
    description: 'New user connections will be blocked.',
    icon: 'StopOutlined',
    requiresConfig: true,
  },
  unblock_sessions: {
    key: 'unblock_sessions',
    label: 'Unblock Sessions',
    description: 'New user connections will be allowed.',
    icon: 'CheckCircleOutlined',
  },
  terminate_sessions: {
    key: 'terminate_sessions',
    label: 'Terminate Sessions',
    description: 'All active user sessions will be disconnected immediately!',
    icon: 'CloseCircleOutlined',
    danger: true,
  },
} as const;

export type RASOperationKey = keyof typeof RAS_OPERATIONS;

/**
 * Generate menu items for Ant Design Dropdown
 */
export const generateRASMenuItems = (
  keys: RASOperationKey[],
  icons?: Record<string, React.ReactNode>
): MenuProps['items'] => {
  return keys.map((key) => {
    const config = RAS_OPERATIONS[key];
    return {
      key,
      label: config.label,
      danger: config.danger,
      icon: icons?.[key],
    };
  });
};

/**
 * Get operation config by key
 */
export const getOperationConfig = (key: string): RASOperationConfig | undefined => {
  return RAS_OPERATIONS[key as RASOperationKey];
};
