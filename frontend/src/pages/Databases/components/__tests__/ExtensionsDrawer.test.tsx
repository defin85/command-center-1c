import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { App } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ExtensionsDrawer } from '../ExtensionsDrawer'

describe('ExtensionsDrawer', () => {
  it('renders manual operations controls and snapshot payload', async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <App>
          <ExtensionsDrawer
            open={true}
            databaseId="db-1"
            databaseName="db-1"
            onClose={() => {}}
            onRefreshSnapshot={() => {}}
            snapshot={{
              database_id: 'db-1',
              snapshot: { extensions: [] },
              updated_at: '2026-01-01T00:00:00Z',
              source_operation_id: 'op-1',
            }}
          />
        </App>
      </QueryClientProvider>
    )

    expect(screen.getByText('Extensions: db-1')).toBeInTheDocument()
    expect(screen.getByText('Manual Operations')).toBeInTheDocument()
    expect(screen.getByText(/"extensions"/)).toBeInTheDocument()
  })
})
