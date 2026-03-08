import { describe, expect, it } from 'vitest'

import { buildExecutorKindOptionsForSurface } from '../OperationExposureEditorModal'

describe('OperationExposureEditorModal executor kind labeling', () => {
  it('marks workflow executor as compatibility-only on template surface', () => {
    const options = buildExecutorKindOptionsForSurface('template', ['ibcmd_cli', 'workflow'])

    expect(options).toEqual([
      { value: 'ibcmd_cli', label: 'ibcmd_cli' },
      { value: 'workflow', label: 'workflow (compatibility)' },
    ])
  })

  it('keeps workflow executor label unchanged outside template surface', () => {
    const options = buildExecutorKindOptionsForSurface('action_catalog', ['workflow'])

    expect(options).toEqual([
      { value: 'workflow', label: 'workflow' },
    ])
  })
})
