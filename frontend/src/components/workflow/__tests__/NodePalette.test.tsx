import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { changeLanguage, ensureNamespaces } from '../../../i18n/runtime'
import NodePalette from '../NodePalette'


describe('NodePalette', () => {
  beforeEach(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'workflows')
  })

  afterEach(async () => {
    await ensureNamespaces('ru', 'workflows')
    await changeLanguage('ru')
  })

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
