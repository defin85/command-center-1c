import type { CSSProperties, ReactNode } from 'react'

import { PermissionsTable } from '../../components/PermissionsTable'
import type { PermissionsTableConfig, TableConfig } from './usePermissionsTableConfig'

type AnyRow = object

export function PermissionsAssignmentsTable(props: {
  title: string
  style?: CSSProperties
  preamble?: ReactNode
  toolbar?: ReactNode
  empty?: {
    show: boolean
    description: ReactNode
  }
  tableConfig: PermissionsTableConfig
  page: number
  pageSize: number
  onPaginationChange: (page: number, pageSize: number) => void
  errorMessage?: string
}) {
  const {
    title,
    style,
    preamble,
    toolbar,
    empty,
    tableConfig,
    page,
    pageSize,
    onPaginationChange,
    errorMessage,
  } = props

  function render<TKind extends string, TRow extends AnyRow>(config: TableConfig<TKind, TRow>) {
    return (
      <PermissionsTable<TRow>
        title={title}
        style={style}
        preamble={preamble}
        toolbar={toolbar}
        empty={empty}
        columns={config.columns}
        rows={config.rows}
        rowKey={config.rowKey}
        loading={config.loading}
        total={config.total}
        page={page}
        pageSize={pageSize}
        onPaginationChange={onPaginationChange}
        error={config.error}
        errorMessage={errorMessage}
      />
    )
  }

  switch (tableConfig.kind) {
    case 'clusters/user':
      return render(tableConfig)
    case 'clusters/role':
      return render(tableConfig)
    case 'databases/user':
      return render(tableConfig)
    case 'databases/role':
      return render(tableConfig)
    case 'operation-templates/user':
      return render(tableConfig)
    case 'operation-templates/role':
      return render(tableConfig)
    case 'workflow-templates/user':
      return render(tableConfig)
    case 'workflow-templates/role':
      return render(tableConfig)
    case 'artifacts/user':
      return render(tableConfig)
    case 'artifacts/role':
      return render(tableConfig)
  }
}
