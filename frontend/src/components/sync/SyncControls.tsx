import { SyncStatusResponse } from '../../types/api';
interface Props { status: SyncStatusResponse | null; onOpenDrawer: () => void; onSync: () => void; loading: boolean; }

export function SyncControls({ status, onOpenDrawer, onSync, loading }: Props) {
  const isSyncing = status?.is_syncing || loading;
  const lastSynced = status?.last_sync_time ? new Date(status.last_sync_time).toLocaleTimeString() : 'Never';

  return (
    <div className="flex items-center gap-[var(--space-3)]">
      <button onClick={onOpenDrawer} className="flex items-center gap-[var(--space-2)] px-[var(--space-3)] py-[var(--space-2)] text-xs font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] bg-[var(--color-bg-surface)] hover:bg-[var(--color-bg-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] transition-colors">
        <span className={`w-2 h-2 rounded-[var(--radius-full)] ${isSyncing ? 'bg-[var(--color-warning)] animate-pulse' : 'bg-[var(--color-success)]'}`}></span>
        Synced {lastSynced}
      </button>
      
      <button onClick={onSync} disabled={isSyncing}
        className="inline-flex items-center gap-[var(--space-2)] px-[var(--space-4)] py-[var(--space-2)] bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-sm font-medium rounded-[var(--radius-md)] transition-all disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 focus:ring-offset-[var(--color-bg-canvas)]">
        {isSyncing ? (
          <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
        )}
        Sync Now
      </button>
    </div>
  );
}
