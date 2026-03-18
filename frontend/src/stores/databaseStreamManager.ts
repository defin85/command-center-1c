import { DatabaseStreamCoordinator } from '../realtime/database/databaseStreamCoordinator'

export type {
  DatabaseRealtimeEvent as DatabaseStreamEvent,
  DatabaseStreamState,
} from '../realtime/database/databaseStreamCoordinator'

export const databaseStreamManager = new DatabaseStreamCoordinator()
