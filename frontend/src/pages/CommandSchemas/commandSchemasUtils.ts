import type { DriverCatalogV2, DriverCommandV2 } from '../../api/driverCommands'
import type {
  CommandSchemaCommandPatch,
  CommandSchemaDriver,
  CommandSchemasOverridesCatalogV2,
} from '../../api/commandSchemas'

export type CommandListItem = {
  id: string
  display_id: string
  label: string
  description: string
  scope: string
  risk_level: string
  disabled: boolean
  has_overrides: boolean
  search_text: string
}

export const buildEmptyOverrides = (driver: CommandSchemaDriver): CommandSchemasOverridesCatalogV2 => ({
  catalog_version: 2,
  driver,
  overrides: { driver_schema: {}, commands_by_id: {} },
})

export const deepCopy = <T,>(value: T): T => {
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch (_err) {
    return value
  }
}

const isPlainObject = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

export const deepMergeObject = (target: Record<string, unknown>, patch: Record<string, unknown>): void => {
  for (const [key, value] of Object.entries(patch)) {
    const current = target[key]
    if (isPlainObject(value) && isPlainObject(current)) {
      deepMergeObject(current, value)
      continue
    }
    target[key] = value
  }
}

export const safeCommandsById = (catalog: DriverCatalogV2 | undefined | null): Record<string, DriverCommandV2> => {
  if (!catalog || typeof catalog !== 'object') return {}
  const commandsById = (catalog as { commands_by_id?: unknown }).commands_by_id
  if (!commandsById || typeof commandsById !== 'object') return {}
  return commandsById as Record<string, DriverCommandV2>
}

export const safeOverridesById = (
  catalog: CommandSchemasOverridesCatalogV2 | undefined | null
): Record<string, CommandSchemaCommandPatch> => {
  if (!catalog || typeof catalog !== 'object') return {}
  const overrides = (catalog as { overrides?: unknown }).overrides
  if (!overrides || typeof overrides !== 'object') return {}
  const commandsById = (overrides as { commands_by_id?: unknown }).commands_by_id
  if (!commandsById || typeof commandsById !== 'object') return {}
  return commandsById as Record<string, CommandSchemaCommandPatch>
}

export const safeOverridesDriverSchema = (
  catalog: CommandSchemasOverridesCatalogV2 | undefined | null
): Record<string, unknown> => {
  if (!catalog || typeof catalog !== 'object') return {}
  const overrides = (catalog as { overrides?: unknown }).overrides
  if (!overrides || typeof overrides !== 'object') return {}
  const driverSchema = (overrides as { driver_schema?: unknown }).driver_schema
  if (!driverSchema || typeof driverSchema !== 'object' || Array.isArray(driverSchema)) return {}
  return driverSchema as Record<string, unknown>
}

export const safeCatalogDriverSchema = (catalog: DriverCatalogV2 | undefined | null): Record<string, unknown> => {
  if (!catalog || typeof catalog !== 'object') return {}
  const driverSchema = (catalog as { driver_schema?: unknown }).driver_schema
  if (!driverSchema || typeof driverSchema !== 'object' || Array.isArray(driverSchema)) return {}
  return driverSchema as Record<string, unknown>
}

export const normalizeOverridesCatalog = (
  driver: CommandSchemaDriver,
  catalog: CommandSchemasOverridesCatalogV2 | undefined | null
): CommandSchemasOverridesCatalogV2 => {
  const base = catalog ?? buildEmptyOverrides(driver)
  const next = deepCopy(base)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const overrides: any = (next as any).overrides
  if (!overrides || typeof overrides !== 'object') {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(next as any).overrides = { driver_schema: {}, commands_by_id: {} }
    return next
  }

  if (!overrides.commands_by_id || typeof overrides.commands_by_id !== 'object') {
    overrides.commands_by_id = {}
  }
  if (!overrides.driver_schema || typeof overrides.driver_schema !== 'object' || Array.isArray(overrides.driver_schema)) {
    overrides.driver_schema = {}
  }

  return next
}

export const parseJsonObject = (raw: string): Record<string, unknown> | null => {
  const text = raw.trim()
  if (!text) return {}
  try {
    const parsed = JSON.parse(text) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return null
    }
    return parsed as Record<string, unknown>
  } catch (_err) {
    return null
  }
}

export const safeText = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

export const normalizeStringList = (raw: unknown): string[] => {
  if (!Array.isArray(raw)) return []
  const out = raw
    .map((item) => safeText(item).trim())
    .filter((item) => item.length > 0)
  return Array.from(new Set(out)).sort()
}

export const displayCommandId = (driver: CommandSchemaDriver, commandId: string): string => {
  if (driver === 'ibcmd' && commandId.startsWith('ibcmd.')) {
    return commandId.slice('ibcmd.'.length)
  }
  return commandId
}

export const groupKeyForCommand = (driver: CommandSchemaDriver, commandId: string): string => {
  const display = displayCommandId(driver, commandId)
  if (driver === 'cli') {
    return 'CLI'
  }
  const parts = display.split('.').filter((part) => part.length > 0)
  if (parts.length === 0) return 'Other'
  return `${parts[0]}.*`
}

export const saveText = (value: string): string => value.trim()

