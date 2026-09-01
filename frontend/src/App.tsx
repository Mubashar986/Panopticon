import { useState } from 'react';
import { useSearch } from './hooks/useSearch';
import { useSync } from './hooks/useSync';
import { useDocuments } from './hooks/useDocuments';
import { DocumentResponseItem } from './types/api';
import { SearchBar } from './components/search/SearchBar';
import { ModeSelector } from './components/search/ModeSelector';
import { FilterBar } from './components/search/FilterBar';
import { ResultsList } from './components/results/ResultsList';
import { SyncControls } from './components/sync/SyncControls';
import { SyncProgressDrawer } from './components/sync/SyncProgressDrawer';
import { SettingsDrawer } from './components/settings/SettingsDrawer';
import { DenseDocumentTable } from './components/directory/DenseDocumentTable';
import { PaginationBar } from './components/directory/PaginationBar';
import { ViewToggle, ViewMode } from './components/directory/ViewToggle';
import { VersionHistoryModal } from './components/diff/VersionHistoryModal';
import { AgentChatDrawer } from './components/agent/AgentChatDrawer';

export default function Dashboard() {
  const search = useSearch();
  const sync = useSync();
  const docs = useDocuments();

  const [syncDrawerOpen, setSyncDrawerOpen] = useState(false);
  const [settingsDrawerOpen, setSettingsDrawerOpen] = useState(false);
  const [agentChatOpen, setAgentChatOpen] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [selectedDocForHistory, setSelectedDocForHistory] = useState<DocumentResponseItem | null>(null);

  const isSearching = search.query.trim().length > 0;

  return (
    <div className="min-h-screen bg-[var(--color-bg-canvas)] text-[var(--color-text-primary)] p-[var(--space-8)]">
      {/* Top Navigation Bar */}
      <header className="flex justify-between items-center mb-[var(--space-8)]">
        <div className="flex items-center gap-[var(--space-3)]">
          <h1 className="text-[var(--text-2xl)] font-bold tracking-tight">Panopticon Observatory</h1>
          {docs.isLiveConnected && (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[var(--radius-full)] bg-[rgba(16,185,129,0.15)] text-[var(--color-success)] text-[11px] font-medium animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)]" />
              Live SSE Active
            </span>
          )}
        </div>
        <div className="flex items-center gap-[var(--space-4)]">
          <button
            type="button"
            onClick={() => setAgentChatOpen(true)}
            className="inline-flex items-center gap-2 px-[var(--space-3)] py-[var(--space-2)] rounded-[var(--radius-md)] bg-[rgba(139,92,246,0.15)] text-[var(--color-primary-hover)] border border-[rgba(139,92,246,0.35)] hover:bg-[rgba(139,92,246,0.25)] hover:border-[var(--color-primary)] active:scale-95 focus-visible:outline-2 focus-visible:outline-[var(--color-primary)] text-[12px] font-semibold transition-all cursor-pointer shadow-[var(--elevation-glow-primary)]"
          >
            <span>✨</span>
            <span>Ask Panopticon</span>
          </button>
          <SyncControls
            status={sync.status}
            onOpenDrawer={() => setSyncDrawerOpen(true)}
            onSync={() => sync.triggerSync()}
            loading={sync.loading}
          />
          <button
            onClick={() => setSettingsDrawerOpen(true)}
            aria-label="Settings"
            className="p-[var(--space-2)] rounded-[var(--radius-md)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-elevated)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
      </header>

      {/* Search & Filter Controls */}
      <div className="space-y-[var(--space-6)] mb-[var(--space-6)]">
        <SearchBar query={search.query} setQuery={search.setQuery} loading={search.loading} />
        
        <div className="flex flex-col sm:flex-row items-center justify-between gap-[var(--space-4)]">
          {isSearching ? (
            <ModeSelector mode={search.mode} setMode={search.setMode} />
          ) : (
            <ViewToggle viewMode={viewMode} onViewModeChange={setViewMode} />
          )}
          <FilterBar filters={search.filters} setFilters={search.setFilters} />
        </div>
      </div>

      {/* Main Content Area */}
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
        /* Default Mode: Live Document Directory (Table or Cards) */
        <div className="space-y-0">
          <DenseDocumentTable
            documents={docs.documents}
            loading={docs.loading}
            sortBy={docs.sortBy}
            onSortChange={docs.setSortBy}
            recentlyModifiedIds={docs.recentlyModifiedIds}
            onViewHistory={(doc) => setSelectedDocForHistory(doc)}
          />
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
        </div>
      )}

      {/* Drawers & Modals */}
      <SyncProgressDrawer
        isOpen={syncDrawerOpen}
        onClose={() => setSyncDrawerOpen(false)}
        status={sync.status}
        onReindex={sync.triggerReindex}
      />
      <SettingsDrawer isOpen={settingsDrawerOpen} onClose={() => setSettingsDrawerOpen(false)} />
      
      <VersionHistoryModal
        isOpen={!!selectedDocForHistory}
        onClose={() => setSelectedDocForHistory(null)}
        fileId={selectedDocForHistory?.id || null}
        fileName={selectedDocForHistory?.name || ''}
      />

      <AgentChatDrawer
        isOpen={agentChatOpen}
        onClose={() => setAgentChatOpen(false)}
      />

      {/* Floating Action Launcher Pill */}
      {!agentChatOpen && (
        <button
          type="button"
          onClick={() => setAgentChatOpen(true)}
          aria-label="Open Panopticon Agent Chat"
          className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 px-4 py-3 rounded-[var(--radius-full)] bg-[var(--color-primary)] text-white font-medium text-sm shadow-[var(--elevation-card-hover)] hover:bg-[var(--color-primary-hover)] active:scale-95 focus-visible:outline-2 focus-visible:outline-[var(--color-primary)] transition-all cursor-pointer border border-white/20"
        >
          <span className="text-base">✨</span>
          <span>Ask Panopticon</span>
        </button>
      )}
    </div>
  );
}
