import { useMemo } from 'react'
import { Button, Space, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ArrowDownOutlined, ArrowUpOutlined, CopyOutlined, DeleteOutlined, EditOutlined, EyeOutlined } from '@ant-design/icons'

import type { ActionRow } from '../actionCatalogTypes'

const { Text } = Typography

export type UseActionCatalogColumnsParams = {
  actionRowsLength: number
  actionsEditable: boolean
  saveErrorsByActionPos: Map<number, string[]>
  moveAction: (pos: number, delta: -1 | 1) => void
  openEditor: (opts: { mode: 'edit' | 'copy'; pos: number }) => void
  openPreview: (pos: number) => void
  disableAction: (pos: number) => void
}

export const useActionCatalogColumns = ({
  actionRowsLength,
  actionsEditable,
  saveErrorsByActionPos,
  moveAction,
  openEditor,
  openPreview,
  disableAction,
}: UseActionCatalogColumnsParams): ColumnsType<ActionRow> => {
  return useMemo(() => ([
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 260,
      render: (value: string, record) => {
        const errs = saveErrorsByActionPos.get(record.pos) ?? []
        if (errs.length === 0) return <Text code>{value}</Text>
        return (
          <Space size={6}>
            <Text code>{value}</Text>
            <Tooltip title={(
              <Space direction="vertical" size={0}>
                {errs.slice(0, 6).map((msg, idx) => (
                  <Text key={`${idx}:${msg}`}>{msg}</Text>
                ))}
                {errs.length > 6 && <Text type="secondary">… and {errs.length - 6} more</Text>}
              </Space>
            )}>
              <Tag color="red">ERR</Tag>
            </Tooltip>
          </Space>
        )
      },
    },
    {
      title: 'Capability',
      dataIndex: 'capability',
      key: 'capability',
      width: 200,
      render: (value?: string) => (value ? <Text code>{value}</Text> : '-'),
    },
    {
      title: 'Label',
      dataIndex: 'label',
      key: 'label',
      render: (value: string) => <Text>{value}</Text>,
    },
    {
      title: 'Contexts',
      dataIndex: 'contexts',
      key: 'contexts',
      width: 180,
      render: (value: string[]) => (
        <Space size={4} wrap>
          {value.map((ctx) => <Tag key={ctx}>{ctx}</Tag>)}
        </Space>
      ),
    },
    {
      title: 'Executor',
      dataIndex: 'executor_kind',
      key: 'executor_kind',
      width: 140,
      render: (value: string) => <Tag>{value || '-'}</Tag>,
    },
    {
      title: 'Ref',
      key: 'ref',
      width: 260,
      render: (_value, record) => {
        if (record.executor_kind === 'workflow') {
          return <Text code>{record.workflow_id || '-'}</Text>
        }
        if (record.executor_kind === 'ibcmd_cli' || record.executor_kind === 'designer_cli') {
          return <Text code>{`${record.driver || '-'} / ${record.command_id || '-'}`}</Text>
        }
        return '-'
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 230,
      render: (_value, record) => (
        <Space size={0}>
          <Button
            size="small"
            type="text"
            icon={<ArrowUpOutlined />}
            aria-label="Move up"
            onClick={() => moveAction(record.pos, -1)}
            disabled={!actionsEditable || record.pos === 0}
          />
          <Button
            size="small"
            type="text"
            icon={<ArrowDownOutlined />}
            aria-label="Move down"
            onClick={() => moveAction(record.pos, 1)}
            disabled={!actionsEditable || record.pos === actionRowsLength - 1}
          />
          <Button
            size="small"
            type="text"
            icon={<EditOutlined />}
            aria-label="Edit"
            onClick={() => openEditor({ mode: 'edit', pos: record.pos })}
            disabled={!actionsEditable}
          />
          <Button
            size="small"
            type="text"
            icon={<EyeOutlined />}
            aria-label="Preview"
            onClick={() => openPreview(record.pos)}
            disabled={!actionsEditable}
          />
          <Button
            size="small"
            type="text"
            icon={<CopyOutlined />}
            aria-label="Copy"
            onClick={() => openEditor({ mode: 'copy', pos: record.pos })}
            disabled={!actionsEditable}
          />
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            aria-label="Disable"
            onClick={() => disableAction(record.pos)}
            disabled={!actionsEditable}
          />
        </Space>
      ),
    },
  ]), [actionRowsLength, actionsEditable, disableAction, moveAction, openEditor, openPreview, saveErrorsByActionPos])
}
