/**
 * Hook for responsive layout direction in Service Mesh diagram.
 *
 * Features:
 * - Auto mode: Automatically switches between TB/LR based on container aspect ratio
 * - Manual mode: User can force TB or LR direction
 * - Persistence: Saves user preference to localStorage
 *
 * @module hooks/useResponsiveDirection
 */

import { useState, useEffect, useCallback } from 'react'
import type { LayoutDirection, DirectionMode } from '../types/serviceMesh'

const STORAGE_KEY = 'service-mesh-direction-mode'

// Thresholds for auto-detection
const WIDTH_THRESHOLD = 1400
const ASPECT_RATIO_THRESHOLD = 1.8

/**
 * Hook for managing responsive layout direction in diagrams.
 *
 * @param containerRef - Reference to the container element for size measurements
 * @returns Object with current mode, calculated direction, and setter function
 *
 * @example
 * ```tsx
 * const containerRef = useRef<HTMLDivElement>(null)
 * const { mode, direction, setMode } = useResponsiveDirection(containerRef)
 *
 * return (
 *   <div ref={containerRef}>
 *     <Diagram direction={direction} />
 *     <Segmented value={mode} onChange={setMode} options={['TB', 'LR', 'auto']} />
 *   </div>
 * )
 * ```
 */
export function useResponsiveDirection(containerRef: React.RefObject<HTMLElement | null>) {
  // Load from localStorage or default to 'auto'
  const [mode, setMode] = useState<DirectionMode>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'TB' || saved === 'LR' || saved === 'auto') {
      return saved
    }
    return 'auto'
  })

  const [autoDirection, setAutoDirection] = useState<LayoutDirection>('TB')

  // Calculate direction for auto mode based on container size
  useEffect(() => {
    if (!containerRef.current || mode !== 'auto') return

    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      if (height === 0) return // Avoid division by zero

      const aspectRatio = width / height

      // Wide screen -> LR (horizontal layout)
      if (width >= WIDTH_THRESHOLD && aspectRatio >= ASPECT_RATIO_THRESHOLD) {
        setAutoDirection('LR')
      } else {
        setAutoDirection('TB')
      }
    })

    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [containerRef, mode])

  // Save to localStorage on mode change
  const handleModeChange = useCallback((newMode: DirectionMode) => {
    setMode(newMode)
    localStorage.setItem(STORAGE_KEY, newMode)
  }, [])

  // Final direction: use auto-calculated or explicit mode
  const direction: LayoutDirection = mode === 'auto' ? autoDirection : mode

  return {
    /** Current direction mode (TB, LR, or auto) */
    mode,
    /** Calculated layout direction (TB or LR) */
    direction,
    /** Function to change the mode */
    setMode: handleModeChange,
  }
}
