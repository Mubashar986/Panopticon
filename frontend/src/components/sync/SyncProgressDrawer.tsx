import { useEffect } from 'react';
import { SyncStatusResponse } from '../../types/api';
interface Props { isOpen: boolean; onClose: () => void; status: SyncStatusResponse | null; onReindex: () => void; }

const PHASES = ['crawling', 'exporting', 'updating_sqlite', 'indexing_meilisearch'] as const;

export function SyncProgressDrawer({ isOpen, onClose, status, onReindex }: Props) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    if (isOpen) window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const currentPhaseIdx = status?.current_phase ? PHASES.indexOf(status.current_phase as any) : -1;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={onClose}></div>
      
      <div className="relative w-full max-w-md bg-[var(--color-bg-surface)] border-l border-[var(--color-border)] shadow-2xl flex flex-col h-full animate-[slideIn_0.25s_ease-out]">
        <div className="flex items-center justify-between p-[var(--space-6)] border-b border-[var(--color-border)]">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Sync Pipeline</h2>
          <button onClick={onClose} className="p-[var(--space-2)] rounded-[var(--radius-md)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-elevated)] hover:text-[var(--color-text-primary)] transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-[var(--space-6)]">
          <div className="mb-[var(--space-6)] p-[var(--space-4)] bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-lg)] border border-[var(--color-border)]" aria-live="polite">
            <p className="text-xs font-mono text-[var(--color-text-secondary)] mb-[var(--space-1)]">CURRENT STATUS</p>
            <p className="text-sm font-medium text-[var(--color-text-primary)]">{status?.progress_message || 'Idle and ready to crawl.'}</p>
          </div>

          <div className="space-y-[var(--space-4)]">
            {PHASES.map((phase, idx) => {
              const isActive = status?.current_phase === phase;
              const isComplete = status?.current_phase === 'idle' && status?.last_sync_stats ? true : idx < currentPhaseIdx;
              
              return (
                <div key={phase} className="flex items-center gap-[var(--space-4)]">
                  <div className={`flex-shrink-0 w-8 h-8 rounded-[var(--radius-full)] flex items-center justify-center border-2 transition-all
                    ${isComplete ? 'bg-[var(--color-success)] border-[var(--color-success)] text-white' : 
                      isActive ? 'bg-[var(--color-primary)]/20 border-[var(--color-primary)] text-[var(--color-primary)]' : 
                      'bg-[var(--color-bg-surface)] border-[var(--color-border)] text-[var(--color-text-secondary)]'}`}>
                    {isComplete ? <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7"></path></svg> :
                     isActive ? <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> :
                     <span className="text-xs font-bold">{idx + 1}</span>}
                  </div>
                  <div>
                    <p className={`text-sm font-medium capitalize ${isActive || isComplete ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-text-secondary)]'}`}>{phase.replace('_', ' ')}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {status?.last_sync_stats && (
            <div className="mt-[var(--space-8)] p-[var(--space-4)] bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-lg)] border border-[var(--color-border)]">
              <p className="text-xs font-mono text-[var(--color-text-secondary)] mb-[var(--space-3)]">LAST RUN STATISTICS</p>
              <div className="grid grid-cols-2 gap-[var(--space-2)] text-sm">
                <span className="text-[var(--color-text-secondary)]">Added:</span><span className="text-[var(--color-success)] font-mono">+{status.last_sync_stats.added}</span>
                <span className="text-[var(--color-text-secondary)]">Updated:</span><span className="text-[var(--color-text-primary)] font-mono">{status.last_sync_stats.updated}</span>
                <span className="text-[var(--color-text-secondary)]">Deleted:</span><span className="text-[var(--color-error)] font-mono">-{status.last_sync_stats.deleted}</span>
                <span className="text-[var(--color-text-secondary)]">Duration:</span><span className="text-[var(--color-text-primary)] font-mono">{status.last_sync_stats.duration_seconds.toFixed(1)}s</span>
              </div>
            </div>
          )}
        </div>

        <div className="p-[var(--space-6)] border-t border-[var(--color-border)]">
          <button onClick={onReindex} className="w-full py-[var(--space-3)] text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] bg-[var(--color-bg-surface-elevated)] hover:bg-[var(--color-border)] border border-[var(--color-border)] rounded-[var(--radius-md)] transition-colors">
            Re-index SQLite to Meilisearch
          </button>
        </div>
      </div>
    </div>
  );
}
