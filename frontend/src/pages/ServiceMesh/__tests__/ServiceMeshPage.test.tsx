import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'

import { changeLanguage } from '@/i18n/runtime'

vi.mock('../../../components/service-mesh/ServiceMeshTab', () => ({
  __esModule: true,
  default: ({
    selectedService,
    selectedOperationId,
  }: {
    selectedService?: string | null
    selectedOperationId?: string | null
  }) => (
    <div data-testid="service-mesh-tab">
      service={selectedService ?? 'none'} operation={selectedOperationId ?? 'none'}
    </div>
  ),
}))

vi.mock('../../../components/platform', () => ({
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
      <h2>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
      {actions}
    </div>
  ),
  RouteButton: ({
    children,
    to,
  }: {
    children: ReactNode
    to: string
  }) => <button data-to={to}>{children}</button>,
}))

import ServiceMeshPage from '../ServiceMeshPage'

function renderServiceMeshPage(initialEntry = '/service-mesh') {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/service-mesh" element={<ServiceMeshPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ServiceMeshPage i18n', () => {
  beforeEach(async () => {
    await changeLanguage('ru')
  })

  afterEach(async () => {
    await changeLanguage('ru')
  })

  it('renders localized page chrome and restores route context', () => {
    renderServiceMeshPage('/service-mesh?service=worker&operation=op-42')

    expect(screen.getByRole('heading', { name: 'Сервисная шина' })).toBeInTheDocument()
    expect(
      screen.getByText('Наблюдение за топологией и метриками в реальном времени внутри общего observability workspace.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Открыть system status' })).toHaveAttribute(
      'data-to',
      '/system-status?service=worker',
    )
    expect(
      screen.getByText('Контекст operation timeline восстановлен из состояния маршрута.'),
    ).toBeInTheDocument()
    expect(screen.getByTestId('service-mesh-tab')).toHaveTextContent('service=worker operation=op-42')
  })
})
