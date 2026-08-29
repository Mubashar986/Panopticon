import { useState } from 'react';
import { useSearch } from './hooks/useSearch';
import { useSync } from './hooks/useSync';
import { SearchBar } from './components/search/SearchBar';
import { ModeSelector } from './components/search/ModeSelector';
import { FilterBar } from './components/search/FilterBar';
import { ResultsList } from './components/results/ResultsList';
import { SyncControls } from './components/sync/SyncControls';
import { SyncProgressDrawer } from './components/sync/SyncProgressDrawer';
import { SettingsDrawer } from './components/settings/SettingsDrawer';

export default function Dashboard() {
  const search = useSearch();
  const sync = useSync();
  const [syncDrawerOpen, setSyncDrawerOpen] = useState(false);
  const [settingsDrawerOpen, setSettingsDrawerOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[var(--color-bg-canvas)] text-[var(--color-text-primary)] p-[var(--space-8)]">
      {/* Header */}
      <header className="flex justify-between items-center mb-[var(--space-8)]">
        <h1 className="text-[var(--text-2xl)] font-bold tracking-tight">Panopticon Observatory</h1>
        <div className="flex items-center gap-[var(--space-4)]">
          <SyncControls status={sync.status} onOpenDrawer={() => setSyncDrawerOpen(true)} onSync={() => sync.triggerSync()} loading={sync.loading} />
          <button onClick={() => setSettingsDrawerOpen(true)} className="p-[var(--space-2)] rounded-[var(--radius-md)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface-elevated)] hover:text-[var(--color-text-primary)] transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
          </button>
        </div>
      </header>

      {/* Search Area */}
      <div className="space-y-[var(--space-6)]">
        <SearchBar query={search.query} setQuery={search.setQuery} loading={search.loading} />
        <div className="flex flex-col sm:flex-row items-center justify-between gap-[var(--space-4)]">
          <ModeSelector mode={search.mode} setMode={search.setMode} />
          <FilterBar filters={search.filters} setFilters={search.setFilters} />
        </div>
      </div>

      {/* Results Area */}
      <ResultsList data={search.data} loading={search.loading} error={search.error} query={search.query} onRetry={search.retry} />

      {/* Drawers */}
      <SyncProgressDrawer isOpen={syncDrawerOpen} onClose={() => setSyncDrawerOpen(false)} status={sync.status} onReindex={sync.triggerReindex} />
      <SettingsDrawer isOpen={settingsDrawerOpen} onClose={() => setSettingsDrawerOpen(false)} />
    </div>
  );
}
