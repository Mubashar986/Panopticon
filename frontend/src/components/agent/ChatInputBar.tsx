import { useState, useRef, useEffect, KeyboardEvent } from 'react';

interface ChatInputBarProps {
  onSend: (text: string) => void;
  onCancel: () => void;
  isStreaming: boolean;
  disabled?: boolean;
  selectedModel: string | null;
  onModelChange: (model: string | null) => void;
}

const AVAILABLE_MODELS = [
  { id: '', label: 'Default (Fast Reasoning)' },
  { id: 'minimax/minimax-m3:free', label: 'MiniMax M3 (Free)' },
  { id: 'nvidia/nemotron-3-ultra-550b-a55b:free', label: 'Nvidia Nemotron 3 Ultra free' },
  { id: 'deepseek/deepseek-chat', label: 'DeepSeek Chat' },
  { id: 'google/gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
];

export function ChatInputBar({
  onSend,
  onCancel,
  isStreaming,
  disabled,
  selectedModel,
  onModelChange,
}: ChatInputBarProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSend(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  return (
    <div className="p-[var(--space-4)] border-t border-[var(--color-border)] bg-[var(--color-bg-surface)]">
      {/* Model Selection Seam */}
      <div className="flex items-center justify-between mb-[var(--space-2)] text-[11px] text-[var(--color-text-secondary)]">
        <div className="flex items-center gap-1.5">
          <span>Model:</span>
          <select
            value={selectedModel || ''}
            onChange={(e) => onModelChange(e.target.value || null)}
            disabled={isStreaming}
            className="bg-[var(--color-bg-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-sm)] px-1.5 py-0.5 text-[11px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-primary)] cursor-pointer disabled:opacity-50"
          >
            {AVAILABLE_MODELS.map((m) => (
              <option key={m.id} value={m.id} className="bg-[var(--color-bg-surface)]">
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <span className="text-[10px] text-[var(--color-text-secondary)]">
          Press Enter to send, Shift+Enter for newline
        </span>
      </div>

      {/* Input Form Box */}
      <div className="relative flex items-end rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface-elevated)] focus-within:border-[var(--color-primary)] focus-within:ring-1 focus-within:ring-[var(--color-primary)] transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming || disabled}
          placeholder={isStreaming ? 'Agent is reasoning...' : 'Ask about documents, diffs, clauses...'}
          rows={1}
          className="w-full resize-none bg-transparent px-[var(--space-3)] py-[var(--space-3)] text-[13px] text-[var(--color-text-primary)] placeholder-[var(--color-text-secondary)] focus:outline-none disabled:opacity-50 max-h-[120px]"
        />

        <div className="p-2 flex-shrink-0">
          {isStreaming ? (
            <button
              type="button"
              onClick={onCancel}
              title="Stop Generation"
              className="flex items-center justify-center w-8 h-8 rounded-full bg-[var(--color-error)] text-white hover:opacity-90 active:scale-95 transition-all cursor-pointer shadow-sm"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="1.5" />
              </svg>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || disabled}
              title="Send Message"
              className="flex items-center justify-center w-8 h-8 rounded-full bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer shadow-[var(--elevation-glow-primary)]"
            >
              <svg className="w-4 h-4 transform rotate-90" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
