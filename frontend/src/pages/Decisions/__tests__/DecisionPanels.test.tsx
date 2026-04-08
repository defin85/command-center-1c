import { App as AntApp } from 'antd'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockTrackUiAction } = vi.hoisted(() => ({
  mockTrackUiAction: vi.fn((_: unknown, handler?: () => unknown) => handler?.()),
}))

vi.mock('../../../observability/uiActionJournal', () => ({
  trackUiAction: mockTrackUiAction,
}))

vi.mock('../DocumentPolicyBuilderEditor', () => ({
  DocumentPolicyBuilderEditor: () => <div>Builder editor</div>,
}))

vi.mock('../../../components/code/LazyJsonCodeEditor', () => ({
  LazyJsonCodeEditorFormField: () => <div>JSON editor</div>,
}))

import { DecisionEditorPanel, type DecisionEditorState } from '../DecisionEditorPanel'
import { DecisionLegacyImportPanel } from '../DecisionLegacyImportPanel'

describe('decision drawer panels', () => {
  beforeEach(() => {
    mockTrackUiAction.mockClear()
  })

  it('tracks semantic save action from the canonical decision editor drawer', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    const value: DecisionEditorState = {
      mode: 'rollover',
      activeTab: 'builder',
      decisionTableId: 'decision.policy',
      name: 'Services publication',
      description: 'Rollover the selected revision.',
      chains: [],
      rawJson: '{}',
      isActive: true,
      parentVersionId: 'decision-r7',
    }

    render(
      <AntApp>
        <DecisionEditorPanel
          value={value}
          saving={false}
          onCancel={vi.fn()}
          onChange={vi.fn()}
          onSave={onSave}
          onTabChange={vi.fn()}
        />
      </AntApp>,
    )

    await user.click(screen.getByRole('button', { name: 'Publish rollover revision' }))

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'drawer.submit',
        actionName: 'Publish rollover revision',
      }),
      expect.any(Function),
    )
    expect(onSave).toHaveBeenCalledTimes(1)
  })

  it('tracks semantic import action from the canonical legacy import drawer', async () => {
    const user = userEvent.setup()
    const onImport = vi.fn()

    render(
      <AntApp>
        <DecisionLegacyImportPanel
          error={null}
          graph={{
            pool_id: 'pool-1',
            date: '2026-04-08',
            version: 'snapshot-1',
            nodes: [
              {
                node_version_id: 'parent-node',
                organization_id: 'org-1',
                inn: '7300000000',
                name: 'Parent node',
                is_root: true,
                metadata: {},
              },
              {
                node_version_id: 'child-node',
                organization_id: 'org-2',
                inn: '7300000001',
                name: 'Child node',
                is_root: false,
                metadata: {},
              },
            ],
            edges: [
              {
                edge_version_id: 'edge-1',
                parent_node_version_id: 'parent-node',
                child_node_version_id: 'child-node',
                weight: '1.0',
                min_amount: null,
                max_amount: null,
                metadata: {
                  document_policy: {
                    mode: 'legacy',
                  },
                },
              },
            ],
          }}
          graphLoading={false}
          onOpenRawImport={vi.fn()}
          pools={[{
            id: 'pool-1',
            code: 'POOL',
            name: 'Pool',
            description: '',
            is_active: true,
            metadata: {},
            updated_at: '2026-04-08T12:00:00Z',
          }]}
          poolsLoading={false}
          saving={false}
          value={{
            poolId: 'pool-1',
            edgeVersionId: 'edge-1',
            decisionTableId: 'decision.policy',
            name: 'Imported policy',
            description: 'Imported from legacy edge.',
          }}
          onCancel={vi.fn()}
          onChange={vi.fn()}
          onImport={onImport}
        />
      </AntApp>,
    )

    await user.click(screen.getByRole('button', { name: 'Import to /decisions' }))

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'drawer.submit',
        actionName: 'Import to /decisions',
      }),
      expect.any(Function),
    )
    expect(onImport).toHaveBeenCalledTimes(1)
  })
})
