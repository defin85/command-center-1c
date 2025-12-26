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
}

export interface ArtifactAliasUpsertPayload {
  alias: string
  version?: string
  version_id?: string
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
