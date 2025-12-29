import { apiClient } from './client'

export type ArtifactKind =
  | 'extension'
  | 'config_xml'
  | 'dt_backup'
  | 'epf'
  | 'erf'
  | 'ibcmd_package'
  | 'ras_script'
  | 'other'

export interface Artifact {
  id: string
  name: string
  kind: ArtifactKind
  is_versioned: boolean
  tags: string[]
  created_at: string
}

export interface ArtifactVersion {
  id: string
  version: string
  filename: string
  storage_key: string
  size: number
  checksum: string
  content_type: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface ArtifactAlias {
  id: string
  alias: string
  version: string
  version_id: string
  updated_at: string
}

export interface ArtifactListResponse {
  artifacts: Artifact[]
  count: number
}

export interface ArtifactVersionListResponse {
  versions: ArtifactVersion[]
  count: number
}

export interface ArtifactAliasListResponse {
  aliases: ArtifactAlias[]
  count: number
}

export interface ArtifactListParams {
  kind?: string
  name?: string
  tag?: string
  include_deleted?: boolean
  only_deleted?: boolean
}

export interface ArtifactAliasUpsertPayload {
  alias: string
  version?: string
  version_id?: string
}

export interface ArtifactCreatePayload {
  name: string
  kind: ArtifactKind
  is_versioned: boolean
  tags: string[]
}

export interface UploadProgressInfo {
  percent: number
  loaded: number
  total: number
}

export interface ArtifactVersionUploadPayload {
  file: File
  version: string
  filename?: string
  metadata?: string
  onProgress?: (info: UploadProgressInfo) => void
}

export const listArtifacts = async (
  params: ArtifactListParams,
  signal?: AbortSignal
): Promise<ArtifactListResponse> => {
  const response = await apiClient.get<ArtifactListResponse>(
    '/api/v2/artifacts/',
    {
      params,
      signal,
      skipGlobalError: true,
    }
  )
  return response.data
}

export const createArtifact = async (
  payload: ArtifactCreatePayload
): Promise<Artifact> => {
  const response = await apiClient.post<{ artifact: Artifact }>(
    '/api/v2/artifacts/create/',
    payload,
    {
      skipGlobalError: true,
    }
  )
  return response.data.artifact
}

export const uploadArtifactVersion = async (
  artifactId: string,
  payload: ArtifactVersionUploadPayload
): Promise<ArtifactVersion> => {
  const formData = new FormData()
  formData.append('file', payload.file)
  formData.append('version', payload.version)
  if (payload.filename) {
    formData.append('filename', payload.filename)
  }
  if (payload.metadata) {
    formData.append('metadata', payload.metadata)
  }
  const response = await apiClient.post<ArtifactVersion>(
    `/api/v2/artifacts/${artifactId}/versions/upload/`,
    formData,
    {
      skipGlobalError: true,
      onUploadProgress: (event) => {
        if (!payload.onProgress || !event.total) return
        payload.onProgress({
          percent: Math.round((event.loaded / event.total) * 100),
          loaded: event.loaded,
          total: event.total,
        })
      },
    }
  )
  return response.data
}

export const listArtifactVersions = async (
  artifactId: string,
  signal?: AbortSignal
): Promise<ArtifactVersionListResponse> => {
  const response = await apiClient.get<ArtifactVersionListResponse>(
    `/api/v2/artifacts/${artifactId}/versions/`,
    {
      signal,
      skipGlobalError: true,
    }
  )
  return response.data
}

export const listArtifactAliases = async (
  artifactId: string,
  signal?: AbortSignal
): Promise<ArtifactAliasListResponse> => {
  const response = await apiClient.get<ArtifactAliasListResponse>(
    `/api/v2/artifacts/${artifactId}/aliases/`,
    {
      signal,
      skipGlobalError: true,
    }
  )
  return response.data
}

export const upsertArtifactAlias = async (
  artifactId: string,
  payload: ArtifactAliasUpsertPayload
): Promise<ArtifactAlias> => {
  const response = await apiClient.post<ArtifactAlias>(
    `/api/v2/artifacts/${artifactId}/aliases/upsert/`,
    payload
  )
  return response.data
}

export const deleteArtifact = async (artifactId: string): Promise<void> => {
  await apiClient.delete(`/api/v2/artifacts/${artifactId}/`, {
    skipGlobalError: true,
  })
}

export const restoreArtifact = async (artifactId: string): Promise<Artifact> => {
  const response = await apiClient.post<Artifact>(
    `/api/v2/artifacts/${artifactId}/restore/`,
    {},
    {
      skipGlobalError: true,
    }
  )
  return response.data
}

export const downloadArtifactVersion = async (
  artifactId: string,
  version: string
): Promise<Blob> => {
  const response = await apiClient.get(
    `/api/v2/artifacts/${artifactId}/versions/${version}/download/`,
    {
      responseType: 'blob',
      skipGlobalError: true,
    }
  )
  return response.data as Blob
}
