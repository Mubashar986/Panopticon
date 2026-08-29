import { useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { AuthStatusCard } from './AuthStatusCard';
import { CredentialUploader } from './CredentialUploader';

interface Props { isOpen: boolean; onClose: () => void; }

export function SettingsDrawer({ isOpen, onClose }: Props) {
  const { config, loading, switchMode, startOAuthPopup, uploadCredentials } = useAuth();

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    if (isOpen) window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose}></div>
      
      <div className="relative w-full max-w-md bg-[var(--color-bg-surface)] border-l border-[var(--color-border)] shadow-2xl flex flex-col h-full animate-[slideIn_0.25s_ease-out]">
        <div className="flex items-center justify-between p-[var(--space-6)] border-b border-[var(--color-border)]">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Settings & Auth</h2>
          <button onClick={onClose} className="p-[var(--space-2)] rounded-[var(--radius-md)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-elevated)] transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-[var(--space-6)] space-y-[var(--space-6)]">
          {loading ? (
            <div className="h-32 bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-lg)] animate-pulse" />
          ) : config ? (
            <>
              <AuthStatusCard config={config} onConnect={startOAuthPopup} />
              
              <div>
                <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-[var(--space-3)]">Authentication Mode</h3>
                <div className="flex gap-[var(--space-2)]">
                  <button onClick={() => switchMode('oauth')} className={`flex-1 py-[var(--space-2)] text-xs font-medium rounded-[var(--radius-md)] border transition-colors ${config.auth_mode === 'oauth' ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white' : 'bg-[var(--color-bg-surface-elevated)] border-[var(--color-border)] text-[var(--color-text-secondary)]'}`}>
                    Personal OAuth
                  </button>
                  <button onClick={() => switchMode('service_account')} className={`flex-1 py-[var(--space-2)] text-xs font-medium rounded-[var(--radius-md)] border transition-colors ${config.auth_mode === 'service_account' ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white' : 'bg-[var(--color-bg-surface-elevated)] border-[var(--color-border)] text-[var(--color-text-secondary)]'}`}>
                    Service Account (DWD)
                  </button>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-[var(--space-3)]">Upload Credentials</h3>
                <CredentialUploader onUpload={uploadCredentials} />
              </div>
            </>
          ) : (
            <p className="text-sm text-[var(--color-error)]">Failed to load configuration.</p>
          )}
        </div>
      </div>
    </div>
  );
}
