import React, { useEffect } from 'react';
import { useVersionHistory } from '../../hooks/useVersionHistory';
import { DiffViewer } from './DiffViewer';

interface VersionHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileId: string | null;
  fileName: string;
}

export function VersionHistoryModal({
  isOpen,
  onClose,
  fileId,
  fileName,
}: VersionHistoryModalProps) {
  const {
    versions,
    diffs,
    loading,
    error,
    selectedDiffId,
    selectedDiff,
    selectDiff,
  } = useVersionHistory(isOpen ? fileId : null);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !fileId) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="flex flex-col w-full max-w-5xl h-[85vh] bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center space-x-3 truncate">
            <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="truncate">
              <h2 id="modal-title" className="text-base font-semibold text-slate-900 dark:text-slate-100 truncate">
                {fileName}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Version History &amp; Temporal Revision Diffs
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Close (Esc)"
            aria-label="Close modal"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Modal Body: Dual Pane Layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Sidebar: Revisions Timeline */}
          <div className="w-80 border-r border-slate-200 dark:border-slate-800 flex flex-col bg-slate-50/30 dark:bg-slate-950/30">
            <div className="px-4 py-2.5 border-b border-slate-200/80 dark:border-slate-800/80 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Timeline ({versions.length} Snapshots)
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {loading && versions.length === 0 ? (
                <div className="flex justify-center p-8">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : error ? (
                <div className="p-4 text-xs text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/30 rounded-lg">
                  {error}
                </div>
              ) : versions.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-6">No version history recorded yet.</p>
              ) : (
                versions.map((ver, idx) => {
                  // Find diff matching this version as to_version
                  const matchingDiff = diffs.find((d) => d.to_version_id === ver.id);
                  const isSelected = matchingDiff ? matchingDiff.id === selectedDiffId : idx === 0 && !selectedDiffId;

                  return (
                    <button
                      key={ver.id}
                      onClick={() => matchingDiff && selectDiff(matchingDiff.id)}
                      className={`w-full text-left p-3 rounded-lg border transition-all ${
                        isSelected
                          ? 'bg-white dark:bg-slate-800 border-indigo-500 dark:border-indigo-500 shadow-sm ring-1 ring-indigo-500/20'
                          : 'bg-white/60 dark:bg-slate-900/60 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-1.5">
                          <span className="w-2 h-2 rounded-full bg-indigo-500 inline-block" />
                          <span>Version {ver.version_number}</span>
                        </span>
                        {matchingDiff && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                            +{matchingDiff.lines_added} / -{matchingDiff.lines_removed}
                          </span>
                        )}
                      </div>

                      <div className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-400 truncate">
                        {ver.editor || 'Anonymous / Google Drive'}
                      </div>

                      <div className="mt-1 flex items-center justify-between text-[10px] text-slate-400">
                        <span>{new Date(ver.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                        <span>{ver.word_count} words</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Panel: Diff Viewer */}
          <div className="flex-1 flex flex-col p-4 bg-slate-100/50 dark:bg-slate-950/50 overflow-hidden">
            {loading && !selectedDiff ? (
              <div className="flex flex-col items-center justify-center h-full">
                <div className="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mb-3" />
                <p className="text-xs text-slate-500">Loading revision delta...</p>
              </div>
            ) : (
              <DiffViewer
                diff={selectedDiff}
                toVersionNumber={versions.find((v) => v.id === selectedDiff?.to_version_id)?.version_number}
                fromVersionNumber={versions.find((v) => v.id === selectedDiff?.from_version_id)?.version_number}
              />
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs text-slate-500">
          <div className="flex items-center space-x-2">
            <span>Doc ID:</span>
            <code className="font-mono text-slate-700 dark:text-slate-300">{fileId}</code>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 font-medium text-slate-700 dark:text-slate-200 bg-slate-200/80 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
