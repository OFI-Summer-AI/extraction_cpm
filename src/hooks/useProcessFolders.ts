import { useState, useEffect, useCallback } from 'react';
import { getProcessFolders, ProcessFolder, SymbioProcessFoldersError } from '../services/symbioProcessFolders';

interface UseProcessFoldersOptions {
  storagecollection: string;
  tenant: string;
  symbioAuthToken?: string;
  autoFetch?: boolean;
}

interface UseProcessFoldersResult {
  folders: ProcessFolder[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useProcessFolders({
  storagecollection,
  tenant,
  symbioAuthToken,
  autoFetch = true,
}: UseProcessFoldersOptions): UseProcessFoldersResult {
  const [folders, setFolders] = useState<ProcessFolder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFolders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getProcessFolders(storagecollection, tenant, symbioAuthToken);
      setFolders(data);
    } catch (err) {
      const message = err instanceof SymbioProcessFoldersError
        ? err.message
        : 'Error desconocido al cargar carpetas de procesos';
      setError(message);
      setFolders([]);
    } finally {
      setLoading(false);
    }
  }, [storagecollection, tenant, symbioAuthToken]);

  useEffect(() => {
    if (autoFetch) {
      fetchFolders();
    }
  }, [fetchFolders, autoFetch]);

  return { folders, loading, error, refetch: fetchFolders };
}