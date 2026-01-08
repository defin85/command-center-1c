import { apiClient } from './client'

export type DriverCommandShortcutDriver = 'ibcmd'

export interface DriverCommandShortcut {
  id: string
  driver: DriverCommandShortcutDriver
  command_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ListDriverCommandShortcutsResponse {
  items: DriverCommandShortcut[]
  count: number
}

export interface CreateDriverCommandShortcutRequest {
  driver: DriverCommandShortcutDriver
  command_id: string
  title: string
}

export interface DeleteDriverCommandShortcutResponse {
  success: boolean
  deleted: boolean
}

export async function listDriverCommandShortcuts(
  driver: DriverCommandShortcutDriver = 'ibcmd'
): Promise<ListDriverCommandShortcutsResponse> {
  const response = await apiClient.get<ListDriverCommandShortcutsResponse>(
    '/api/v2/operations/list-command-shortcuts/',
    { params: { driver }, skipGlobalError: true }
  )
  return response.data
}

export async function createDriverCommandShortcut(
  payload: CreateDriverCommandShortcutRequest
): Promise<DriverCommandShortcut> {
  const response = await apiClient.post<DriverCommandShortcut>(
    '/api/v2/operations/create-command-shortcut/',
    payload
  )
  return response.data
}

export async function deleteDriverCommandShortcut(shortcutId: string): Promise<DeleteDriverCommandShortcutResponse> {
  const response = await apiClient.post<DeleteDriverCommandShortcutResponse>(
    '/api/v2/operations/delete-command-shortcut/',
    { shortcut_id: shortcutId }
  )
  return response.data
}

