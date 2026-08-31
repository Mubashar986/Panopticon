interface PaginationBarProps {
  totalCount: number;
  limit: number;
  offset: number;
  onPageChange: (newOffset: number) => void;
  onLimitChange: (newLimit: number) => void;
  loading?: boolean;
}

export function PaginationBar({
  totalCount,
  limit,
  offset,
  onPageChange,
  onLimitChange,
  loading = false,
}: PaginationBarProps) {
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(totalCount / limit));
  const startItem = totalCount === 0 ? 0 : offset + 1;
  const endItem = Math.min(offset + limit, totalCount);

  const canGoPrevious = offset > 0 && !loading;
  const canGoNext = offset + limit < totalCount && !loading;

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-[var(--space-4)] px-[var(--space-4)] py-[var(--space-3)] bg-[var(--color-bg-surface)] border-t border-[var(--color-border)] rounded-b-[var(--radius-lg)] text-xs text-[var(--color-text-secondary)]">
      {/* Item Counter & Sizing */}
      <div className="flex items-center gap-[var(--space-4)]">
        <span>
          Showing <strong className="text-[var(--color-text-primary)] font-medium">{startItem}–{endItem}</strong> of{' '}
          <strong className="text-[var(--color-text-primary)] font-medium">{totalCount}</strong> documents
        </span>

        <div className="flex items-center gap-[var(--space-2)]">
          <label htmlFor="page-size-select" className="text-[var(--color-text-secondary)]">Per page:</label>
          <select
            id="page-size-select"
            value={limit}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            disabled={loading}
            className="bg-[var(--color-bg-surface-elevated)] text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-[var(--radius-sm)] px-[var(--space-2)] py-[var(--space-1)] focus:outline-none focus:border-[var(--color-primary)] cursor-pointer disabled:opacity-50"
          >
            <option value="25">25</option>
            <option value="50">50</option>
            <option value="100">100</option>
            <option value="250">250</option>
          </select>
        </div>
      </div>

      {/* Pagination Controls */}
      <div className="flex items-center gap-[var(--space-2)]">
        <span className="mr-[var(--space-2)]">
          Page {currentPage} of {totalPages}
        </span>

        <button
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          disabled={!canGoPrevious}
          aria-label="Previous Page"
          className="px-[var(--space-3)] py-[var(--space-1)] bg-[var(--color-bg-surface-elevated)] text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-[var(--radius-sm)] hover:border-[var(--color-primary)] disabled:opacity-40 disabled:hover:border-[var(--color-border)] transition-colors cursor-pointer disabled:cursor-not-allowed"
        >
          Previous
        </button>

        <button
          onClick={() => onPageChange(offset + limit)}
          disabled={!canGoNext}
          aria-label="Next Page"
          className="px-[var(--space-3)] py-[var(--space-1)] bg-[var(--color-bg-surface-elevated)] text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-[var(--radius-sm)] hover:border-[var(--color-primary)] disabled:opacity-40 disabled:hover:border-[var(--color-border)] transition-colors cursor-pointer disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>
  );
}
