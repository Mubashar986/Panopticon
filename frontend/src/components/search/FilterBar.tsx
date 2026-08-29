interface Props { filters: Record<string, string>; setFilters: (f: Record<string, string>) => void; }

export function FilterBar({ filters, setFilters }: Props) {
  const toggleFilter = (key: string, value: string) => setFilters({ ...filters, [key]: filters[key] === value ? '' : value });
  const pills = [
    { key: 'file_type', label: 'Docs', value: 'document' },
    { key: 'file_type', label: 'Sheets', value: 'spreadsheet' },
    { key: 'sharing_status', label: 'Domain', value: 'domain' },
    { key: 'sharing_status', label: 'Shared', value: 'shared' },
  ];
  return (
    <div className="flex flex-wrap gap-[var(--space-2)]">
      {pills.map((p) => (
        <button key={p.label} onClick={() => toggleFilter(p.key, p.value)}
          className={`px-[var(--space-3)] py-[var(--space-1)] rounded-[var(--radius-full)] text-xs font-medium border transition-all
            ${filters[p.key] === p.value ? 'bg-[var(--color-primary)]/10 border-[var(--color-primary)] text-[var(--color-primary)]' : 'bg-[var(--color-bg-surface)] border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-text-secondary)]'}`}>
          {p.label}
        </button>
      ))}
    </div>
  );
}
