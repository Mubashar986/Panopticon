export function LoadingSkeleton() {
  return (
    <div className="w-full max-w-5xl mx-auto mt-[var(--space-8)] grid grid-cols-1 md:grid-cols-2 gap-[var(--space-4)]">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="bg-[var(--color-bg-surface)] border border-[var(--color-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] animate-pulse">
          <div className="flex items-center gap-[var(--space-3)] mb-[var(--space-4)]">
            <div className="w-6 h-6 bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-sm)]" />
            <div className="h-4 bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-sm)] flex-1" />
          </div>
          <div className="space-y-[var(--space-2)] mb-[var(--space-4)]">
            <div className="h-3 bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-sm)] w-full" />
            <div className="h-3 bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-sm)] w-4/5" />
          </div>
          <div className="flex justify-between pt-[var(--space-3)] border-t border-[var(--color-border)]">
            <div className="h-3 bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-sm)] w-1/3" />
            <div className="h-6 bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-md)] w-24" />
          </div>
        </div>
      ))}
    </div>
  );
}
