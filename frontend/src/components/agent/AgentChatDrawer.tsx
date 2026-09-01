import { useEffect, useRef } from 'react';
import { useAgentChat } from '../../hooks/useAgentChat';
import { ChatMessageItem } from './ChatMessageItem';
import { QuickInquiryChips } from './QuickInquiryChips';
import { ChatInputBar } from './ChatInputBar';

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
    sendMessage,
    cancelStreaming,
    clearChat,
  } = useAgentChat();

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

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

      {/* Slide-Over Drawer Container */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="agent-chat-title"
        className="relative z-10 w-full max-w-[560px] bg-[var(--color-bg-canvas)] border-l border-[var(--color-border)] shadow-2xl flex flex-col h-full animate-[slideIn_var(--motion-duration-base)_ease-out]"
      >
        {/* Drawer Header */}
        <header className="flex items-center justify-between px-[var(--space-4)] py-[var(--space-3)] border-b border-[var(--color-border)] bg-[var(--color-bg-surface)]">
          <div className="flex items-center gap-2">
            <span className="text-lg">✨</span>
            <div>
              <h2
                id="agent-chat-title"
                className="text-sm font-bold text-[var(--color-text-primary)]"
              >
                Ask Panopticon
              </h2>
              <span className="inline-flex items-center gap-1 text-[11px] text-[var(--color-success)] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)] animate-pulse" />
                Real-Time SSE Agent
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <button
                type="button"
                onClick={clearChat}
                title="Clear Conversation"
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
  );
}
