import { useState, useEffect, useCallback } from 'react';
import { DocumentListResponse, DocumentResponseItem } from '../types/api';
import { useLiveEvents } from './useLiveEvents';

export function useDocuments() {
  const [data, setData] = useState<DocumentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState<string>('modified_time:desc');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [recentlyModifiedIds, setRecentlyModifiedIds] = useState<Set<string>>(new Set());

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
        sort_by: sortBy,
      });

      Object.entries(filters).forEach(([k, v]) => {
        if (v) params.append(k, v);
      });

      const res = await fetch(`http://localhost:8000/api/documents?${params}`);
      if (!res.ok) {
        throw new Error(`Failed to load document directory: ${res.status}`);
      }
      const result: DocumentListResponse = await res.json();
      setData(result);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to backend.');
    } finally {
      setLoading(false);
    }
  }, [limit, offset, sortBy, filters]);

  // Initial fetch and on dependency change
  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Listen for live SSE events and auto-refresh
  const { isConnected, lastEvent } = useLiveEvents({
    onSyncCompleted: () => {
      fetchDocuments();
    },
    onFileModified: (fileData) => {
      if (fileData.file_id) {
        setRecentlyModifiedIds((prev) => new Set(prev).add(fileData.file_id));
        // Remove pulse highlight after 5 seconds
        setTimeout(() => {
          setRecentlyModifiedIds((prev) => {
            const next = new Set(prev);
            next.delete(fileData.file_id);
            return next;
          });
        }, 5000);
      }
      fetchDocuments();
    },
  });

  return {
    data,
    documents: data?.documents || [],
    totalCount: data?.total_count || 0,
    loading,
    error,
    limit,
    setLimit,
    offset,
    setOffset,
    sortBy,
    setSortBy,
    filters,
    setFilters,
    recentlyModifiedIds,
    isLiveConnected: isConnected,
    lastLiveEvent: lastEvent,
    refetch: fetchDocuments,
  };
}
