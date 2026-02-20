import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

import { PoolSchemaTemplatesPage } from '../PoolSchemaTemplatesPage'

const mockListPoolSchemaTemplates = vi.fn()
const mockCreatePoolSchemaTemplate = vi.fn()
const mockUpdatePoolSchemaTemplate = vi.fn()

vi.mock('../../../api/intercompanyPools', () => ({
  listPoolSchemaTemplates: (...args: unknown[]) => mockListPoolSchemaTemplates(...args),
  createPoolSchemaTemplate: (...args: unknown[]) => mockCreatePoolSchemaTemplate(...args),
  updatePoolSchemaTemplate: (...args: unknown[]) => mockUpdatePoolSchemaTemplate(...args),
}))

function renderPage() {
  return render(
    <AntApp>
      <PoolSchemaTemplatesPage />
    </AntApp>
  )
}

describe('PoolSchemaTemplatesPage', () => {
  beforeEach(() => {
    mockListPoolSchemaTemplates.mockReset()
    mockCreatePoolSchemaTemplate.mockReset()
    mockUpdatePoolSchemaTemplate.mockReset()
    mockListPoolSchemaTemplates.mockResolvedValue([
      {
        id: '11111111-1111-1111-1111-111111111111',
        tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        code: 'xlsx-bottomup-v1',
        name: 'Bottom-up v1',
        format: 'xlsx',
        is_public: true,
        is_active: true,
        schema: {},
        metadata: {
          workflow_binding: {
            workflow_template_id: 'wf-legacy-1',
            version: 'v2',
          },
        },
        workflow_template_id: '22222222-2222-2222-2222-222222222222',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:01Z',
      },
    ])
  })

  it('shows workflow_binding as compatibility compiler hint', async () => {
    renderPage()

    expect(await screen.findByTestId('pool-template-workflow-binding-hint')).toHaveTextContent('wf-legacy-1')
    expect(screen.getByText('compat')).toBeInTheDocument()
    expect(screen.getByText(/Unified execution source-of-truth/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(mockListPoolSchemaTemplates).toHaveBeenCalledWith({
        format: undefined,
        isPublic: true,
        isActive: true,
      })
    })
  })

  it('updates template from edit modal', async () => {
    const user = userEvent.setup()
    mockUpdatePoolSchemaTemplate.mockResolvedValue({
      id: '11111111-1111-1111-1111-111111111111',
    })

    renderPage()

    const editButton = await screen.findByRole('button', { name: 'Edit' })
    await user.click(editButton)

    const modal = await screen.findByRole('dialog', { name: 'Edit Pool Schema Template' })
    const saveButton = within(modal).getByRole('button', { name: 'Save' })
    await user.click(saveButton)

    await waitFor(() => {
      expect(mockUpdatePoolSchemaTemplate).toHaveBeenCalledWith(
        '11111111-1111-1111-1111-111111111111',
        expect.objectContaining({
          code: 'xlsx-bottomup-v1',
          name: 'Bottom-up v1',
          format: 'xlsx',
          workflow_template_id: '22222222-2222-2222-2222-222222222222',
        })
      )
    })
  })
})
