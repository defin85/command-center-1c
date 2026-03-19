import { describe, expect, it, vi } from 'vitest'
import { App as AntApp, Input } from 'antd'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import * as React from 'react'

import {
  DashboardPage,
  DrawerFormShell,
  EntityList,
  ModalFormShell,
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
