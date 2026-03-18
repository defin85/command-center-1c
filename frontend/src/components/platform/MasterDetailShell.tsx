import { Drawer, Grid } from 'antd'
import type { ReactNode } from 'react'

const { useBreakpoint } = Grid
const DESKTOP_BREAKPOINT_PX = 992

type MasterDetailShellProps = {
  list: ReactNode
  detail: ReactNode
  detailOpen?: boolean
  onCloseDetail?: () => void
  detailDrawerTitle?: ReactNode
  listMinWidth?: number
  listMaxWidth?: number
  gap?: number
}

export function MasterDetailShell({
  list,
  detail,
  detailOpen = false,
  onCloseDetail,
  detailDrawerTitle,
  listMinWidth = 320,
  listMaxWidth = 420,
  gap = 24,
}: MasterDetailShellProps) {
  const screens = useBreakpoint()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < DESKTOP_BREAKPOINT_PX
        : false
    )

  if (isNarrow) {
    return (
      <>
        {list}
        <Drawer
          open={detailOpen}
          onClose={onCloseDetail}
          title={detailDrawerTitle}
          width="100%"
          destroyOnClose={false}
        >
          {detail}
        </Drawer>
      </>
    )
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `minmax(${listMinWidth}px, ${listMaxWidth}px) minmax(0, 1fr)`,
        gap,
        alignItems: 'start',
      }}
    >
      {list}
      {detail}
    </div>
  )
}
