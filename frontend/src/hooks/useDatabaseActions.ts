import { useState, useCallback } from 'react';
import { message } from 'antd';
import { executeOperation, type RASOperationType, type ExecuteOperationRequest } from '../api/operations';

interface DatabaseInfo {
  id: string;
  name: string;
}

export interface UseDatabaseActionsResult {
  execute: (
    operationType: RASOperationType,
    databases: DatabaseInfo[],
    config?: ExecuteOperationRequest['config']
  ) => Promise<string | null>;
  loading: boolean;
  error: string | null;
}

export const useDatabaseActions = (): UseDatabaseActionsResult => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(
    async (
      operationType: RASOperationType,
      databases: DatabaseInfo[],
      config?: ExecuteOperationRequest['config']
    ): Promise<string | null> => {
      setLoading(true);
      setError(null);

      try {
        const response = await executeOperation({
          operation_type: operationType,
          database_ids: databases.map((db) => db.id),
          config,
        });

        message.success(response.message);
        return response.operation_id;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Operation failed';
        setError(errorMsg);
        message.error(errorMsg);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { execute, loading, error };
};

export default useDatabaseActions;
