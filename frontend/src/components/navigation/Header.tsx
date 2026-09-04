import React from 'react';
import { SyncControls } from '../sync/SyncControls';
import { SyncStatusResponse } from '../../types/api';

interface HeaderProps {
  isLiveConnected: boolean;
  totalDocuments: number;
  totalDossiers: number;
  syncStatus: SyncStatusResponse | null;
  syncLoading: boolean;
  onOpenSyncDrawer: () => void;
  onTriggerSync: () => void;
  onOpenSettings: () => void;
  onOpenAgentChat: () => void;
}

export function Header({
  isLiveConnected,
  totalDocuments,
  totalDossiers,
  syncStatus,
  syncLoading,
  onOpenSyncDrawer,
  onTriggerSync,
  onOpenSettings,
  onOpenAgentChat,
}: HeaderProps) {
  return (
    <header className="double-bezel mb-6">
      <div className="bezel-inner px-4 py-3 sm:px-6 flex flex-wrap items-center justify-between gap-4">
        {/* Brand & Telemetry Pulse */}
        <div className="flex items-center gap-3.5 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-mono font-bold text-sm shadow-sm shadow-emerald-500/20 shrink-0">
            👁️
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-base font-extrabold tracking-tight text-zinc-100 font-sans">
                Panopticon
              </h1>
              <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] font-mono text-zinc-400 border border-white/5 uppercase">
                v0.1.0
              </span>
              {isLiveConnected && (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-[10px] font-mono font-semibold border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  LIVE SSE
                </span>
              )}
            </div>
            <p className="text-[11px] text-zinc-500 font-mono">
              OBSERVATORY &bull; {totalDocuments} DOCS &bull; {totalDossiers} DOSSIERS
            </p>
          </div>
        </div>

        {/* Cockpit Actions */}
        <div className="flex items-center gap-2.5">
          {/* Ask Panopticon Primary CTA */}
          <button
            type="button"
            onClick={onOpenAgentChat}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 hover:border-emerald-400/60 active:scale-95 focus-visible:outline-2 focus-visible:outline-emerald-500 text-xs font-semibold transition-all cursor-pointer shadow-sm shadow-emerald-500/10"
          >
            <span className="text-sm">✨</span>
            <span>Ask Panopticon</span>
          </button>

          {/* Sync Controls Seam */}
          <SyncControls
            status={syncStatus}
            onOpenDrawer={onOpenSyncDrawer}
            onSync={onTriggerSync}
            loading={syncLoading}
          />

          {/* Settings Trigger */}
          <button
            type="button"
            onClick={onOpenSettings}
            aria-label="Open Settings"
            className="p-2 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-white/5 border border-transparent hover:border-white/10 transition-colors cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  );
}
