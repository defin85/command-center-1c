import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { OperationsFilters } from '../OperationsFilters'

describe('OperationsFilters a11y', () => {
  it('provides accessible names for filter inputs', () => {
    render(
      <OperationsFilters
        filters={{}}
        onChange={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Operation ID filter')).toBeInTheDocument()
    expect(screen.getByLabelText('Workflow execution ID filter')).toBeInTheDocument()
    expect(screen.getByLabelText('Node ID filter')).toBeInTheDocument()
  })
})

