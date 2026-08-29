interface Props { mode: 'fuzzy' | 'tag' | 'exact'; setMode: (m: 'fuzzy' | 'tag' | 'exact') => void; }

export function ModeSelector({ mode, setMode }: Props) {
  const modes = [
    { id: 'fuzzy', label: 'Fuzzy' }, { id: 'tag', label: 'Tag' }, { id: 'exact', label: 'Exact' }
  ];
  return (
    <div className="flex gap-[var(--space-2)] bg-[var(--color-bg-surface)] p-[var(--space-1)] rounded-[var(--radius-md)] border border-[var(--color-border)] w-fit">
      {modes.map((m) => (
        <button key={m.id} onClick={() => setMode(m.id as any)}
          className={`px-[var(--space-4)] py-[var(--space-2)] rounded-[var(--radius-sm)] text-sm font-medium transition-all
            ${mode === m.id ? 'bg-[var(--color-primary)] text-white shadow-[var(--elevation-glow-primary)]' : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-surface-elevated)]'}`}>
          {m.label}
        </button>
      ))}
    </div>
  );
}
