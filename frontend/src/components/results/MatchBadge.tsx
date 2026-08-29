import { MatchedVia, MatchConfidence } from '../../types/api';
interface Props { matchedVia: MatchedVia; confidence: MatchConfidence; }

export function MatchBadge({ matchedVia, confidence }: Props) {
  const config = {
    tag: { label: 'TAG', color: 'bg-[var(--color-tag-match)]/20 text-[var(--color-tag-match)] border-[var(--color-tag-match)]/30' },
    title: { label: 'TITLE', color: 'bg-[var(--color-drive)]/20 text-[var(--color-drive)] border-[var(--color-drive)]/30' },
    content: { label: 'CONTENT', color: 'bg-[var(--color-text-secondary)]/20 text-[var(--color-text-secondary)] border-[var(--color-border)]' },
    owner: { label: 'OWNER', color: 'bg-[var(--color-success)]/20 text-[var(--color-success)] border-[var(--color-success)]/30' },
  };
  const { label, color } = config[matchedVia] || config.content;
  return (
    <span className={`inline-flex items-center px-[var(--space-2)] py-[var(--space-1)] rounded-[var(--radius-sm)] text-[10px] font-mono font-bold border ${color}`}>
      [{label}:{confidence.toUpperCase()}]
    </span>
  );
}
