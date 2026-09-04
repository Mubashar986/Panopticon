import { useState, useEffect, useCallback } from 'react';
import { DocumentVersion, DocumentDiff, VersionHistoryResponse, DiffListResponse } from '../types/api';
import { getApiUrl } from '../config/api';

interface UseVersionHistoryReturn {
  versions: DocumentVersion[];
  diffs: DocumentDiff[];
  loading: boolean;
  error: string | null;
  selectedDiffId: string | null;
  selectedDiff: DocumentDiff | null;
  selectDiff: (diffId: string) => void;
  refetch: () => void;
}

export function useVersionHistory(fileId: string | null): UseVersionHistoryReturn {
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [diffs, setDiffs] = useState<DocumentDiff[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDiffId, setSelectedDiffId] = useState<string | null>(null);

  const fetchHistory = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const [versionsRes, diffsRes] = await Promise.all([
        fetch(getApiUrl(`/api/documents/${id}/versions`)),
        fetch(getApiUrl(`/api/documents/${id}/diffs`)),
      ]);

      if (!versionsRes.ok) {
        throw new Error(`Failed to fetch version history (${versionsRes.status})`);
      }
      if (!diffsRes.ok) {
        throw new Error(`Failed to fetch diffs (${diffsRes.status})`);
      }

      const versionsData: VersionHistoryResponse = await versionsRes.json();
      const diffsData: DiffListResponse = await diffsRes.json();

      setVersions(versionsData.items);
      setDiffs(diffsData.items);

      if (diffsData.items.length > 0) {
        setSelectedDiffId(diffsData.items[0].id);
      } else {
        setSelectedDiffId(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error loading history');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (fileId) {
      fetchHistory(fileId);
    } else {
      setVersions([]);
      setDiffs([]);
      setSelectedDiffId(null);
      setError(null);
    }
  }, [fileId, fetchHistory]);

  const selectDiff = useCallback((diffId: string) => {
    setSelectedDiffId(diffId);
  }, []);

  const selectedDiff = diffs.find((d) => d.id === selectedDiffId) || null;

  return {
    versions,
    diffs,
    loading,
    error,
    selectedDiffId,
    selectedDiff,
    selectDiff,
    refetch: () => fileId && fetchHistory(fileId),
  };
}
