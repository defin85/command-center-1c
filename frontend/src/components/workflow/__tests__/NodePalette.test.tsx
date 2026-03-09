import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import NodePalette from '../NodePalette'


describe('NodePalette', () => {
  it('shows only analyst-facing building blocks on the default palette', () => {
    render(<NodePalette />)

    expect(screen.getByText('Operation Task')).toBeInTheDocument()
    expect(screen.getByText('Decision Gate')).toBeInTheDocument()
    expect(screen.getByText('Approval Gate')).toBeInTheDocument()
    expect(screen.getByText('Subworkflow Call')).toBeInTheDocument()
    expect(screen.queryByText('Parallel Stage')).not.toBeInTheDocument()
    expect(screen.queryByText('Repeat Stage')).not.toBeInTheDocument()
  })
})
