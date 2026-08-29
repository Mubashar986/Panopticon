import { useEffect, useRef } from 'react';

interface Props { query: string; setQuery: (q: string) => void; loading: boolean; }

export function SearchBar({ query, setQuery, loading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) && document.activeElement !== inputRef.current) {
        e.preventDefault(); inputRef.current?.focus();
      }
      if (e.key === 'Escape' && document.activeElement === inputRef.current) {
        setQuery(''); inputRef.current?.blur();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setQuery]);

  return (
    <div className="relative w-full max-w-3xl mx-auto">
      <div className="absolute inset-y-0 left-0 flex items-center pl-[var(--space-4)] pointer-events-none">
        {loading ? (
          <svg className="animate-spin h-5 w-5 text-[var(--color-primary)]" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        ) : (
          <svg className="w-5 h-5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
        )}
      </div>
      <input
        ref={inputRef} type="text" value={query} onChange={(e) => setQuery(e.target.value)}
        placeholder="Search documents, tags, or owners... (Press '/')"
        className="w-full bg-[var(--color-bg-surface)] border border-[var(--color-border)] rounded-[var(--radius-lg)] py-[var(--space-3)] pl-[var(--space-12)] pr-[var(--space-4)] text-[var(--color-text-primary)] placeholder-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent transition-all"
      />
      <div className="absolute inset-y-0 right-0 flex items-center pr-[var(--space-4)] pointer-events-none">
        <kbd className="hidden sm:inline-block px-[var(--space-2)] py-[var(--space-1)] text-xs font-mono text-[var(--color-text-secondary)] bg-[var(--color-bg-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-sm)]">ESC</kbd>
      </div>
    </div>
  );
}
