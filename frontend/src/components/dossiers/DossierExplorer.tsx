import { useState } from 'react';
import { DossierSummary, DossierCreatePayload } from '../../types/api';
import { CreateDossierModal } from './CreateDossierModal';

interface DossierExplorerProps {
  dossiers: DossierSummary[];
  activeDossier: DossierSummary | null;
  onSelectDossier: (dossier: DossierSummary | null) => void;
  onCreateDossier: (payload: DossierCreatePayload) => Promise<DossierSummary>;
  totalDocumentsCount: number;
  loading: boolean;
  onOpenAgentChat: () => void;
}

export function DossierExplorer({
  dossiers,
  activeDossier,
  onSelectDossier,
  onCreateDossier,
  totalDocumentsCount,
  loading,
  onOpenAgentChat,
}: DossierExplorerProps) {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="double-bezel mb-6">
      <div className="bezel-inner p-3.5 sm:p-4">
        {/* Rail Top Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Workspace Projects
            </span>
            <span className="px-2 py-0.5 rounded-full bg-zinc-800 text-[10px] font-mono text-zinc-300 border border-white/5">
              {dossiers.length} Dossiers
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-white/10 hover:border-emerald-500/40 text-xs font-medium transition-all active:scale-95 cursor-pointer shadow-sm"
            >
              <span className="text-emerald-400 text-sm font-bold">+</span>
              <span>New Dossier</span>
            </button>
          </div>
        </div>

        {/* Dossier Pills Scroll / Flex Rail */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-zinc-700">
          {/* Global 'All Documents' Pill */}
          <button
            type="button"
            onClick={() => onSelectDossier(null)}
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all cursor-pointer whitespace-nowrap shrink-0 ${
              activeDossier === null
                ? 'bg-emerald-500/15 border-emerald-500/50 text-emerald-300 shadow-sm shadow-emerald-500/10'
                : 'bg-zinc-900/60 border-white/5 text-zinc-400 hover:text-zinc-200 hover:border-white/20'
            }`}
          >
            <span>🌐</span>
            <span>All Documents</span>
            <span className="px-1.5 py-0.2 rounded bg-black/40 text-[10px] font-mono opacity-80">
              {totalDocumentsCount}
            </span>
          </button>

          {/* Dossiers List */}
          {loading && dossiers.length === 0 ? (
            <div className="inline-flex items-center gap-2 px-3 py-1.5 text-xs text-zinc-500 italic">
              <span className="w-3 h-3 border-2 border-zinc-500 border-t-transparent rounded-full animate-spin" />
              <span>Loading dossiers...</span>
            </div>
          ) : (
            dossiers.map((dossier) => {
              const isActive = activeDossier?.id === dossier.id;
              const accentColor = dossier.color || '#10b981';

              return (
                <button
                  key={dossier.id}
                  type="button"
                  onClick={() => onSelectDossier(isActive ? null : dossier)}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all cursor-pointer whitespace-nowrap shrink-0 ${
                    isActive
                      ? 'bg-zinc-900/90 border-white/30 text-white shadow-md'
                      : 'bg-zinc-900/40 border-white/5 text-zinc-400 hover:text-zinc-200 hover:border-white/15'
                  }`}
                  style={
                    isActive
                      ? {
                          borderColor: `${accentColor}88`,
                          boxShadow: `0 0 12px -3px ${accentColor}44`,
                        }
                      : undefined
                  }
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: accentColor }}
                  />
                  <span className="font-medium text-zinc-200">{dossier.name}</span>
                  <span className="px-1.5 py-0.2 rounded bg-black/50 text-[10px] font-mono text-zinc-400">
                    {dossier.item_count}
                  </span>
                </button>
              );
            })
          )}
        </div>

        {/* Active Dossier Context Bar */}
        {activeDossier && (
          <div className="mt-3 pt-3 border-t border-white/5 flex flex-wrap items-center justify-between gap-3 animate-fade-in">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-emerald-500/20 text-emerald-400 text-xs">
                ✓
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-zinc-100">
                    Filtering by: {activeDossier.name}
                  </span>
                  <span className="text-[11px] text-zinc-400">
                    ({activeDossier.item_count} documents in scope)
                  </span>
                </div>
                {activeDossier.description && (
                  <p className="text-[11px] text-zinc-400 line-clamp-1">
                    {activeDossier.description}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onOpenAgentChat}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-xs font-medium transition-all active:scale-95 cursor-pointer"
              >
                <span>✨</span>
                <span>Ask Dossier</span>
              </button>
              <button
                type="button"
                onClick={() => onSelectDossier(null)}
                className="px-2.5 py-1 rounded-md text-[11px] text-zinc-400 hover:text-zinc-200 hover:bg-white/5 transition-colors cursor-pointer"
              >
                Clear Scope (Show All)
              </button>
            </div>
          </div>
        )}
      </div>

      <CreateDossierModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreate={onCreateDossier}
      />
    </div>
  );
}
