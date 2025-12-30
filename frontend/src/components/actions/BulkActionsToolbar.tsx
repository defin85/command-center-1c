import React from 'react';
import { Space, Button, Dropdown, Typography } from 'antd';
import type { MenuProps } from 'antd';
import { DownOutlined, ClearOutlined } from '@ant-design/icons';
import { RAS_OPERATIONS } from './constants';

export interface BulkActionsToolbarProps {
  selectedCount: number;
  onAction: (action: string) => void;
  onClearSelection: () => void;
  loading?: boolean;
  disabled?: boolean;
}

const bulkMenuItems: MenuProps['items'] = Object.values(RAS_OPERATIONS).map((op) => ({
  key: op.key,
  label: op.label,
  danger: op.danger,
}));

export const BulkActionsToolbar: React.FC<BulkActionsToolbarProps> = ({
  selectedCount,
  onAction,
  onClearSelection,
  loading = false,
  disabled = false,
}) => {
  if (selectedCount === 0) return null;
  const isDisabled = disabled || loading;

  return (
    <Space style={{ marginBottom: 16 }}>
      <Typography.Text strong>
        {selectedCount} database{selectedCount > 1 ? 's' : ''} selected
      </Typography.Text>

      <Dropdown
        menu={{
          items: bulkMenuItems,
          onClick: ({ key }) => onAction(key),
        }}
        disabled={isDisabled}
      >
        <Button type="primary" loading={loading} disabled={disabled}>
          Bulk Actions <DownOutlined />
        </Button>
      </Dropdown>

      <Button
        icon={<ClearOutlined />}
        onClick={onClearSelection}
        disabled={isDisabled}
      >
        Clear
      </Button>
    </Space>
  );
};

export default BulkActionsToolbar;
