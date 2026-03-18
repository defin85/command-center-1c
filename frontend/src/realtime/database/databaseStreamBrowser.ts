import type {
  DatabaseCrossTabBus,
  DatabaseCrossTabMessage,
  DatabaseLeaderLease,
  DatabaseLeaderLeaseStore,
} from './databaseStreamTypes'

const CLIENT_INSTANCE_STORAGE_KEY = 'cc1c.database-stream.client-instance-id'
const TAB_ID_STORAGE_KEY = 'cc1c.database-stream.tab-id'
const LEASE_STORAGE_KEY = 'cc1c.database-stream.leader'
const BUS_STORAGE_KEY = 'cc1c.database-stream.bus'
const BUS_CHANNEL_NAME = 'cc1c:database-stream'

const generateRuntimeId = (prefix: string) => {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return `${prefix}-${globalThis.crypto.randomUUID()}`
  }
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`
}

const parseJson = <T>(value: string | null): T | null => {
  if (!value) return null
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

const readOrCreateStorageId = (storage: Storage | undefined, key: string, prefix: string) => {
  if (!storage) {
    return generateRuntimeId(prefix)
  }
  const existing = storage.getItem(key)
  if (existing) {
    return existing
  }
  const nextValue = generateRuntimeId(prefix)
  storage.setItem(key, nextValue)
  return nextValue
}

export const getDatabaseStreamClientInstanceId = () => (
  readOrCreateStorageId(
    typeof window !== 'undefined' ? window.localStorage : undefined,
    CLIENT_INSTANCE_STORAGE_KEY,
    'browser',
  )
)

export const getDatabaseStreamTabId = () => (
  readOrCreateStorageId(
    typeof window !== 'undefined' ? window.sessionStorage : undefined,
    TAB_ID_STORAGE_KEY,
    'tab',
  )
)

export class BrowserDatabaseCrossTabBus implements DatabaseCrossTabBus {
  private listeners = new Set<(message: DatabaseCrossTabMessage) => void>()
  private channel = typeof BroadcastChannel !== 'undefined'
    ? new BroadcastChannel(BUS_CHANNEL_NAME)
    : null
  private storageListener: ((event: StorageEvent) => void) | null = null

  constructor() {
    if (this.channel) {
      this.channel.onmessage = (event) => {
        this.emit(event.data as DatabaseCrossTabMessage)
      }
      return
    }

    if (typeof window !== 'undefined') {
      this.storageListener = (event) => {
        if (event.key !== BUS_STORAGE_KEY) return
        const payload = parseJson<{ message: DatabaseCrossTabMessage }>(event.newValue)
        if (payload?.message) {
          this.emit(payload.message)
        }
      }
      window.addEventListener('storage', this.storageListener)
    }
  }

  post(message: DatabaseCrossTabMessage) {
    if (this.channel) {
      this.channel.postMessage(message)
      return
    }
    if (typeof window === 'undefined') return
    window.localStorage.setItem(BUS_STORAGE_KEY, JSON.stringify({
      nonce: generateRuntimeId('message'),
      message,
    }))
  }

  subscribe(listener: (message: DatabaseCrossTabMessage) => void) {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  close() {
    if (this.channel) {
      this.channel.close()
      return
    }
    if (this.storageListener && typeof window !== 'undefined') {
      window.removeEventListener('storage', this.storageListener)
    }
    this.storageListener = null
  }

  private emit(message: DatabaseCrossTabMessage) {
    for (const listener of this.listeners) {
      listener(message)
    }
  }
}

export class BrowserDatabaseLeaderLeaseStore implements DatabaseLeaderLeaseStore {
  private listeners = new Set<(lease: DatabaseLeaderLease | null) => void>()
  private storageListener: ((event: StorageEvent) => void) | null = null

  constructor() {
    if (typeof window !== 'undefined') {
      this.storageListener = (event) => {
        if (event.key !== LEASE_STORAGE_KEY) return
        this.emit(this.read())
      }
      window.addEventListener('storage', this.storageListener)
    }
  }

  read() {
    if (typeof window === 'undefined') return null
    return parseJson<DatabaseLeaderLease>(window.localStorage.getItem(LEASE_STORAGE_KEY))
  }

  write(lease: DatabaseLeaderLease) {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(LEASE_STORAGE_KEY, JSON.stringify(lease))
    this.emit(lease)
  }

  clear(ownerTabId?: string) {
    if (typeof window === 'undefined') return
    const currentLease = this.read()
    if (ownerTabId && currentLease?.tabId !== ownerTabId) {
      return
    }
    window.localStorage.removeItem(LEASE_STORAGE_KEY)
    this.emit(null)
  }

  subscribe(listener: (lease: DatabaseLeaderLease | null) => void) {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  private emit(lease: DatabaseLeaderLease | null) {
    for (const listener of this.listeners) {
      listener(lease)
    }
  }
}
