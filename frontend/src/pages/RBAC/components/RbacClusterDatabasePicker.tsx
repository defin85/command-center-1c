import { useMemo, useState } from 'react'
import { Button, Modal, Space } from 'antd'

import type { ClusterRef, DatabaseRef } from '../../../api/queries/rbac'
import { RbacClusterDatabaseTree } from './RbacClusterDatabaseTree'

export function RbacClusterDatabasePicker(props: {
  mode: 'clusters' | 'databases'
  clusters: ClusterRef[]
  value?: string
  onChange?: (value: string | undefined) => void
  disabled?: boolean
  placeholder?: string
  width?: number
  databaseLabelById?: Map<string, string>
  onDatabasesLoaded?: (items: DatabaseRef[]) => void
}) {
  const [open, setOpen] = useState(false)

  const label = useMemo(() => {
    if (!props.value) return ''
    if (props.mode === 'clusters') {
      const cluster = props.clusters.find((c) => c.id === props.value)
      return cluster ? `${cluster.name} #${cluster.id}` : props.value
    }
    return props.databaseLabelById?.get(props.value) ?? props.value
  }, [props.value, props.mode, props.clusters, props.databaseLabelById])

  const placeholder = props.placeholder ?? (props.mode === 'clusters' ? 'Select cluster' : 'Select database')

  return (
    <>
      <Space.Compact>
        <Button
          style={{ width: props.width ?? 360, textAlign: 'left' }}
          disabled={props.disabled}
          onClick={() => setOpen(true)}
        >
          {props.value ? label : placeholder}
        </Button>
        <Button
          disabled={props.disabled || !props.value}
          onClick={() => props.onChange?.(undefined)}
        >
          Clear
        </Button>
      </Space.Compact>

      <Modal
        title={props.mode === 'clusters' ? 'Select cluster' : 'Select database'}
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={560}
      >
        <RbacClusterDatabaseTree
          mode={props.mode}
          clusters={props.clusters}
          value={props.value}
          onChange={(value) => {
            props.onChange?.(value)
            setOpen(false)
          }}
          width={520}
          height={520}
          onDatabasesLoaded={props.onDatabasesLoaded}
        />
      </Modal>
    </>
  )
}

