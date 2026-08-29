interface Props { type: 'initial' | 'no-results'; query?: string; }

export function EmptyState({ type, query }: Props) {
  if (type === 'initial') {
    return (
      <div className="flex flex-col items-center justify-center mt-[var(--space-16)] text-center">
        <div className="w-16 h-16 mb-[var(--space-6)] rounded-[var(--radius-full)] bg-[var(--color-primary)]/10 flex items-center justify-center">
          <svg className="w-8 h-8 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
        </div>
        <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-[var(--space-2)]">Discover your workspace</h2>
        <p className="text-[var(--color-text-secondary)] max-w-md mb-[var(--space-6)]">Search across Google Drive documents, sheets, and project tags.</p>
        <div className="flex flex-wrap gap-[var(--space-2)] justify-center">
          {['Project Falcon', 'Architecture', 'Q3 Roadmap'].map((s) => (
            <span key={s} className="px-[var(--space-3)] py-[var(--space-1)] bg-[var(--color-bg-surface)] border border-[var(--color-border)] rounded-[var(--radius-full)] text-sm text-[var(--color-text-secondary)]">{s}</span>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center justify-center mt-[var(--space-16)] text-center">
      <div className="w-16 h-16 mb-[var(--space-6)] rounded-[var(--radius-full)] bg-[var(--color-warning)]/10 flex items-center justify-center">
        <svg className="w-8 h-8 text-[var(--color-warning)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
      </div>
      <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-[var(--space-2)]">No documents found</h2>
      <p className="text-[var(--color-text-secondary)] max-w-md">We couldn't find any matches for <span className="font-mono text-[var(--color-text-primary)]">"{query}"</span>. Try checking for typos.</p>
    </div>
  );
}
