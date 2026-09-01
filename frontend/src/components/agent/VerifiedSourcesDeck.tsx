import { VerifiedCitationItem } from '../../types/agent';

interface VerifiedSourcesDeckProps {
  citations?: VerifiedCitationItem[];
}

export function VerifiedSourcesDeck({ citations = [] }: VerifiedSourcesDeckProps) {
  if (citations.length === 0) {
    return null;
  }

  const isSpreadsheet = (mime: string) => mime.includes('spreadsheet');

  return (
    <div className="mt-[var(--space-3)] pt-[var(--space-3)] border-t border-[var(--color-border)]/60">
      <div className="flex items-center gap-1.5 mb-[var(--space-2)]">
        <span className="text-[12px] font-semibold text-[var(--color-text-primary)]">
          Verified Sources ({citations.length})
        </span>
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[var(--radius-full)] bg-[rgba(16,185,129,0.12)] text-[var(--color-success)] text-[10px] font-medium">
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
          Grounded
        </span>
      </div>

      <div className="grid grid-cols-1 gap-[var(--space-2)]">
        {citations.map((item, idx) => (
          <div
            key={`${item.file_id}_${idx}`}
            className="p-[var(--space-3)] rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-canvas)] hover:border-[var(--color-primary)]/50 transition-colors"
          >
            <div className="flex items-start justify-between gap-[var(--space-2)] mb-1">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-base flex-shrink-0">
                  {isSpreadsheet(item.mime_type) ? '📊' : '📄'}
                </span>
                <span
                  className="text-[12px] font-semibold text-[var(--color-text-primary)] truncate"
                  title={item.document_name}
                >
                  {item.document_name}
                </span>
              </div>

              {item.verification_status === 'verified' ? (
                <span className="flex-shrink-0 text-[10px] font-medium text-[var(--color-success)] bg-[rgba(16,185,129,0.12)] px-1.5 py-0.5 rounded-[var(--radius-full)]">
                  {Math.round(item.confidence_score * 100)}% Match
                </span>
              ) : (
                <span className="flex-shrink-0 text-[10px] font-medium text-[var(--color-warning)] bg-[rgba(245,158,11,0.12)] px-1.5 py-0.5 rounded-[var(--radius-full)]">
                  Unverified
                </span>
              )}
            </div>

            {item.matched_snippet && (
              <p className="text-[11px] text-[var(--color-text-secondary)] italic bg-[var(--color-bg-surface-elevated)] p-2 rounded-[var(--radius-sm)] mb-2 border-l-2 border-[var(--color-primary)]">
                &ldquo;{item.matched_snippet}&rdquo;
              </p>
            )}

            <div className="flex justify-end">
              <a
                href={item.web_view_link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--color-drive)] hover:underline hover:text-[var(--color-primary-hover)] transition-colors cursor-pointer"
              >
                <span>Open in Google Drive</span>
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                  />
                </svg>
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
