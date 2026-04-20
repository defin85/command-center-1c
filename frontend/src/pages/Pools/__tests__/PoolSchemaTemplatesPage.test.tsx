import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { App as AntApp } from 'antd'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'

import { changeLanguage, ensureNamespaces } from '../../../i18n/runtime'
import { PoolSchemaTemplatesPage } from '../PoolSchemaTemplatesPage'

const mockListPoolSchemaTemplates = vi.fn()
const mockCreatePoolSchemaTemplate = vi.fn()
const mockUpdatePoolSchemaTemplate = vi.fn()

vi.mock('../../../api/intercompanyPools', () => ({
  listPoolSchemaTemplates: (...args: unknown[]) => mockListPoolSchemaTemplates(...args),
  createPoolSchemaTemplate: (...args: unknown[]) => mockCreatePoolSchemaTemplate(...args),
  updatePoolSchemaTemplate: (...args: unknown[]) => mockUpdatePoolSchemaTemplate(...args),
}))

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd')
  const { createPoolSchemaTemplatesAntdTestDouble } = await import('./poolSchemaTemplatesAntdTestDouble')
  return createPoolSchemaTemplatesAntdTestDouble(actual)
})

vi.mock('../../../components/platform', async () => {
  const actual = await vi.importActual<typeof import('../../../components/platform')>(
    '../../../components/platform'
  )

  return {
    ...actual,
    WorkspacePage: ({ header, children }: { header?: ReactNode; children: ReactNode }) => (
      <div>
        {header}
        {children}
      </div>
    ),
    PageHeader: ({
      title,
      subtitle,
      actions,
    }: {
      title: ReactNode
      subtitle?: ReactNode
      actions?: ReactNode
    }) => (
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
        {actions}
      </div>
    ),
    MasterDetailShell: ({
      list,
      detail,
      detailOpen,
      detailDrawerTitle,
      onCloseDetail,
    }: {
      list: ReactNode
      detail: ReactNode
      detailOpen?: boolean
      detailDrawerTitle?: ReactNode
      onCloseDetail?: () => void
    }) => (
      <div>
        <section>{list}</section>
        <section data-detail-open={detailOpen ? 'true' : 'false'}>
          {detailDrawerTitle ? <h2>{detailDrawerTitle}</h2> : null}
          {detailOpen && onCloseDetail ? (
            <button type="button" onClick={onCloseDetail}>
              Close detail
            </button>
          ) : null}
          {detail}
        </section>
      </div>
    ),
    EntityList: ({
      title,
      extra,
      toolbar,
      error,
      loading,
      emptyDescription,
      dataSource,
      renderItem,
    }: {
      title?: ReactNode
      extra?: ReactNode
      toolbar?: ReactNode
      error?: ReactNode
      loading?: boolean
      emptyDescription?: ReactNode
      dataSource?: Array<Record<string, unknown>>
      renderItem: (item: Record<string, unknown>) => ReactNode
    }) => (
      <section>
        {title ? <h3>{title}</h3> : null}
        {extra}
        {toolbar}
        {error ? error : loading ? <div>Loading</div> : (dataSource?.length ?? 0) === 0 ? <div>{emptyDescription}</div> : (
          (dataSource ?? []).map((item, index) => (
            <div key={String(item.id ?? index)}>
              {renderItem(item)}
            </div>
          ))
        )}
      </section>
    ),
    EntityDetails: ({
      title,
      extra,
      error,
      loading,
      empty,
      emptyDescription,
      children,
    }: {
      title?: ReactNode
      extra?: ReactNode
      error?: ReactNode
      loading?: boolean
      empty?: boolean
      emptyDescription?: ReactNode
      children?: ReactNode
    }) => (
      <section>
        {title ? <h3>{title}</h3> : null}
        {extra}
        {error ? error : loading ? <div>Loading</div> : empty ? emptyDescription : children}
      </section>
    ),
    ModalFormShell: ({
      open,
      title,
      onClose,
      onSubmit,
      submitText,
      confirmLoading,
      children,
    }: {
      open: boolean
      title?: ReactNode
      onClose?: () => void
      onSubmit?: () => void
      submitText?: ReactNode
      confirmLoading?: boolean
      children?: ReactNode
    }) => (
      open ? (
        <section role="dialog" aria-label={typeof title === 'string' ? title : undefined}>
          {title ? <h2>{title}</h2> : null}
          {children}
          {onClose ? (
            <button type="button" onClick={onClose}>
              Close
            </button>
          ) : null}
          {onSubmit ? (
            <button type="button" disabled={confirmLoading} onClick={onSubmit}>
              {submitText ?? 'Save'}
            </button>
          ) : null}
        </section>
      ) : null
    ),
    JsonBlock: ({ title, value }: { title?: ReactNode; value: unknown }) => (
      <section>
        {title ? <h4>{title}</h4> : null}
        <pre>{JSON.stringify(value, null, 2)}</pre>
      </section>
    ),
  }
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/pools/templates']}>
      <AntApp>
        <PoolSchemaTemplatesPage />
      </AntApp>
    </MemoryRouter>
  )
}

describe('PoolSchemaTemplatesPage', () => {
  beforeAll(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'pools')
  })

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

  afterAll(async () => {
    await ensureNamespaces('ru', 'pools')
    await changeLanguage('ru')
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
    mockUpdatePoolSchemaTemplate.mockResolvedValue({
      id: '11111111-1111-1111-1111-111111111111',
    })

    renderPage()

    const editButton = await screen.findByRole('button', { name: 'Edit' })
    fireEvent.click(editButton)

    const modal = await screen.findByRole('dialog', { name: 'Edit Pool Schema Template' })
    const saveButton = within(modal).getByRole('button', { name: 'Save' })
    fireEvent.click(saveButton)

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

  it('blocks submit on invalid schema JSON and preserves input', async () => {
    renderPage()

    const createButton = await screen.findByRole('button', { name: 'Create Template' })
    fireEvent.click(createButton)

    const modal = await screen.findByRole('dialog', { name: 'Create Pool Schema Template' })
    fireEvent.change(within(modal).getByLabelText('Code'), { target: { value: 'json-invalid-v1' } })
    fireEvent.change(within(modal).getByLabelText('Name'), { target: { value: 'Invalid JSON Template' } })

    const schemaInput = within(modal).getByLabelText('Schema JSON') as HTMLTextAreaElement
    fireEvent.change(schemaInput, { target: { value: '{invalid-json' } })

    fireEvent.click(within(modal).getByRole('button', { name: 'Create' }))

    expect(await within(modal).findByText('Schema: invalid JSON')).toBeInTheDocument()
    expect(mockCreatePoolSchemaTemplate).not.toHaveBeenCalled()
    expect(schemaInput.value).toBe('{invalid-json')
  })
})
