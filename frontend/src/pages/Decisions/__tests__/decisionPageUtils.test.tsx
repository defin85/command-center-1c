import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderCompatibilityTag } from '../decisionPageUtils'

describe('decisionPageUtils', () => {
  it('renders incompatible compatibility status with contrast-safe badge styling', () => {
    render(
      <div>
        {renderCompatibilityTag({
          status: 'incompatible',
          reason: 'configuration_scope_mismatch',
          is_compatible: false,
        })}
      </div>,
    )

    expect(screen.getByText('incompatible')).toHaveStyle({
      backgroundColor: '#ffedd5',
      borderColor: '#fdba74',
      color: '#9a3412',
    })
  })
})
