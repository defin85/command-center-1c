import { Button } from 'antd'
import type { ButtonProps } from 'antd'
import { useNavigate } from 'react-router-dom'

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

  return (
    <Button
      {...buttonProps}
      onClick={(event) => {
        onClick?.(event)
        if (event.defaultPrevented) {
          return
        }
        navigate(to, { replace, state })
      }}
    />
  )
}
