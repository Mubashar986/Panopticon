interface QuickInquiryChipsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

const STARTER_PROMPTS = [
  {
    icon: '⚡',
    title: 'Recent Specification Changes',
    query: 'What changed in our technical specifications recently?',
  },
  {
    icon: '📊',
    title: 'Spreadsheets & Financials',
    query: 'Find all spreadsheets tracking project budgets, costs, or roadmaps.',
  },
  {
    icon: '🔐',
    title: 'Security & Auth Requirements',
    query: 'Compare authentication and authorization rules across active projects.',
  },
];

export function QuickInquiryChips({ onSelect, disabled }: QuickInquiryChipsProps) {
  return (
    <div className="p-[var(--space-4)] space-y-[var(--space-3)]">
      <div className="text-center py-[var(--space-4)]">
        <div className="w-12 h-12 rounded-full bg-[rgba(139,92,246,0.15)] text-[var(--color-primary)] flex items-center justify-center text-2xl mx-auto mb-[var(--space-2)] border border-[rgba(139,92,246,0.3)]">
          ✨
        </div>
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-1">
          Ask Panopticon Agent
        </h3>
        <p className="text-xs text-[var(--color-text-secondary)] max-w-xs mx-auto">
          Autonomous multi-step reasoning over internal Google Docs, Sheets, diffs, and semantic clauses.
        </p>
      </div>

      <div className="space-y-[var(--space-2)]">
        <div className="text-[11px] font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider px-1">
          Suggested Inquiries
        </div>
        {STARTER_PROMPTS.map((item, idx) => (
          <button
            key={idx}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(item.query)}
            className="w-full text-left p-[var(--space-3)] rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-surface-elevated)] hover:border-[var(--color-primary)] hover:bg-[rgba(139,92,246,0.08)] active:scale-[0.99] focus-visible:outline-2 focus-visible:outline-[var(--color-primary)] disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer group"
          >
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-sm">{item.icon}</span>
              <span className="text-[12px] font-medium text-[var(--color-text-primary)] group-hover:text-[var(--color-primary-hover)]">
                {item.title}
              </span>
            </div>
            <p className="text-[11px] text-[var(--color-text-secondary)] pl-6 truncate">
              {item.query}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}
