import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExtensionsDrawer } from '../ExtensionsDrawer'
import type { ActionCatalogAction } from '../../../../api/types/actionCatalog'

describe('ExtensionsDrawer', () => {
  it('renders actions and runs selected action', async () => {
    const user = userEvent.setup()
    const onRunAction = vi.fn().mockResolvedValue(undefined)

    const actions: ActionCatalogAction[] = [
      {
        id: 'extensions.list',
        label: 'List extensions',
        contexts: ['database_card'],
        executor: { kind: 'ibcmd_cli', driver: 'ibcmd', command_id: 'infobase.extension.list' },
      },
    ]

    render(
      <ExtensionsDrawer
        open={true}
        databaseName="db-1"
        actions={actions}
        onClose={() => {}}
        onRunAction={onRunAction}
        onRefreshSnapshot={() => {}}
        snapshot={{
          database_id: 'db-1',
          snapshot: { extensions: [] },
          updated_at: '2026-01-01T00:00:00Z',
          source_operation_id: 'op-1',
        }}
      />
    )

    expect(screen.getByText('Extensions: db-1')).toBeInTheDocument()
    expect(screen.getByText('List extensions')).toBeInTheDocument()
    expect(screen.getByText(/extensions\.list/)).toBeInTheDocument()
    expect(screen.getByText(/"extensions"/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Run' }))
    expect(onRunAction).toHaveBeenCalledTimes(1)
    expect(onRunAction).toHaveBeenCalledWith(actions[0])
  })
})
