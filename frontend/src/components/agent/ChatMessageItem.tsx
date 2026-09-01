import { ChatMessage } from '../../types/agent';
import { ThoughtAccordion } from './ThoughtAccordion';
import { VerifiedSourcesDeck } from './VerifiedSourcesDeck';

interface ChatMessageItemProps {
  message: ChatMessage;
  activeTool?: string | null;
}

export function ChatMessageItem({ message, activeTool }: ChatMessageItemProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end mb-[var(--space-3)]">
        <div className="max-w-[85%] rounded-[var(--radius-lg)] rounded-br-[var(--radius-sm)] bg-[var(--color-primary)] text-white px-[var(--space-4)] py-[var(--space-3)] text-[13px] shadow-[var(--elevation-glow-primary)]">
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
          <div className="text-[10px] text-white/70 text-right mt-1">
            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    );
  }

  // Format simple markdown paragraphs, lists, bold text, and code
  const renderFormattedContent = (raw: string) => {
    return raw.split('\n\n').map((block, bIdx) => {
      const trimmed = block.trim();
      if (!trimmed) return null;

      // Bullet list items
      if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
        const items = trimmed.split('\n');
        return (
          <ul key={bIdx} className="list-disc pl-5 my-1.5 space-y-1">
            {items.map((it, iIdx) => {
              const cleanItem = it.replace(/^[*•-]\s+/, '');
              return (
                <li key={iIdx} className="text-[13px] leading-relaxed">
                  {renderInlineFormatting(cleanItem)}
                </li>
              );
            })}
          </ul>
        );
      }

      // Headers (### or ##)
      if (trimmed.startsWith('### ')) {
        return (
          <h4
            key={bIdx}
            className="text-[13px] font-bold text-[var(--color-text-primary)] mt-3 mb-1"
          >
            {trimmed.replace(/^###\s+/, '')}
          </h4>
        );
      }
      if (trimmed.startsWith('## ')) {
        return (
          <h3
            key={bIdx}
            className="text-[14px] font-bold text-[var(--color-primary)] mt-3 mb-1"
          >
            {trimmed.replace(/^##\s+/, '')}
          </h3>
        );
      }

      return (
        <p key={bIdx} className="my-1.5 text-[13px] leading-relaxed">
          {renderInlineFormatting(trimmed)}
        </p>
      );
    });
  };

  const renderInlineFormatting = (text: string) => {
    // Bold matching (**text**)
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, idx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={idx} className="font-semibold text-[var(--color-text-primary)]">
            {part.slice(2, -2)}
          </strong>
        );
      }
      // Inline code (`code`)
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code
            key={idx}
            className="px-1 py-0.5 rounded bg-[var(--color-bg-surface)] font-mono text-[12px] text-[var(--color-primary-hover)] border border-[var(--color-border)]"
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
  };

  return (
    <div className="flex gap-[var(--space-3)] mb-[var(--space-4)]">
      <div className="w-8 h-8 rounded-full bg-[rgba(139,92,246,0.2)] text-[var(--color-primary)] flex items-center justify-center text-sm font-bold flex-shrink-0 border border-[rgba(139,92,246,0.4)]">
        ✨
      </div>

      <div className="flex-1 min-w-0">
        <div className="rounded-[var(--radius-lg)] rounded-tl-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-4)] text-[13px] text-[var(--color-text-primary)] shadow-sm">
          {/* Reasoning & Tool Calling Accordion */}
          <ThoughtAccordion
            trace={message.trace}
            latencyMs={message.latencyMs}
            isLoading={message.isLoading}
            activeTool={activeTool}
          />

          {/* Answer Text Content */}
          {message.content ? (
            <div className="space-y-1">{renderFormattedContent(message.content)}</div>
          ) : message.isLoading ? (
            <div className="flex items-center gap-2 text-[var(--color-text-secondary)] text-xs py-2">
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-primary)] animate-bounce" />
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-primary)] animate-bounce [animation-delay:0.2s]" />
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-primary)] animate-bounce [animation-delay:0.4s]" />
              <span className="font-mono text-[11px] ml-1">Synthesizing grounded answer...</span>
            </div>
          ) : null}

          {/* Error Message if Any */}
          {message.error && (
            <div className="mt-2 p-2 rounded-[var(--radius-sm)] bg-[rgba(244,63,94,0.12)] border border-[var(--color-error)]/40 text-[var(--color-error)] text-[12px]">
              {message.error}
            </div>
          )}

          {/* Grounded Citation Cards Deck */}
          <VerifiedSourcesDeck citations={message.citations} />

          {/* Footer Metadata */}
          <div className="flex items-center justify-between text-[10px] text-[var(--color-text-secondary)] mt-[var(--space-3)] pt-[var(--space-2)] border-t border-[var(--color-border)]/40">
            <span>
              {message.model ? `Model: ${message.model}` : 'Panopticon Engine'}
            </span>
            <div className="flex items-center gap-2">
              {message.latencyMs && <span>{(message.latencyMs / 1000).toFixed(1)}s</span>}
              <span>
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
