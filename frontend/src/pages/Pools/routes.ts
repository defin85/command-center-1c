export const POOL_EXECUTION_PACKS_ROUTE = '/pools/execution-packs'
export const POOL_CATALOG_ROUTE = '/pools/catalog'
export const POOL_RUNS_ROUTE = '/pools/runs'
export const POOL_TOPOLOGY_TEMPLATES_ROUTE = '/pools/topology-templates'

type PoolCatalogRouteParams = {
  poolId?: string | null
  tab?: string | null
  date?: string | null
}

type PoolTopologyTemplatesRouteParams = {
  search?: string | null
  templateId?: string | null
  detail?: boolean
  compose?: 'create' | 'revise' | null
  returnPoolId?: string | null
  returnTab?: string | null
  returnDate?: string | null
}

const appendRouteParam = (params: URLSearchParams, key: string, value?: string | null) => {
  const normalized = String(value || '').trim()
  if (normalized) {
    params.set(key, normalized)
  }
}

export const buildPoolCatalogRoute = ({
  poolId,
  tab,
  date,
}: PoolCatalogRouteParams = {}) => {
  const params = new URLSearchParams()
  appendRouteParam(params, 'pool_id', poolId)
  appendRouteParam(params, 'tab', tab)
  appendRouteParam(params, 'date', date)
  const query = params.toString()
  return query ? `${POOL_CATALOG_ROUTE}?${query}` : POOL_CATALOG_ROUTE
}

export const buildPoolTopologyTemplatesRoute = ({
  search,
  templateId,
  detail = false,
  compose,
  returnPoolId,
  returnTab,
  returnDate,
}: PoolTopologyTemplatesRouteParams = {}) => {
  const params = new URLSearchParams()
  appendRouteParam(params, 'q', search)
  appendRouteParam(params, 'template', templateId)
  if (detail) {
    params.set('detail', '1')
  }
  appendRouteParam(params, 'compose', compose)
  appendRouteParam(params, 'return_pool_id', returnPoolId)
  appendRouteParam(params, 'return_tab', returnTab)
  appendRouteParam(params, 'return_date', returnDate)
  const query = params.toString()
  return query ? `${POOL_TOPOLOGY_TEMPLATES_ROUTE}?${query}` : POOL_TOPOLOGY_TEMPLATES_ROUTE
}
