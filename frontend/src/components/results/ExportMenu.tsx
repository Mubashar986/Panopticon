import { useState, useRef, useEffect } from 'react';
interface Props { exportLinks: Record<string, string> | null; }

export function ExportMenu({ exportLinks }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  if (!exportLinks) return null;

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} className="p-[var(--space-2)] rounded-[var(--radius-sm)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-elevated)] hover:text-[var(--color-text-primary)] transition-colors" aria-label="Export options">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
      </button>
      {open && (
        <div className="absolute right-0 mt-[var(--space-2)] w-48 bg-[var(--color-bg-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] shadow-lg z-10 overflow-hidden">
          {Object.entries(exportLinks).map(([format, url]) => (
            <a key={format} href={url} target="_blank" rel="noopener noreferrer" className="block px-[var(--space-4)] py-[var(--space-2)] text-sm text-[var(--color-text-primary)] hover:bg-[var(--color-primary)]/10 hover:text-[var(--color-primary)] transition-colors">
              Export as {format.toUpperCase()}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
