export function StaleBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-[var(--space-2)] py-[var(--space-1)] bg-[var(--color-warning)]/10 text-[var(--color-warning)] border border-[var(--color-warning)]/30 rounded-[var(--radius-sm)] text-[10px] font-mono font-bold" title="Untouched for >90 days">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
      STALE
    </span>
  );
}
