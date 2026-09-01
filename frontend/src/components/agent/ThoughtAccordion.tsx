import { useState } from 'react';
import { AgentStepTraceItem } from '../../types/agent';

interface ThoughtAccordionProps {
  trace?: AgentStepTraceItem[];
  latencyMs?: number;
  isLoading?: boolean;
  activeTool?: string | null;
}

export function ThoughtAccordion({
  trace = [],
  latencyMs,
  isLoading,
  activeTool,
}: ThoughtAccordionProps) {
  const [isOpen, setIsOpen] = useState(isLoading || false);

  if (trace.length === 0 && !isLoading) {
    return null;
  }

  const getToolIcon = (name: string) => {
    switch (name) {
      case 'search_index':
        return '🔍';
      case 'get_document_diff':
        return '📄';
      case 'get_file_metadata':
        return 'ℹ️';
      case 'semantic_chunk_search':
        return '🧬';
      default:
        return '⚙️';
    }
  };

  const getToolDisplayName = (name: string) => {
    switch (name) {
      case 'search_index':
        return 'Search Index';
      case 'get_document_diff':
        return 'Inspect Diff';
      case 'get_file_metadata':
        return 'File Metadata';
      case 'semantic_chunk_search':
        return 'Semantic Chunk Search';
      default:
        return name;
    }
  };

  return (
    <div className="mb-[var(--space-3)] rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-surface-elevated)] overflow-hidden transition-all">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full flex items-center justify-between px-[var(--space-3)] py-[var(--space-2)] text-[12px] font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[rgba(139,92,246,0.06)] transition-colors cursor-pointer select-none"
      >
        <div className="flex items-center gap-[var(--space-2)]">
          {isLoading ? (
            <span className="inline-flex items-center gap-1.5 text-[var(--color-primary)] font-semibold animate-pulse">
              <span className="w-2 h-2 rounded-full bg-[var(--color-primary)] animate-ping" />
              {activeTool ? `Executing ${getToolDisplayName(activeTool)}...` : 'Reasoning...'}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[var(--color-text-secondary)]">
              <span>🧠</span>
              <span>
                Thought for {latencyMs ? `${(latencyMs / 1000).toFixed(1)}s` : 'a few seconds'} (
                {trace.length} tool{trace.length === 1 ? '' : 's'} used)
              </span>
            </span>
          )}
        </div>

        <svg
          className={`w-3.5 h-3.5 transform transition-transform duration-[var(--motion-duration-base)] ${
            isOpen ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-[var(--space-3)] pb-[var(--space-3)] pt-[var(--space-1)] space-y-[var(--space-2)] border-t border-[var(--color-border)]/50 text-[11px]">
          {trace.map((item, idx) => (
            <div
              key={`${item.step}_${item.tool_name}_${idx}`}
              className="p-[var(--space-2)] rounded-[var(--radius-sm)] bg-[var(--color-bg-canvas)] border border-[var(--color-border)]/60"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="inline-flex items-center gap-1 font-semibold text-[var(--color-primary)]">
                  <span>{getToolIcon(item.tool_name)}</span>
                  <span>{getToolDisplayName(item.tool_name)}</span>
                </span>
                <span className="text-[10px] text-[var(--color-text-secondary)]">
                  Step {item.step}
                </span>
              </div>

              {Object.keys(item.arguments).length > 0 && (
                <div className="text-[10px] text-[var(--color-text-secondary)] font-mono bg-[var(--color-bg-surface)] px-1.5 py-0.5 rounded mb-1 truncate">
                  {JSON.stringify(item.arguments)}
                </div>
              )}

              <p className="text-[11px] text-[var(--color-text-primary)] font-mono whitespace-pre-wrap leading-relaxed">
                {item.output_summary}
              </p>
            </div>
          ))}

          {isLoading && activeTool && (
            <div className="p-[var(--space-2)] rounded-[var(--radius-sm)] bg-[var(--color-bg-canvas)] border border-[var(--color-primary)]/40 animate-pulse">
              <span className="inline-flex items-center gap-1 text-[var(--color-primary)] text-[11px] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)]" />
                Running {getToolDisplayName(activeTool)}...
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
