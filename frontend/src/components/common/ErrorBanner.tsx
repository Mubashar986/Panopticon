interface Props { message: string; onRetry: () => void; }

export function ErrorBanner({ message, onRetry }: Props) {
  return (
    <div className="w-full max-w-3xl mx-auto mt-[var(--space-8)] bg-[var(--color-error)]/10 border border-[var(--color-error)]/30 rounded-[var(--radius-lg)] p-[var(--space-4)] flex items-center justify-between">
      <div className="flex items-center gap-[var(--space-3)]">
        <svg className="w-5 h-5 text-[var(--color-error)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        <div>
          <p className="text-sm font-medium text-[var(--color-error)]">Search Engine Disconnected</p>
          <p className="text-xs text-[var(--color-text-secondary)] mt-[var(--space-1)]">{message}</p>
        </div>
      </div>
      <button onClick={onRetry} className="px-[var(--space-3)] py-[var(--space-1)] bg-[var(--color-error)] hover:bg-[var(--color-error)]/80 text-white text-xs font-medium rounded-[var(--radius-md)] transition-colors">Retry</button>
    </div>
  );
}
