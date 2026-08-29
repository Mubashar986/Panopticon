import { SearchItemResponse } from '../../types/api';
import { MatchBadge } from './MatchBadge';
import { ExportMenu } from './ExportMenu';
import { StaleBadge } from '../common/StaleBadge';
interface Props { item: SearchItemResponse; }

export function ResultCard({ item }: Props) {
  const isStale = item.modified_time && (new Date().getTime() - new Date(item.modified_time).getTime()) > 90 * 24 * 60 * 60 * 1000;

  return (
    <div className="group bg-[var(--color-bg-surface)] border border-[var(--color-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] hover:border-[var(--color-primary)]/50 hover:shadow-[var(--elevation-card-hover)] transition-all duration-[var(--motion-duration-base)]">
      <div className="flex items-start justify-between gap-[var(--space-4)] mb-[var(--space-3)]">
        <div className="flex items-center gap-[var(--space-3)] min-w-0">
          <img src={item.icon_link || 'https://ssl.gstatic.com/docs/documents/documents/kix-favicon7.ico'} alt="" className="w-6 h-6 flex-shrink-0" />
          <h3 className="text-base font-semibold text-[var(--color-text-primary)] truncate group-hover:text-[var(--color-primary)] transition-colors" dangerouslySetInnerHTML={{ __html: item.highlighted_name || item.name }} />
          <MatchBadge matchedVia={item.matched_via} confidence={item.confidence} />
          {isStale && <StaleBadge />}
        </div>
        <ExportMenu exportLinks={item.export_links} />
      </div>

      {item.highlighted_snippet && (
        <p className="text-sm text-[var(--color-text-secondary)] line-clamp-2 mb-[var(--space-4)] leading-relaxed" dangerouslySetInnerHTML={{ __html: item.highlighted_snippet }} />
      )}

      <div className="flex items-center justify-between pt-[var(--space-3)] border-t border-[var(--color-border)]">
        <div className="flex items-center gap-[var(--space-4)] text-xs text-[var(--color-text-secondary)]">
          <span className="flex items-center gap-[var(--space-1)]">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
            {item.owner}
          </span>
          <span className="flex items-center gap-[var(--space-1)]">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            {item.modified_time ? new Date(item.modified_time).toLocaleDateString() : 'Unknown'}
          </span>
          {item.project_tags && item.project_tags.length > 0 && (
            <span className="px-[var(--space-2)] py-[var(--space-1)] bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-sm)] font-mono">#{item.project_tags[0]}</span>
          )}
        </div>

        <a href={item.view_url || '#'} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-[var(--space-2)] px-[var(--space-3)] py-[var(--space-1)] bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-xs font-medium rounded-[var(--radius-md)] transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 focus:ring-offset-[var(--color-bg-surface)]">
          View in Drive
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
        </a>
      </div>
    </div>
  );
}
