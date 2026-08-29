import { useState, useEffect, useCallback, useRef } from 'react';
import { SyncStatusResponse } from '../../types/api';

export function useSync() {
  const [status, setStatus] = useState<SyncStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/sync/status');
      if (res.ok) {
        const data: SyncStatusResponse = await res.json();
        setStatus(data);
      }
    } catch (err) { /* Silent fail for background polling */ }
  }, []);

  useEffect(() => {
    fetchStatus();
    // Poll faster when syncing, slower when idle
    const pollInterval = status?.is_syncing ? 1000 : 10000; 
    intervalRef.current = setInterval(fetchStatus, pollInterval);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetchStatus, status?.is_syncing]);

  const triggerSync = async (fullRefresh = false) => {
    setLoading(true); setError(null);
    try {
      const res = await fetch('http://localhost:8000/api/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_refresh: fullRefresh, export_content: true }),
      });
      if (res.status === 409) throw new Error('Sync already in progress. Check the progress drawer.');
      if (!res.ok) throw new Error('Failed to start sync');
      await fetchStatus();
    } catch (err: any) { setError(err.message); } 
    finally { setLoading(false); }
  };

  const triggerReindex = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/sync/reindex', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to start reindex');
      await fetchStatus();
    } catch (err: any) { setError(err.message); } 
    finally { setLoading(false); }
  };

  return { status, loading, error, triggerSync, triggerReindex };
}
