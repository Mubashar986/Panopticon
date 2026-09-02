import { useState } from 'react';
import { AgentThread } from '../../types/agent';

interface ThreadHistorySidebarProps {
  threads: AgentThread[];
  activeThreadId: string | null;
  isLoading: boolean;
  onSelectThread: (threadId: string) => void;
  onNewChat: () => void;
  onDeleteThread: (threadId: string) => void;
  onRenameThread: (threadId: string, newTitle: string) => void;
  onClose: () => void;
}

function formatRelativeTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);

    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return 'Recently';
  }
}

export function ThreadHistorySidebar({
  threads,
  activeThreadId,
  isLoading,
  onSelectThread,
  onNewChat,
  onDeleteThread,
  onRenameThread,
  onClose,
}: ThreadHistorySidebarProps) {
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const startRename = (thread: AgentThread, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingThreadId(thread.id);
    setEditTitle(thread.title);
  };

  const handleSaveRename = (threadId: string) => {
    if (editTitle.trim()) {
      onRenameThread(threadId, editTitle.trim());
    }
    setEditingThreadId(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent, threadId: string) => {
    if (e.key === 'Enter') {
      handleSaveRename(threadId);
    } else if (e.key === 'Escape') {
      setEditingThreadId(null);
    }
  };

  return (
    <aside
      aria-label="Conversation History"
      className="w-72 bg-[var(--color-bg-surface)] border-r border-[var(--color-border)] flex flex-col h-full z-20 transition-all duration-[var(--motion-duration-base)]"
    >
      {/* Sidebar Header */}
      <div className="flex items-center justify-between px-[var(--space-3)] py-[var(--space-3)] border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <span className="text-sm">🕒</span>
          <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">
            Chat History
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          title="Close History"
          className="p-1 rounded-[var(--radius-md)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-surface-elevated)] transition-colors cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* New Chat Button */}
      <div className="p-[var(--space-3)] border-b border-[var(--color-border)]">
        <button
          type="button"
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-[var(--space-3)] py-[var(--space-2)] rounded-[var(--radius-md)] bg-[var(--color-brand-primary)] hover:bg-[var(--color-brand-primary-hover)] active:opacity-90 text-[var(--color-text-primary)] text-xs font-semibold shadow-sm transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-primary)] focus:ring-offset-1"
        >
          <span>✨</span>
          <span>+ New Conversation</span>
        </button>
      </div>

      {/* Threads List */}
      <div className="flex-1 overflow-y-auto p-[var(--space-2)] space-y-1">
        {isLoading ? (
          <div className="p-[var(--space-4)] text-center text-xs text-[var(--color-text-secondary)] animate-pulse">
            Loading conversations...
          </div>
        ) : threads.length === 0 ? (
          <div className="p-[var(--space-4)] text-center text-xs text-[var(--color-text-secondary)] space-y-1">
            <p>No saved conversations.</p>
            <p className="text-[11px] opacity-75">Start a chat to keep history here.</p>
          </div>
        ) : (
          threads.map((thread) => {
            const isActive = thread.id === activeThreadId;
            const isEditing = editingThreadId === thread.id;
            const isConfirmingDelete = confirmDeleteId === thread.id;

            return (
              <div
                key={thread.id}
                onClick={() => !isEditing && onSelectThread(thread.id)}
                className={`group relative flex flex-col p-[var(--space-2)] rounded-[var(--radius-md)] transition-all cursor-pointer border ${
                  isActive
                    ? 'bg-[var(--color-bg-surface-elevated)] border-[var(--color-brand-primary)] shadow-sm'
                    : 'border-transparent hover:bg-[var(--color-bg-surface-elevated)] hover:border-[var(--color-border)]'
                }`}
              >
                {/* Title or Inline Edit */}
                {isEditing ? (
                  <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e, thread.id)}
                      onBlur={() => handleSaveRename(thread.id)}
                      autoFocus
                      className="w-full px-1.5 py-0.5 text-xs bg-[var(--color-bg-canvas)] text-[var(--color-text-primary)] border border-[var(--color-brand-primary)] rounded-[var(--radius-sm)] focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => handleSaveRename(thread.id)}
                      className="text-[10px] text-[var(--color-success)] p-0.5"
                    >
                      ✓
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center justify-between gap-1">
                    <span
                      title={thread.title}
                      className={`text-xs font-medium truncate flex-1 ${
                        isActive ? 'text-[var(--color-text-primary)] font-semibold' : 'text-[var(--color-text-secondary)] group-hover:text-[var(--color-text-primary)]'
                      }`}
                    >
                      {thread.title}
                    </span>

                    {/* Action buttons (Rename & Delete) */}
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={(e) => startRename(thread, e)}
                        title="Rename title"
                        className="p-1 rounded text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-canvas)]"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                          />
                        </svg>
                      </button>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDeleteId(thread.id);
                        }}
                        title="Delete conversation"
                        className="p-1 rounded text-[var(--color-text-secondary)] hover:text-[var(--color-error)] hover:bg-[var(--color-bg-canvas)]"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      </button>
                    </div>
                  </div>
                )}

                {/* Sub-meta: time and message count */}
                <div className="flex items-center justify-between mt-1 text-[10px] text-[var(--color-text-secondary)]">
                  <span>{formatRelativeTime(thread.updated_at)}</span>
                  {thread.message_count > 0 && (
                    <span className="px-1 py-0.2 rounded bg-[var(--color-bg-canvas)] border border-[var(--color-border)] text-[9px]">
                      {thread.message_count} {thread.message_count === 1 ? 'msg' : 'msgs'}
                    </span>
                  )}
                </div>

                {/* Confirm Delete Overlay */}
                {isConfirmingDelete && (
                  <div
                    className="absolute inset-0 bg-[var(--color-bg-surface-elevated)] border border-[var(--color-error)] rounded-[var(--radius-md)] p-2 flex items-center justify-between z-10 animate-[fadeIn_150ms_ease-in]"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <span className="text-[10px] font-semibold text-[var(--color-error)]">
                      Delete chat?
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => {
                          onDeleteThread(thread.id);
                          setConfirmDeleteId(null);
                        }}
                        className="px-2 py-0.5 rounded bg-[var(--color-error)] text-[var(--color-text-primary)] text-[10px] font-bold hover:opacity-90"
                      >
                        Yes
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteId(null)}
                        className="px-2 py-0.5 rounded bg-[var(--color-bg-canvas)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] text-[10px]"
                      >
                        No
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
