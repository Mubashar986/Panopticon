import { useEffect, useRef } from 'react';
import { useAgentChat } from '../../hooks/useAgentChat';
import { ChatMessageItem } from './ChatMessageItem';
import { QuickInquiryChips } from './QuickInquiryChips';
import { ChatInputBar } from './ChatInputBar';
import { ThreadHistorySidebar } from './ThreadHistorySidebar';
import { DossierSummary } from '../../types/api';

interface AgentChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeDossier?: DossierSummary | null;
  onClearDossierScope?: () => void;
}

export function AgentChatDrawer({
  isOpen,
  onClose,
  activeDossier,
  onClearDossierScope,
}: AgentChatDrawerProps) {
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
  } = useAgentChat(activeDossier?.id);

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
        className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity duration-200"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-Over Drawer Container */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="agent-chat-title"
        className={`relative z-10 w-full ${
          isHistoryOpen ? 'max-w-[860px]' : 'max-w-[580px]'
        } bg-zinc-950 border-l border-white/10 shadow-2xl flex flex-row h-full transition-all duration-200 animate-[slideIn_200ms_ease-out]`}
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
        <div className="flex-1 flex flex-col h-full min-w-0 bg-zinc-950">
          {/* Drawer Header */}
          <header className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-zinc-900/60">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="text-lg shrink-0">✨</span>
              <div className="min-w-0">
                <h2
                  id="agent-chat-title"
                  className="text-sm font-bold text-zinc-100 truncate"
                >
                  {activeThread ? activeThread.title : activeDossier ? `Ask ${activeDossier.name}` : 'Ask Panopticon'}
                </h2>
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Real-Time SSE
                  </span>
                  {activeThread && (
                    <span className="text-zinc-500 font-mono text-[10px]">
                      ({activeThread.id})
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              {/* History Toggle Button */}
              <button
                type="button"
                onClick={() => setIsHistoryOpen((prev) => !prev)}
                title={isHistoryOpen ? 'Hide History' : 'View History'}
                className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                  isHistoryOpen
                    ? 'bg-zinc-800 text-zinc-100 border border-white/20'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 border border-white/5'
                }`}
              >
                <span>🕒</span>
                <span className="hidden sm:inline">History</span>
                {threads.length > 0 && (
                  <span className="px-1 py-0.2 rounded-full text-[10px] bg-black/40 font-semibold font-mono">
                    {threads.length}
                  </span>
                )}
              </button>

              {/* + New Chat Button */}
              <button
                type="button"
                onClick={createNewThread}
                title="Start a fresh conversation"
                className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors cursor-pointer"
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
                  className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors cursor-pointer"
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
                className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors cursor-pointer"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </header>

          {/* Dossier Container Isolation Banner */}
          {activeDossier && (
            <div className="px-4 py-2 bg-emerald-950/40 border-b border-emerald-500/20 flex items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
                <span className="font-semibold text-emerald-300 truncate">
                  Dossier Isolated: {activeDossier.name}
                </span>
                <span className="text-[10px] font-mono text-emerald-500/80 shrink-0">
                  ({activeDossier.item_count} files)
                </span>
              </div>
              {onClearDossierScope && (
                <button
                  type="button"
                  onClick={onClearDossierScope}
                  className="text-[10px] font-mono text-emerald-400 hover:text-emerald-200 underline cursor-pointer shrink-0"
                >
                  Switch to Global
                </button>
              )}
            </div>
          )}

          {/* Message Feed Area */}
          <div
            ref={scrollContainerRef}
            className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-thin scrollbar-thumb-zinc-800"
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
