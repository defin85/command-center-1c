import { Select } from 'antd'

import type { ClusterRef, DatabaseRef } from '../../../api/queries/rbac'
import { RbacClusterDatabasePicker } from './RbacClusterDatabasePicker'

type ResourceKey = 'clusters' | 'databases' | 'operation-templates' | 'workflow-templates' | 'artifacts'

type SelectOption = { label: string; value: string }

export type RbacResourceSelectConfig = {
  options: SelectOption[]
  loading?: boolean
  showSearch?: boolean
  filterOption?: boolean
  onSearch?: (value: string) => void
  onPopupScroll?: (event: any) => void
}

export function RbacResourcePicker(props: {
  resourceKey: ResourceKey
  clusters: ClusterRef[]
  value?: string
  onChange?: (value: string | undefined) => void
  disabled?: boolean
  allowClear?: boolean
  placeholder?: string
  width?: number
  databaseLabelById?: Map<string, string>
  onDatabasesLoaded?: (items: DatabaseRef[]) => void
  select?: RbacResourceSelectConfig
}) {
  const width = props.width ?? 360

  if (props.resourceKey === 'clusters') {
    return (
      <RbacClusterDatabasePicker
        mode="clusters"
        clusters={props.clusters}
        value={props.value}
        onChange={props.onChange}
        disabled={props.disabled}
        placeholder={props.placeholder ?? 'Cluster'}
        width={width}
      />
    )
  }

  if (props.resourceKey === 'databases') {
    return (
      <RbacClusterDatabasePicker
        mode="databases"
        clusters={props.clusters}
        value={props.value}
        onChange={props.onChange}
        disabled={props.disabled}
        placeholder={props.placeholder ?? 'Database'}
        width={width}
        databaseLabelById={props.databaseLabelById}
        onDatabasesLoaded={props.onDatabasesLoaded}
      />
    )
  }

  return (
    <Select
      style={{ width }}
      placeholder={props.placeholder ?? 'Resource'}
      allowClear={props.allowClear}
      disabled={props.disabled}
      value={props.value}
      onChange={(value) => props.onChange?.(typeof value === 'string' ? value : undefined)}
      showSearch={props.select?.showSearch ?? true}
      optionFilterProp="label"
      filterOption={props.select?.filterOption ?? false}
      onSearch={props.select?.filterOption ? undefined : props.select?.onSearch}
      onPopupScroll={props.select?.filterOption ? undefined : props.select?.onPopupScroll}
      options={props.select?.options ?? []}
      loading={props.select?.loading}
    />
  )
}

