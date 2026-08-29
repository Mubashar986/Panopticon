import { useState, useEffect, useCallback } from 'react';
import { SearchResponse } from '../../types/api';

export function useSearch() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'fuzzy' | 'tag' | 'exact'>('fuzzy');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ q: searchQuery, mode });
      Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
      
      const res = await fetch(`http://localhost:8000/api/search?${params}`);
      if (!res.ok) throw new Error(`Search failed: ${res.status}`);
      const result: SearchResponse = await res.json();
      setData(result);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [mode, filters]);

  useEffect(() => {
    const timer = setTimeout(() => fetchSearch(query), 250); // 250ms Debounce
    return () => clearTimeout(timer);
  }, [query, fetchSearch]);

  return { query, setQuery, mode, setMode, filters, setFilters, data, loading, error, retry: () => fetchSearch(query) };
}
