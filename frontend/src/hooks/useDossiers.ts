import { useState, useEffect, useCallback, useMemo } from 'react';
import { DossierSummary, DossierCreatePayload, DocumentResponseItem } from '../types/api';
import { getApiUrl } from '../config/api';

export interface UseDossiersReturn {
  dossiers: DossierSummary[];
  activeDossier: DossierSummary | null;
  setActiveDossier: (dossier: DossierSummary | null) => void;
  activeDossierFiles: DocumentResponseItem[];
  activeDossierFileIds: Set<string>;
  loading: boolean;
  filesLoading: boolean;
  error: string | null;
  refreshDossiers: () => Promise<void>;
  createDossier: (payload: DossierCreatePayload) => Promise<DossierSummary>;
}

export function useDossiers(): UseDossiersReturn {
  const [dossiers, setDossiers] = useState<DossierSummary[]>([]);
  const [activeDossier, setActiveDossier] = useState<DossierSummary | null>(null);
  const [activeDossierFiles, setActiveDossierFiles] = useState<DocumentResponseItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filesLoading, setFilesLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDossiers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(getApiUrl('/api/dossiers'));
      if (!response.ok) {
        throw new Error(`Failed to load dossiers: HTTP ${response.status}`);
      }
      const data: DossierSummary[] = await response.json();
      setDossiers(data);
    } catch (err) {
      console.error('Failed to fetch dossiers:', err);
      setError(err instanceof Error ? err.message : 'Unknown error loading dossiers');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDossierFiles = useCallback(async (dossierId: string) => {
    setFilesLoading(true);
    try {
      const response = await fetch(getApiUrl(`/api/dossiers/${dossierId}/items`));
      if (!response.ok) {
        throw new Error(`Failed to load dossier items: HTTP ${response.status}`);
      }
      const data: DocumentResponseItem[] = await response.json();
      setActiveDossierFiles(data);
    } catch (err) {
      console.error(`Failed to fetch items for dossier ${dossierId}:`, err);
      setActiveDossierFiles([]);
    } finally {
      setFilesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDossiers();
  }, [fetchDossiers]);

  useEffect(() => {
    if (activeDossier) {
      fetchDossierFiles(activeDossier.id);
    } else {
      setActiveDossierFiles([]);
      setFilesLoading(false);
    }
  }, [activeDossier, fetchDossierFiles]);

  const activeDossierFileIds = useMemo(() => {
    return new Set(activeDossierFiles.map((file) => file.id));
  }, [activeDossierFiles]);

  const createDossier = useCallback(
    async (payload: DossierCreatePayload): Promise<DossierSummary> => {
      const response = await fetch(getApiUrl('/api/dossiers'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to create dossier: HTTP ${response.status}`);
      }

      const created: DossierSummary = await response.json();
      setDossiers((prev) => [created, ...prev]);
      setActiveDossier(created);
      return created;
    },
    []
  );

  return {
    dossiers,
    activeDossier,
    setActiveDossier,
    activeDossierFiles,
    activeDossierFileIds,
    loading,
    filesLoading,
    error,
    refreshDossiers: fetchDossiers,
    createDossier,
  };
}
