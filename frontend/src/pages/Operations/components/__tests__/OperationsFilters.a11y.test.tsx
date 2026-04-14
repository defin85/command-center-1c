import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { changeLanguage, ensureNamespaces } from '../../../../i18n/runtime'
import { OperationsFilters } from '../OperationsFilters'

describe('OperationsFilters a11y', () => {
  beforeEach(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'operations')
  })

  it('provides accessible names for filter inputs', () => {
    render(
      <OperationsFilters
        filters={{}}
        onChange={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Operation ID')).toBeInTheDocument()
    expect(screen.getByLabelText('Workflow')).toBeInTheDocument()
    expect(screen.getByLabelText('Node:')).toBeInTheDocument()
  })
})
