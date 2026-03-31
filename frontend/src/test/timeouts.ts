// Heavy route-level suites mount full authoring workspaces and are sensitive
// to 2-vCPU CI runner contention. Keep explicit per-test overrides aligned
// with the global Vitest budget instead of ad hoc 25-30s limits.
export const HEAVY_ROUTE_TEST_TIMEOUT_MS = 120000
