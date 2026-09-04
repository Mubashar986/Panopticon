import { useVersionHistory } from '../../hooks/useVersionHistory';
import { DiffViewer } from './DiffViewer';

interface SplitPaneDiffViewerProps {
  fileId: string | null;
  fileName: string;
  onClose: () => void;
}

export function SplitPaneDiffViewer({ fileId, fileName, onClose }: SplitPaneDiffViewerProps) {
  const {
    versions,
    diffs,
    loading,
    error,
    selectedDiffId,
    selectedDiff,
    selectDiff,
  } = useVersionHistory(fileId);

  if (!fileId) return null;

  return (
    <div className="double-bezel mt-4 animate-fade-in">
      <div className="bezel-inner flex flex-col h-[560px] overflow-hidden">
        {/* Telemetry Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-zinc-950/60">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-zinc-100 truncate">
                  {fileName}
                </h3>
                <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] font-mono text-zinc-300 border border-white/5">
                  DIFF INSPECTOR
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 font-mono">
                {versions.length} Version Snapshots &bull; {diffs.length} Change Patches
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="w-7 h-7 rounded-md flex items-center justify-center text-zinc-400 hover:text-zinc-100 hover:bg-white/5 transition-colors cursor-pointer"
              title="Close diff inspector"
              aria-label="Close diff inspector"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Dual-Pane Content */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          {/* Revisions Sidebar */}
          <div className="w-full md:w-72 border-b md:border-b-0 md:border-r border-white/5 flex flex-col bg-zinc-950/40 shrink-0">
            <div className="px-3.5 py-2 border-b border-white/5 text-[10px] font-bold uppercase tracking-wider text-zinc-400 flex items-center justify-between">
              <span>Timeline</span>
              <span className="font-mono text-zinc-500">{versions.length} Records</span>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1.5 scrollbar-thin scrollbar-thumb-zinc-800">
              {loading && versions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 gap-2">
                  <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-xs text-zinc-500">Loading revisions...</span>
                </div>
              ) : error ? (
                <div className="p-3 text-xs text-rose-400 bg-rose-950/30 rounded-lg border border-rose-500/20">
                  {error}
                </div>
              ) : versions.length === 0 ? (
                <div className="p-4 text-center text-xs text-zinc-500">
                  No revisions recorded yet.
                </div>
              ) : (
                versions.map((ver, idx) => {
                  const matchingDiff = diffs.find((d) => d.to_version_id === ver.id);
                  const isSelected = selectedDiffId === matchingDiff?.id;
                  const isInitial = idx === versions.length - 1;

                  return (
                    <button
                      key={ver.id}
                      type="button"
                      onClick={() => matchingDiff && selectDiff(matchingDiff.id)}
                      disabled={!matchingDiff && !isInitial}
                      className={`w-full text-left p-2.5 rounded-lg border transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-emerald-500/10 border-emerald-500/40 text-white shadow-sm'
                          : matchingDiff
                          ? 'bg-zinc-900/40 border-white/5 text-zinc-400 hover:text-zinc-200 hover:border-white/10 hover:bg-zinc-900/80'
                          : 'bg-zinc-950/40 border-white/5 text-zinc-500 opacity-60 cursor-default'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1 mb-1">
                        <span className="font-mono font-semibold text-xs text-zinc-200">
                          v{ver.version_number}
                        </span>
                        {matchingDiff ? (
                          <div className="flex items-center gap-1 text-[10px] font-mono">
                            <span className="text-emerald-400">+{matchingDiff.lines_added}</span>
                            <span className="text-rose-400">-{matchingDiff.lines_removed}</span>
                          </div>
                        ) : (
                          <span className="text-[10px] font-mono uppercase text-zinc-500">
                            Baseline
                          </span>
                        )}
                      </div>

                      <div className="text-[11px] text-zinc-400 truncate">
                        {ver.editor || 'Anonymous editor'}
                      </div>

                      <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono mt-1">
                        <span>
                          {ver.modified_time
                            ? new Date(ver.modified_time).toLocaleDateString(undefined, {
                                month: 'short',
                                day: 'numeric',
                              })
                            : 'Initial'}
                        </span>
                        <span>{ver.word_count.toLocaleString()} words</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Diff Patch & AI Summary Viewport */}
          <div className="flex-1 overflow-hidden bg-black/40 flex flex-col">
            <DiffViewer
              diff={selectedDiff}
              fromVersionNumber={
                selectedDiff
                  ? versions.find((v) => v.id === selectedDiff.from_version_id)?.version_number
                  : undefined
              }
              toVersionNumber={
                selectedDiff
                  ? versions.find((v) => v.id === selectedDiff.to_version_id)?.version_number
                  : undefined
              }
            />
          </div>
        </div>
      </div>
    </div>
  );
}
