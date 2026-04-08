import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockTrackUiAction } = vi.hoisted(() => ({
  mockTrackUiAction: vi.fn((_: unknown, handler?: () => unknown) => handler?.()),
}))

vi.mock('../uiActionJournal', () => ({
  trackUiAction: mockTrackUiAction,
}))

import { confirmWithTracking } from '../confirmWithTracking'

describe('confirmWithTracking', () => {
  beforeEach(() => {
    mockTrackUiAction.mockClear()
  })

  it('wraps confirm onOk with a derived semantic action label', () => {
    const onOk = vi.fn()
    const modal = {
      confirm: vi.fn((config: { onOk?: () => unknown }) => config),
    }

    confirmWithTracking(modal, {
      title: 'Delete artifact?',
      okText: 'Delete',
      onOk,
    })

    const trackedConfig = modal.confirm.mock.calls[0]?.[0] as { onOk?: () => unknown }

    trackedConfig.onOk?.()

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'modal.confirm',
        actionName: 'Delete',
      }),
      expect.any(Function),
    )
    expect(onOk).toHaveBeenCalledTimes(1)
  })

  it('preserves explicit operator metadata overrides', () => {
    const onOk = vi.fn()
    const modal = {
      confirm: vi.fn((config: { onOk?: () => unknown }) => config),
    }

    confirmWithTracking(modal, {
      title: 'Reset credentials?',
      onOk,
    }, {
      actionKind: 'operator.action',
      actionName: 'Reset database credentials',
      context: {
        database_id: 'db-1',
      },
    })

    const trackedConfig = modal.confirm.mock.calls[0]?.[0] as { onOk?: () => unknown }

    trackedConfig.onOk?.()

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Reset database credentials',
        context: {
          database_id: 'db-1',
        },
      }),
      expect.any(Function),
    )
    expect(onOk).toHaveBeenCalledTimes(1)
  })
})
