import { describe, expect, it, vi } from 'vitest'
import { App as AntApp, Form, Input } from 'antd'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import * as React from 'react'

import {
  DashboardPage,
  DrawerSurfaceShell,
  DrawerFormShell,
  EntityList,
  MasterDetailShell,
  ModalFormShell,
  ModalSurfaceShell,
  PageHeader,
  RouteButton,
  StatusBadge,
} from '..'

function RouteLocationProbe() {
  const location = useLocation()
  return <div data-testid="route-location">{`${location.pathname}${location.search}`}</div>
}

describe('platform primitives', () => {
  it('renders EntityList as the canonical list pattern', () => {
    render(
      <AntApp>
        <EntityList
          title="Catalog"
          dataSource={[{ id: 'decision-1', name: 'Services publication policy' }]}
          renderItem={(item) => <div>{item.name}</div>}
        />
      </AntApp>
    )

    expect(screen.getByText('Catalog')).toBeInTheDocument()
    expect(screen.getByText('Services publication policy')).toBeInTheDocument()
  })

  it('renders ModalFormShell as the canonical modal authoring pattern', () => {
    render(
      <AntApp>
        <ModalFormShell
          open
          onClose={vi.fn()}
          onSubmit={vi.fn()}
          title="Create reusable profile"
          submitText="Create profile"
        >
          <label htmlFor="profile-code">Profile code</label>
          <Input id="profile-code" />
        </ModalFormShell>
      </AntApp>
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByLabelText('Profile code')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create profile' })).toBeInTheDocument()
  })

  it('keeps closed ModalFormShell form instances connected without console warnings when forceRender is enabled', () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    function ClosedModalHarness() {
      const [form] = Form.useForm()

      return (
        <AntApp>
          <ModalFormShell
            open={false}
            onClose={vi.fn()}
            onSubmit={vi.fn()}
            title="Hidden editor"
            forceRender
          >
            <Form form={form} layout="vertical">
              <Form.Item label="Profile code" name="code">
                <Input />
              </Form.Item>
            </Form>
          </ModalFormShell>
        </AntApp>
      )
    }

    render(<ClosedModalHarness />)

    expect(
      consoleErrorSpy.mock.calls.some(([message]) => String(message).includes('useForm')),
    ).toBe(false)

    consoleErrorSpy.mockRestore()
  })

  it('renders DrawerFormShell content after dynamic open transitions', async () => {
    const user = userEvent.setup()

    function DrawerHarness() {
      const [open, setOpen] = React.useState(false)

      return (
        <AntApp>
          <button type="button" onClick={() => setOpen(true)}>
            Open drawer
          </button>
          <DrawerFormShell
            open={open}
            onClose={() => setOpen(false)}
            title="Attachment workspace"
            drawerTestId="platform-drawer-shell"
          >
            <label htmlFor="drawer-field">Drawer field</label>
            <Input id="drawer-field" />
          </DrawerFormShell>
        </AntApp>
      )
    }

    render(<DrawerHarness />)

    await user.click(screen.getByRole('button', { name: 'Open drawer' }))

    expect(await screen.findByTestId('platform-drawer-shell')).toBeInTheDocument()
    expect(screen.getByLabelText('Drawer field')).toBeInTheDocument()
  })

  it('renders DrawerFormShell header actions through the canonical extra slot', () => {
    render(
      <AntApp>
        <DrawerFormShell
          open
          onClose={vi.fn()}
          title="Attachment workspace"
          extra={<button type="button">Header action</button>}
        >
          <div>Drawer body</div>
        </DrawerFormShell>
      </AntApp>,
    )

    expect(screen.getByRole('button', { name: 'Header action' })).toBeInTheDocument()
    expect(screen.getByText('Drawer body')).toBeInTheDocument()
  })

  it('renders DrawerSurfaceShell as the canonical non-form drawer surface', async () => {
    const user = userEvent.setup()

    function DrawerSurfaceHarness() {
      const [open, setOpen] = React.useState(false)

      return (
        <AntApp>
          <button type="button" onClick={() => setOpen(true)}>
            Open inspect drawer
          </button>
          <DrawerSurfaceShell
            open={open}
            onClose={() => setOpen(false)}
            title="Inspect surface"
            drawerTestId="platform-drawer-surface"
          >
            <div>Inspect content</div>
          </DrawerSurfaceShell>
        </AntApp>
      )
    }

    render(<DrawerSurfaceHarness />)

    await user.click(screen.getByRole('button', { name: 'Open inspect drawer' }))

    expect(await screen.findByTestId('platform-drawer-surface')).toBeInTheDocument()
    expect(screen.getByText('Inspect content')).toBeInTheDocument()
  })

  it('renders ModalSurfaceShell as the canonical non-form modal surface', () => {
    render(
      <AntApp>
        <ModalSurfaceShell
          open
          onClose={vi.fn()}
          onSubmit={vi.fn()}
          title="Review remediation"
          submitText="Retry"
        >
          <div>Remediation content</div>
        </ModalSurfaceShell>
      </AntApp>,
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Remediation content')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('degrades MasterDetailShell into list plus Drawer on narrow viewport', async () => {
    const originalInnerWidth = window.innerWidth
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 480,
    })

    try {
      render(
        <AntApp>
          <MasterDetailShell
            list={<div>Compact list</div>}
            detail={<div>Review detail</div>}
            detailOpen
            detailDrawerTitle="Factual review detail"
          />
        </AntApp>,
      )

      expect(screen.getByText('Compact list')).toBeInTheDocument()
      expect(await screen.findByText('Factual review detail')).toBeInTheDocument()
      expect(screen.getByText('Review detail')).toBeInTheDocument()
    } finally {
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        value: originalInnerWidth,
      })
    }
  })

  it('renders DashboardPage as the canonical dashboard shell', () => {
    render(
      <AntApp>
        <DashboardPage header={<PageHeader title="Dashboard" subtitle="Last updated: now" />}>
          <div>Cluster overview</div>
        </DashboardPage>
      </AntApp>
    )

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Last updated: now')).toBeInTheDocument()
    expect(screen.getByText('Cluster overview')).toBeInTheDocument()
  })

  it('renders RouteButton as a shell-safe internal navigation primitive', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/source']}>
        <AntApp>
          <RouteButton to="/target?tab=details">Open target</RouteButton>
          <RouteLocationProbe />
        </AntApp>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Open target' }))

    expect(screen.getByTestId('route-location')).toHaveTextContent('/target?tab=details')
  })

  it('renders deactivated badges with contrast-safe neutral styling', () => {
    render(
      <AntApp>
        <StatusBadge status="deactivated" />
      </AntApp>,
    )

    expect(screen.getByText('deactivated')).toHaveStyle({
      backgroundColor: '#f3f4f6',
      borderColor: '#d1d5db',
      color: '#374151',
    })
  })
})
