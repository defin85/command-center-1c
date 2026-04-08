import type { ReactNode } from 'react'

import { firstSemanticActionLabel } from './semanticActionLabel'
import { trackUiAction } from './uiActionJournal'

type ConfirmConfigLike = {
  title?: ReactNode
  okText?: ReactNode
  onOk?: (...args: never[]) => unknown
}

type ConfirmApiLike<TConfig extends ConfirmConfigLike = ConfirmConfigLike, TResult = unknown> = {
  confirm: (config: TConfig) => TResult
}

export type ConfirmTrackingMeta = {
  actionKind?: 'modal.confirm' | 'operator.action'
  actionName?: string
  actionSource?: 'explicit' | 'navigation' | 'synthetic_request'
  context?: Record<string, unknown>
}

const resolveConfirmActionName = (
  config: ConfirmConfigLike,
  meta?: ConfirmTrackingMeta,
): string => (
  meta?.actionName
  ?? firstSemanticActionLabel(config.okText, config.title)
  ?? 'Modal confirm'
)

export const buildTrackedConfirmConfig = <TConfig extends ConfirmConfigLike>(
  config: TConfig,
  meta?: ConfirmTrackingMeta,
): TConfig => {
  const originalOnOk = config.onOk
  const onOk = ((...args: Parameters<NonNullable<TConfig['onOk']>>) => (
    trackUiAction({
      actionKind: meta?.actionKind ?? 'modal.confirm',
      actionName: resolveConfirmActionName(config, meta),
      actionSource: meta?.actionSource,
      context: meta?.context,
    }, () => originalOnOk?.(...args))
  )) as NonNullable<TConfig['onOk']>

  return {
    ...config,
    onOk,
  }
}

export const confirmWithTracking = <TConfig extends ConfirmConfigLike, TResult>(
  modal: ConfirmApiLike<TConfig, TResult>,
  config: TConfig,
  meta?: ConfirmTrackingMeta,
): TResult => (
  modal.confirm(buildTrackedConfirmConfig(config, meta))
)
