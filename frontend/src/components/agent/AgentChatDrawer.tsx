import { useEffect, useRef } from 'react';
import { useAgentChat } from '../../hooks/useAgentChat';
import { ChatMessageItem } from './ChatMessageItem';
import { QuickInquiryChips } from './QuickInquiryChips';
import { ChatInputBar } from './ChatInputBar';
import { ThreadHistorySidebar } from './ThreadHistorySidebar';

interface AgentChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AgentChatDrawer({ isOpen, onClose }: AgentChatDrawerProps) {
  const {
    messages,
    isStreaming,
    activeTool,
    selectedModel,
    setSelectedModel,
    threads,
    activeThreadId,
    isHistoryOpen,
    setIsHistoryOpen,
    selectThread,
    createNewThread,
    renameThread,
    deleteThread,
    sendMessage,
    cancelStreaming,
    clearChat,
  } = useAgentChat();

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  // Find active thread object for display
  const activeThread = threads.find((t) => t.id === activeThreadId);

  // Auto-scroll to bottom if user is already near the bottom
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (isNearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, isStreaming]);

  // Handle Escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-[var(--motion-duration-base)]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-Over Drawer Container (Expands when history sidebar is open) */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="agent-chat-title"
        className={`relative z-10 w-full ${
          isHistoryOpen ? 'max-w-[860px]' : 'max-w-[580px]'
        } bg-[var(--color-bg-canvas)] border-l border-[var(--color-border)] shadow-2xl flex flex-row h-full transition-all duration-[var(--motion-duration-base)] animate-[slideIn_var(--motion-duration-base)_ease-out]`}
      >
        {/* Collapsible Thread History Sidebar */}
        {isHistoryOpen && (
          <ThreadHistorySidebar
            threads={threads}
            activeThreadId={activeThreadId}
            isLoading={false}
            onSelectThread={(id) => selectThread(id)}
            onNewChat={createNewThread}
            onDeleteThread={(id) => deleteThread(id)}
            onRenameThread={(id, title) => renameThread(id, title)}
            onClose={() => setIsHistoryOpen(false)}
          />
        )}

        {/* Main Chat Pane */}
        <div className="flex-1 flex flex-col h-full min-w-0">
          {/* Drawer Header */}
          <header className="flex items-center justify-between px-[var(--space-4)] py-[var(--space-3)] border-b border-[var(--color-border)] bg-[var(--color-bg-surface)]">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-lg flex-shrink-0">✨</span>
              <div className="min-w-0">
                <h2
                  id="agent-chat-title"
                  className="text-sm font-bold text-[var(--color-text-primary)] truncate"
                >
                  {activeThread ? activeThread.title : 'Ask Panopticon'}
                </h2>
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="inline-flex items-center gap-1 text-[var(--color-success)] font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)] animate-pulse" />
                    Real-Time SSE
                  </span>
                  {activeThread && (
                    <span className="text-[var(--color-text-secondary)] font-mono text-[10px]">
                      ({activeThread.id})
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1.5 flex-shrink-0">
              {/* History Toggle Button */}
              <button
                type="button"
                onClick={() => setIsHistoryOpen((prev) => !prev)}
                title={isHistoryOpen ? 'Hide History' : 'View History'}
                className={`flex items-center gap-1 px-2 py-1 rounded-[var(--radius-md)] text-xs font-medium transition-colors cursor-pointer ${
                  isHistoryOpen
                    ? 'bg-[var(--color-brand-primary)] text-[var(--color-text-primary)]'
                    : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-surface-elevated)] border border-[var(--color-border)]'
                }`}
              >
                <span>🕒</span>
                <span className="hidden sm:inline">History</span>
                {threads.length > 0 && (
                  <span className="px-1 py-0.2 rounded-full text-[10px] bg-black/30 font-semibold">
                    {threads.length}
                  </span>
                )}
              </button>

              {/* + New Chat Button */}
              <button
                type="button"
                onClick={createNewThread}
                title="Start a fresh conversation"
                className="p-1.5 rounded-[var(--radius-md)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-surface-elevated)] transition-colors cursor-pointer"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
              </button>

              {messages.length > 0 && (
                <button
                  type="button"
                  onClick={clearChat}
                  title="Clear Current View"
                  className="p-1.5 rounded-[var(--radius-md)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-surface-elevated)] transition-colors cursor-pointer"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                </button>
              )}

              <button
                type="button"
                onClick={onClose}
                title="Close Drawer"
                className="p-1.5 rounded-[var(--radius-md)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-surface-elevated)] transition-colors cursor-pointer"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </header>

          {/* Message Feed Area */}
          <div
            ref={scrollContainerRef}
            className="flex-1 overflow-y-auto p-[var(--space-4)] space-y-[var(--space-2)]"
          >
            {messages.length === 0 ? (
              <QuickInquiryChips onSelect={(q) => sendMessage(q)} disabled={isStreaming} />
            ) : (
              messages.map((msg) => (
                <ChatMessageItem key={msg.id} message={msg} activeTool={activeTool} />
              ))
            )}
          </div>

          {/* Input Bar */}
          <ChatInputBar
            onSend={sendMessage}
            onCancel={cancelStreaming}
            isStreaming={isStreaming}
            selectedModel={selectedModel}
            onModelChange={setSelectedModel}
          />
        </div>
      </div>
    </div>
  );
}
