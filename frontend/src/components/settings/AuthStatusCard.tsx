import { AuthConfigResponse } from '../../types/api';
interface Props { config: AuthConfigResponse; onConnect: () => void; }

export function AuthStatusCard({ config, onConnect }: Props) {
  const isConnected = config.token_valid && !config.token_expired;

  return (
    <div className="p-[var(--space-4)] bg-[var(--color-bg-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-lg)]">
      <div className="flex items-center justify-between mb-[var(--space-4)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Google Drive Connection</h3>
        <span className={`px-[var(--space-2)] py-[var(--space-1)] rounded-[var(--radius-full)] text-[10px] font-bold uppercase
          ${isConnected ? 'bg-[var(--color-success)]/20 text-[var(--color-success)]' : 'bg-[var(--color-error)]/20 text-[var(--color-error)]'}`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {isConnected ? (
        <div className="space-y-[var(--space-2)] text-xs text-[var(--color-text-secondary)]">
          <p>Mode: <span className="text-[var(--color-text-primary)] font-mono">{config.auth_mode}</span></p>
          <p>Expires: <span className="text-[var(--color-text-primary)] font-mono">{config.token_expiry ? new Date(config.token_expiry).toLocaleString() : 'Unknown'}</span></p>
        </div>
      ) : (
        <button onClick={onConnect} className="w-full py-[var(--space-2)] bg-[var(--color-drive)] hover:bg-[var(--color-drive)]/90 text-white text-sm font-medium rounded-[var(--radius-md)] transition-colors flex items-center justify-center gap-[var(--space-2)]">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.701-6.033-6.032s2.701-6.032,6.033-6.032c1.498,0,2.866,0.549,3.921,1.453l2.814-2.814C17.503,2.988,15.139,2,12.545,2C7.021,2,2.543,6.478,2.543,12s4.478,10,10.002,10c8.396,0,10.249-7.85,9.426-11.748L12.545,10.239z"/></svg>
          Connect Google Drive
        </button>
      )}
    </div>
  );
}
