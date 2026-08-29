import { SearchResponse } from '../../types/api';
import { ResultCard } from './ResultCard';
import { LoadingSkeleton } from '../common/LoadingSkeleton';
import { EmptyState } from './EmptyState';
import { ErrorBanner } from '../common/ErrorBanner';
interface Props { data: SearchResponse | null; loading: boolean; error: string | null; query: string; onRetry: () => void; }

export function ResultsList({ data, loading, error, query, onRetry }: Props) {
  if (error) return <ErrorBanner message={error} onRetry={onRetry} />;
  if (loading) return <LoadingSkeleton />;
  if (!query) return <EmptyState type="initial" />;
  if (data && data.total_hits === 0) return <EmptyState type="no-results" query={query} />;
  if (!data) return null;

  return (
    <div className="w-full max-w-5xl mx-auto mt-[var(--space-8)]">
      <div className="flex items-center justify-between mb-[var(--space-6)] px-[var(--space-2)]">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Found <span className="text-[var(--color-text-primary)] font-semibold">{data.total_hits}</span> documents in <span className="text-[var(--color-primary)] font-mono">{data.processing_time_ms.toFixed(1)}ms</span>
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[var(--space-4)]">
        {data.results.map((item) => <ResultCard key={item.id} item={item} />)}
      </div>
    </div>
  );
}
