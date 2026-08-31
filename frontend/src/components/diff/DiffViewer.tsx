import React from 'react';
import { DocumentDiff } from '../../types/api';

interface DiffViewerProps {
  diff: DocumentDiff | null;
  fromVersionNumber?: number;
  toVersionNumber?: number;
}

export function DiffViewer({ diff, fromVersionNumber, toVersionNumber }: DiffViewerProps) {
  if (!diff) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center h-full">
        <svg className="w-12 h-12 text-slate-400 dark:text-slate-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Initial Snapshot</p>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
          This is the initial baseline snapshot. No prior revisions or diffs exist for this document.
        </p>
      </div>
    );
  }

  const lines = diff.patch_text.split('\n');

  return (
    <div className="flex flex-col h-full bg-slate-900 text-slate-100 rounded-lg overflow-hidden border border-slate-700 shadow-inner">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-800/80 border-b border-slate-700">
        <div className="flex items-center space-x-3">
          <span className="text-xs font-semibold text-slate-300">
            {fromVersionNumber ? `v${fromVersionNumber}` : 'Previous'} → {toVersionNumber ? `v${toVersionNumber}` : 'Latest'}
          </span>
          <div className="flex items-center space-x-2 text-xs">
            <span className="inline-flex items-center px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono font-medium">
              +{diff.lines_added}
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono font-medium">
              -{diff.lines_removed}
            </span>
          </div>
        </div>
        <div className="text-xs text-slate-400">
          {new Date(diff.created_at).toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>

      {/* AI Semantic Summary Banner */}
      {diff.ai_summary && (
        <div className="px-4 py-2.5 bg-indigo-950/60 border-b border-indigo-800/60 flex items-start space-x-2.5">
          <svg className="w-4 h-4 text-indigo-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <div className="text-xs text-indigo-200 leading-relaxed">
            <span className="font-semibold text-indigo-300 mr-1.5">AI Summary:</span>
            {diff.ai_summary}
          </div>
        </div>
      )}

      {/* Diff Code View */}
      <div className="flex-1 overflow-auto p-3 font-mono text-xs leading-5 select-text">
        {lines.map((line, idx) => {
          let lineBg = 'hover:bg-slate-800/50 text-slate-300';
          let indicator = ' ';

          if (line.startsWith('+++') || line.startsWith('---')) {
            lineBg = 'text-slate-500 font-semibold select-none';
          } else if (line.startsWith('@@')) {
            lineBg = 'bg-blue-950/40 text-blue-300 font-semibold border-y border-blue-900/30 my-1 py-0.5';
          } else if (line.startsWith('+')) {
            lineBg = 'bg-emerald-950/40 text-emerald-300';
            indicator = '+';
          } else if (line.startsWith('-')) {
            lineBg = 'bg-rose-950/40 text-rose-300';
            indicator = '-';
          }

          return (
            <div key={idx} className={`flex items-start px-2 py-0.5 rounded-sm ${lineBg}`}>
              <span className="w-8 text-right text-slate-600 select-none mr-3 shrink-0">{idx + 1}</span>
              <span className="w-3 text-center select-none font-bold mr-1 shrink-0">{indicator}</span>
              <span className="whitespace-pre-wrap break-all flex-1">{line.slice(1) || ' '}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
