import { useState, useMemo } from 'react';
import { useSearch } from './hooks/useSearch';
import { useSync } from './hooks/useSync';
import { useDocuments } from './hooks/useDocuments';
import { useDossiers } from './hooks/useDossiers';
import { DocumentResponseItem } from './types/api';
import { Header } from './components/navigation/Header';
import { DossierExplorer } from './components/dossiers/DossierExplorer';
import { SearchBar } from './components/search/SearchBar';
import { ModeSelector } from './components/search/ModeSelector';
import { FilterBar } from './components/search/FilterBar';
import { ResultsList } from './components/results/ResultsList';
import { SyncProgressDrawer } from './components/sync/SyncProgressDrawer';
import { SettingsDrawer } from './components/settings/SettingsDrawer';
import { DenseDocumentTable } from './components/directory/DenseDocumentTable';
import { PaginationBar } from './components/directory/PaginationBar';
import { ViewToggle, ViewMode } from './components/directory/ViewToggle';
import { SplitPaneDiffViewer } from './components/diff/SplitPaneDiffViewer';
import { VersionHistoryModal } from './components/diff/VersionHistoryModal';
import { AgentChatDrawer } from './components/agent/AgentChatDrawer';

export default function Dashboard() {
  const search = useSearch();
  const sync = useSync();
  const docs = useDocuments();
  const dossierState = useDossiers();

  const [syncDrawerOpen, setSyncDrawerOpen] = useState(false);
  const [settingsDrawerOpen, setSettingsDrawerOpen] = useState(false);
  const [agentChatOpen, setAgentChatOpen] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [selectedDocForDiff, setSelectedDocForDiff] = useState<DocumentResponseItem | null>(null);
  const [selectedDocForHistory, setSelectedDocForHistory] = useState<DocumentResponseItem | null>(null);

  const isSearching = search.query.trim().length > 0;

  // Filter documents when a dossier is actively selected
  const displayedDocuments = useMemo(() => {
    if (!dossierState.activeDossier) {
      return docs.documents;
    }
    // If active dossier is selected, filter by files belonging to this dossier
    return docs.documents.filter((doc) => dossierState.activeDossierFileIds.has(doc.id));
  }, [docs.documents, dossierState.activeDossier, dossierState.activeDossierFileIds]);

  return (
    <div className="min-h-screen bg-[var(--color-bg-canvas)] text-[var(--color-text-primary)] p-4 sm:p-6 lg:p-8 font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      <div className="max-w-7xl mx-auto">
        {/* Precision Cockpit Header */}
        <Header
          isLiveConnected={docs.isLiveConnected}
          totalDocuments={docs.totalCount}
          totalDossiers={dossierState.dossiers.length}
          syncStatus={sync.status}
          syncLoading={sync.loading}
          onOpenSyncDrawer={() => setSyncDrawerOpen(true)}
          onTriggerSync={() => sync.triggerSync()}
          onOpenSettings={() => setSettingsDrawerOpen(true)}
          onOpenAgentChat={() => setAgentChatOpen(true)}
        />

        {/* Project Dossier Rail / Workspace Selector */}
        <DossierExplorer
          dossiers={dossierState.dossiers}
          activeDossier={dossierState.activeDossier}
          onSelectDossier={dossierState.setActiveDossier}
          onCreateDossier={dossierState.createDossier}
          totalDocumentsCount={docs.totalCount}
          loading={dossierState.loading}
          onOpenAgentChat={() => setAgentChatOpen(true)}
        />

        {/* Search & Telemetry Controls */}
        <div className="space-y-4 mb-6">
          <SearchBar query={search.query} setQuery={search.setQuery} loading={search.loading} />

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            {isSearching ? (
              <ModeSelector mode={search.mode} setMode={search.setMode} />
            ) : (
              <ViewToggle viewMode={viewMode} onViewModeChange={setViewMode} />
            )}
            <FilterBar filters={search.filters} setFilters={search.setFilters} />
          </div>
        </div>

        {/* Main Workspace Stage */}
        {isSearching ? (
          /* Search Mode: Results List */
          <ResultsList
            data={search.data}
            loading={search.loading}
            error={search.error}
            query={search.query}
            onRetry={search.retry}
          />
        ) : (
          /* Default Directory Mode: High-Density Document Table */
          <div className="space-y-0">
            <DenseDocumentTable
              documents={displayedDocuments}
              loading={docs.loading || dossierState.filesLoading}
              sortBy={docs.sortBy}
              onSortChange={docs.setSortBy}
              recentlyModifiedIds={docs.recentlyModifiedIds}
              onViewHistory={(doc) => setSelectedDocForHistory(doc)}
              onInspectDiff={(doc) => setSelectedDocForDiff(doc)}
            />

            {!dossierState.activeDossier && (
              <PaginationBar
                totalCount={docs.totalCount}
                limit={docs.limit}
                offset={docs.offset}
                onPageChange={docs.setOffset}
                onLimitChange={(newLimit) => {
                  docs.setLimit(newLimit);
                  docs.setOffset(0);
                }}
                loading={docs.loading}
              />
            )}
          </div>
        )}

        {/* Docked Split-Pane Diff Inspector */}
        {selectedDocForDiff && (
          <SplitPaneDiffViewer
            fileId={selectedDocForDiff.id}
            fileName={selectedDocForDiff.name}
            onClose={() => setSelectedDocForDiff(null)}
          />
        )}

        {/* Drawers & Modals */}
        <SyncProgressDrawer
          isOpen={syncDrawerOpen}
          onClose={() => setSyncDrawerOpen(false)}
          status={sync.status}
          onReindex={sync.triggerReindex}
        />

        <SettingsDrawer
          isOpen={settingsDrawerOpen}
          onClose={() => setSettingsDrawerOpen(false)}
        />

        <VersionHistoryModal
          isOpen={!!selectedDocForHistory}
          onClose={() => setSelectedDocForHistory(null)}
          fileId={selectedDocForHistory?.id || null}
          fileName={selectedDocForHistory?.name || ''}
        />

        <AgentChatDrawer
          isOpen={agentChatOpen}
          onClose={() => setAgentChatOpen(false)}
          activeDossier={dossierState.activeDossier}
          onClearDossierScope={() => dossierState.setActiveDossier(null)}
        />

        {/* Floating Action Launcher Pill */}
        {!agentChatOpen && (
          <button
            type="button"
            onClick={() => setAgentChatOpen(true)}
            aria-label="Open Panopticon Agent Chat"
            className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 px-4 py-3 rounded-full bg-zinc-900/90 hover:bg-zinc-800 text-emerald-400 font-medium text-xs shadow-2xl border border-emerald-500/30 hover:border-emerald-500/60 active:scale-95 focus-visible:outline-2 focus-visible:outline-emerald-500 transition-all cursor-pointer backdrop-blur-md"
          >
            <span className="text-base">✨</span>
            <span className="font-semibold text-zinc-100">
              {dossierState.activeDossier
                ? `Ask ${dossierState.activeDossier.name}`
                : 'Ask Panopticon'}
            </span>
            {dossierState.activeDossier && (
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            )}
          </button>
        )}
      </div>
    </div>
  );
}
