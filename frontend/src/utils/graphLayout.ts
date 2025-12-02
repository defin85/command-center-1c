/**
 * Graph layout utilities using dagre algorithm.
 *
 * Provides automatic node positioning for service mesh visualization
 * based on the topology graph structure.
 */
import dagre from 'dagre'
import type { ServiceMetrics, ServiceConnection, ServiceLayoutConfig } from '../types/serviceMesh'

export interface LayoutOptions {
  /** Layout direction: TB (top-bottom), LR (left-right), BT, RL */
  direction: 'TB' | 'LR' | 'BT' | 'RL'
  /** Width of each node in pixels */
  nodeWidth: number
  /** Height of each node in pixels */
  nodeHeight: number
  /** Vertical separation between ranks (levels) */
  rankSep: number
  /** Horizontal separation between nodes on same level */
  nodeSep: number
}

const DEFAULT_LAYOUT_OPTIONS: LayoutOptions = {
  direction: 'TB',
  nodeWidth: 180,
  nodeHeight: 100,
  rankSep: 100,
  nodeSep: 80,
}

/**
 * Calculate automatic node positions using dagre layout algorithm.
 *
 * @param services - Array of service metrics (nodes)
 * @param connections - Array of service connections (edges)
 * @param options - Layout configuration options
 * @returns ServiceLayoutConfig with calculated positions
 */
export function calculateDagreLayout(
  services: ServiceMetrics[],
  connections: ServiceConnection[],
  options: Partial<LayoutOptions> = {}
): ServiceLayoutConfig {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options }

  // Create dagre graph
  const g = new dagre.graphlib.Graph()
  g.setGraph({
    rankdir: opts.direction,
    ranksep: opts.rankSep,
    nodesep: opts.nodeSep,
    marginx: 50,
    marginy: 50,
  })
  g.setDefaultEdgeLabel(() => ({}))

  // Add nodes
  services.forEach((service) => {
    g.setNode(service.name, {
      width: opts.nodeWidth,
      height: opts.nodeHeight,
    })
  })

  // Add edges (connections define hierarchy)
  connections.forEach((conn) => {
    if (g.hasNode(conn.source) && g.hasNode(conn.target)) {
      g.setEdge(conn.source, conn.target)
    }
  })

  // Run layout algorithm
  dagre.layout(g)

  // Extract positions (dagre returns center, convert to top-left for react-flow)
  const positions: ServiceLayoutConfig = {}
  g.nodes().forEach((nodeId) => {
    const node = g.node(nodeId)
    if (node) {
      positions[nodeId] = {
        x: node.x - opts.nodeWidth / 2,
        y: node.y - opts.nodeHeight / 2,
      }
    }
  })

  return positions
}

/**
 * Get layout with optional user overrides.
 * User-dragged positions take precedence over calculated ones.
 *
 * @param services - Array of service metrics
 * @param connections - Array of service connections
 * @param userOverrides - User-defined position overrides (from drag-and-drop)
 * @param options - Layout options
 * @returns Merged layout config
 */
export function getLayoutWithOverrides(
  services: ServiceMetrics[],
  connections: ServiceConnection[],
  userOverrides?: ServiceLayoutConfig | null,
  options?: Partial<LayoutOptions>
): ServiceLayoutConfig {
  const autoLayout = calculateDagreLayout(services, connections, options)

  if (!userOverrides) {
    return autoLayout
  }

  // Merge: user positions take precedence
  return { ...autoLayout, ...userOverrides }
}
