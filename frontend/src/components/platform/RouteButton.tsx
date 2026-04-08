import { Button } from 'antd'
import type { ButtonProps } from 'antd'
import { useNavigate } from 'react-router-dom'
import { trackUiAction } from '../../observability/uiActionJournal'
import { firstSemanticActionLabel } from '../../observability/semanticActionLabel'

type RouteButtonProps = Omit<ButtonProps, 'href'> & {
  to: string
  replace?: boolean
  state?: unknown
}

export function RouteButton({
  to,
  replace,
  state,
  onClick,
  ...buttonProps
}: RouteButtonProps) {
  const navigate = useNavigate()
  const actionName = firstSemanticActionLabel(
    buttonProps.children,
    buttonProps['aria-label'],
  ) ?? `Navigate to ${to}`

  return (
    <Button
      {...buttonProps}
      onClick={(event) => {
        onClick?.(event)
        if (event.defaultPrevented) {
          return
        }
        trackUiAction({
          actionKind: 'route.navigate',
          actionName,
          actionSource: 'navigation',
        }, () => {
          navigate(to, { replace, state })
        })
      }}
    />
  )
}
