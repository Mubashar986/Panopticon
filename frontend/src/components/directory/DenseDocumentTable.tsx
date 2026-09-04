import React, { useState } from 'react';
import { DocumentResponseItem } from '../../types/api';

interface DenseDocumentTableProps {
  documents: DocumentResponseItem[];
  loading: boolean;
  sortBy: string;
  onSortChange: (newSort: string) => void;
  recentlyModifiedIds?: Set<string>;
  onViewHistory?: (doc: DocumentResponseItem) => void;
  onInspectDiff?: (doc: DocumentResponseItem) => void;
}

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 30) return `${diffDays}d ago`;

  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function DenseDocumentTable({
  documents,
  loading,
  sortBy,
  onSortChange,
  recentlyModifiedIds = new Set(),
  onViewHistory,
  onInspectDiff,
}: DenseDocumentTableProps) {
  const [openExportMenuId, setOpenExportMenuId] = useState<string | null>(null);

  const toggleSort = (field: string) => {
    if (sortBy === `${field}:asc`) {
      onSortChange(`${field}:desc`);
    } else {
      onSortChange(`${field}:asc`);
    }
  };

  const getSortIcon = (field: string) => {
    if (sortBy === `${field}:asc`) {
      return (
        <svg className="w-3 h-3 inline-block ml-1 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        </svg>
      );
    }
    if (sortBy === `${field}:desc`) {
      return (
        <svg className="w-3 h-3 inline-block ml-1 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      );
    }
    return (
      <svg className="w-3 h-3 inline-block ml-1 text-zinc-500 opacity-40 hover:opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
      </svg>
    );
  };

  const handleDiffAction = onInspectDiff || onViewHistory;

  if (loading && documents.length === 0) {
    return (
      <div className="double-bezel w-full">
        <div className="bezel-inner p-8">
          <div className="flex flex-col gap-3 animate-pulse">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-9 bg-zinc-900/60 rounded-lg w-full" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="double-bezel w-full">
        <div className="bezel-inner p-12 text-center">
          <div className="w-12 h-12 mx-auto mb-3 text-zinc-600">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-zinc-200">No documents found in scope</p>
          <p className="text-xs text-zinc-400 mt-1 max-w-sm mx-auto">
            Try adjusting your search query, switching project dossiers, or initiating a Google Drive sync.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="double-bezel w-full overflow-hidden">
      <div className="bezel-inner overflow-x-auto">
        <table className="w-full text-left border-collapse font-sans">
          <thead>
            <tr className="border-b border-white/5 bg-zinc-950/80 text-[10px] font-bold text-zinc-400 uppercase tracking-wider select-none">
              <th className="py-3 px-4 cursor-pointer hover:text-zinc-200" onClick={() => toggleSort('name')}>
                Document Title {getSortIcon('name')}
              </th>
              <th className="py-3 px-3">Type</th>
              <th className="py-3 px-3">Project Tags</th>
              <th className="py-3 px-3">Owner</th>
              <th className="py-3 px-3">Sharing</th>
              <th className="py-3 px-4 cursor-pointer hover:text-zinc-200" onClick={() => toggleSort('modified_time')}>
                Modified {getSortIcon('modified_time')}
              </th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-xs text-zinc-200">
            {documents.map((doc) => {
              const isDoc = doc.type === 'document';
              const isSheet = doc.type === 'spreadsheet';
              const isRecent = recentlyModifiedIds.has(doc.id);

              return (
                <tr
                  key={doc.id}
                  className={`transition-colors hover:bg-zinc-900/50 ${
                    isRecent ? 'bg-emerald-500/10 ring-1 ring-emerald-500/50' : ''
                  }`}
                >
                  {/* Title & Icon */}
                  <td className="py-2.5 px-4 max-w-xs sm:max-w-md">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="shrink-0 text-base" title={doc.mime_type}>
                        {isDoc ? '📄' : isSheet ? '📊' : '📁'}
                      </span>
                      <a
                        href={doc.view_url || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-zinc-100 hover:text-emerald-400 truncate hover:underline transition-colors"
                        title={doc.name}
                      >
                        {doc.name}
                      </a>
                    </div>
                  </td>

                  {/* Type Badge */}
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium border ${
                        isDoc
                          ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                          : isSheet
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-zinc-800 text-zinc-400 border-white/5'
                      }`}
                    >
                      {isDoc ? 'DOC' : isSheet ? 'SHEET' : 'FILE'}
                    </span>
                  </td>

                  {/* Project Tags */}
                  <td className="py-2.5 px-3">
                    <div className="flex flex-wrap gap-1">
                      {doc.project_tags.length > 0 ? (
                        doc.project_tags.map((tag) => (
                          <span
                            key={tag}
                            className="px-1.5 py-0.5 text-[10px] rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 font-mono font-medium"
                          >
                            {tag}
                          </span>
                        ))
                      ) : (
                        <span className="text-zinc-600 font-mono text-[10px]">—</span>
                      )}
                    </div>
                  </td>

                  {/* Owner */}
                  <td className="py-2.5 px-3 whitespace-nowrap text-zinc-400 truncate max-w-[140px]" title={doc.owner}>
                    {doc.owner || '—'}
                  </td>

                  {/* Sharing Status */}
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span className="text-[11px] font-mono text-zinc-400 capitalize">
                      {doc.sharing_status}
                    </span>
                  </td>

                  {/* Modified Time */}
                  <td className="py-2.5 px-4 whitespace-nowrap text-zinc-400 font-mono text-[11px] tabular-nums">
                    <div className="flex flex-col">
                      <span className="text-zinc-200">{formatRelativeTime(doc.modified_time)}</span>
                      {doc.last_modifying_user && (
                        <span className="text-[10px] text-zinc-500 truncate max-w-[120px]" title={`By ${doc.last_modifying_user}`}>
                          by {doc.last_modifying_user.split('@')[0]}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Quick Actions */}
                  <td className="py-2.5 px-4 text-right whitespace-nowrap relative">
                    <div className="inline-flex items-center gap-1.5">
                      {handleDiffAction && (
                        <button
                          type="button"
                          onClick={() => handleDiffAction(doc)}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded bg-zinc-800/80 hover:bg-emerald-500/20 text-zinc-300 hover:text-emerald-300 border border-white/5 hover:border-emerald-500/30 text-[11px] font-mono transition-all cursor-pointer shadow-sm"
                          title="Inspect version diffs & AI change summary"
                        >
                          <span>⚡</span>
                          <span>Diff</span>
                        </button>
                      )}

                      {doc.view_url && (
                        <a
                          href={doc.view_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 text-zinc-400 hover:text-zinc-100 hover:bg-white/5 rounded transition-colors"
                          title="Open in Google Drive"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      )}

                      {doc.export_links && Object.keys(doc.export_links).length > 0 && (
                        <div className="relative inline-block text-left">
                          <button
                            type="button"
                            onClick={() => setOpenExportMenuId(openExportMenuId === doc.id ? null : doc.id)}
                            className="p-1 text-zinc-400 hover:text-zinc-100 hover:bg-white/5 rounded transition-colors"
                            title="Export Document"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                          </button>

                          {openExportMenuId === doc.id && (
                            <div className="absolute right-0 mt-1 w-32 bg-zinc-900 border border-white/10 rounded-lg shadow-xl z-20 py-1 text-left animate-fade-in">
                              {Object.entries(doc.export_links).map(([fmt, link]) => (
                                <a
                                  key={fmt}
                                  href={link}
                                  download
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={() => setOpenExportMenuId(null)}
                                  className="block px-3 py-1 text-[11px] font-mono text-zinc-300 hover:bg-emerald-500 hover:text-zinc-950 uppercase font-semibold transition-colors"
                                >
                                  {fmt}
                                </a>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
