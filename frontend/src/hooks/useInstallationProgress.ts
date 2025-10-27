import { useState, useEffect, useCallback } from 'react'
import { InstallationProgress } from '../types/installation'
import { installationApi } from '../api/endpoints/installation'

interface UseInstallationProgressProps {
  taskId: string | null
  enabled: boolean
}

export const useInstallationProgress = ({ taskId, enabled }: UseInstallationProgressProps) => {
  const [progress, setProgress] = useState<InstallationProgress | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchProgress = useCallback(async () => {
    if (!taskId || !enabled) return

    setLoading(true)
    try {
      const data = await installationApi.getProgress(taskId)
      setProgress(data)
      setError(null)
    } catch (err: any) {
      setError(err.message || 'Failed to fetch progress')
    } finally {
      setLoading(false)
    }
  }, [taskId, enabled])

  useEffect(() => {
    if (!enabled) return

    // Fetch immediately
    fetchProgress()

    // Poll every 2 seconds
    const interval = setInterval(fetchProgress, 2000)

    return () => clearInterval(interval)
  }, [fetchProgress, enabled])

  return { progress, loading, error, refetch: fetchProgress }
}
