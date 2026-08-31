import React, { useState } from 'react';
import { DocumentResponseItem } from '../../types/api';

interface DenseDocumentTableProps {
  documents: DocumentResponseItem[];
  loading: boolean;
  sortBy: string;
  onSortChange: (newSort: string) => void;
  recentlyModifiedIds?: Set<string>;
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
        <svg className="w-3 h-3 inline-block ml-1 text-[var(--color-primary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        </svg>
      );
    }
    if (sortBy === `${field}:desc`) {
      return (
        <svg className="w-3 h-3 inline-block ml-1 text-[var(--color-primary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      );
    }
    return (
      <svg className="w-3 h-3 inline-block ml-1 text-[var(--color-text-secondary)] opacity-40 hover:opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
      </svg>
    );
  };

  if (loading && documents.length === 0) {
    return (
      <div className="w-full bg-[var(--color-bg-surface)] border border-[var(--color-border)] rounded-t-[var(--radius-lg)] p-[var(--space-8)]">
        <div className="flex flex-col gap-[var(--space-3)] animate-pulse">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-8 bg-[var(--color-bg-surface-elevated)] rounded-[var(--radius-sm)] w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="w-full bg-[var(--color-bg-surface)] border border-[var(--color-border)] rounded-t-[var(--radius-lg)] p-[var(--space-12)] text-center">
        <div className="w-12 h-12 mx-auto mb-[var(--space-3)] text-[var(--color-text-secondary)] opacity-50">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <p className="text-sm font-medium text-[var(--color-text-primary)]">No documents found</p>
        <p className="text-xs text-[var(--color-text-secondary)] mt-1">Try adjusting your filters or triggering a Google Drive sync.</p>
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto bg-[var(--color-bg-surface)] border border-[var(--color-border)] rounded-t-[var(--radius-lg)] shadow-sm">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-[var(--color-border)] bg-[var(--color-bg-surface-elevated)] text-[11px] font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider select-none">
            <th className="py-[var(--space-3)] px-[var(--space-4)] cursor-pointer hover:text-[var(--color-text-primary)]" onClick={() => toggleSort('name')}>
              Title {getSortIcon('name')}
            </th>
            <th className="py-[var(--space-3)] px-[var(--space-3)]">Type</th>
            <th className="py-[var(--space-3)] px-[var(--space-3)]">Projects</th>
            <th className="py-[var(--space-3)] px-[var(--space-3)]">Owner</th>
            <th className="py-[var(--space-3)] px-[var(--space-3)]">Sharing</th>
            <th className="py-[var(--space-3)] px-[var(--space-4)] cursor-pointer hover:text-[var(--color-text-primary)]" onClick={() => toggleSort('modified_time')}>
              Modified {getSortIcon('modified_time')}
            </th>
            <th className="py-[var(--space-3)] px-[var(--space-4)] text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--color-border)] text-xs text-[var(--color-text-primary)]">
          {documents.map((doc) => {
            const isDoc = doc.type === 'document';
            const isSheet = doc.type === 'spreadsheet';
            const isRecent = recentlyModifiedIds.has(doc.id);

            return (
              <tr
                key={doc.id}
                className={`transition-colors hover:bg-[var(--color-bg-surface-elevated)] ${
                  isRecent ? 'bg-[rgba(16,185,129,0.12)] ring-1 ring-[var(--color-success)]' : ''
                }`}
              >
                {/* Title & Icon */}
                <td className="py-[var(--space-2)] px-[var(--space-4)] max-w-xs sm:max-w-md">
                  <div className="flex items-center gap-[var(--space-2)]">
                    <span className="flex-shrink-0 text-base" title={doc.mime_type}>
                      {isDoc ? '📄' : isSheet ? '📊' : '📁'}
                    </span>
                    <a
                      href={doc.view_url || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-[var(--color-text-primary)] hover:text-[var(--color-primary-hover)] truncate hover:underline"
                      title={doc.name}
                    >
                      {doc.name}
                    </a>
                  </div>
                </td>

                {/* Type Badge */}
                <td className="py-[var(--space-2)] px-[var(--space-3)] whitespace-nowrap">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-[var(--radius-sm)] text-[10px] font-medium ${
                      isDoc
                        ? 'bg-[rgba(66,133,244,0.15)] text-[var(--color-drive)]'
                        : isSheet
                        ? 'bg-[rgba(16,185,129,0.15)] text-[var(--color-success)]'
                        : 'bg-[var(--color-bg-surface-elevated)] text-[var(--color-text-secondary)]'
                    }`}
                  >
                    {isDoc ? 'Doc' : isSheet ? 'Sheet' : 'File'}
                  </span>
                </td>

                {/* Project Tags */}
                <td className="py-[var(--space-2)] px-[var(--space-3)]">
                  <div className="flex flex-wrap gap-1">
                    {doc.project_tags.length > 0 ? (
                      doc.project_tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-1.5 py-0.5 text-[10px] rounded-[var(--radius-sm)] bg-[rgba(168,85,247,0.15)] text-[var(--color-tag-match)] font-medium"
                        >
                          {tag}
                        </span>
                      ))
                    ) : (
                      <span className="text-[var(--color-text-secondary)] opacity-40">—</span>
                    )}
                  </div>
                </td>

                {/* Owner */}
                <td className="py-[var(--space-2)] px-[var(--space-3)] whitespace-nowrap text-[var(--color-text-secondary)] truncate max-w-[140px]" title={doc.owner}>
                  {doc.owner || '—'}
                </td>

                {/* Sharing Status */}
                <td className="py-[var(--space-2)] px-[var(--space-3)] whitespace-nowrap">
                  <span className="text-[11px] text-[var(--color-text-secondary)] capitalize">
                    {doc.sharing_status}
                  </span>
                </td>

                {/* Modified Time */}
                <td className="py-[var(--space-2)] px-[var(--space-4)] whitespace-nowrap text-[var(--color-text-secondary)]">
                  <div className="flex flex-col">
                    <span className="text-[var(--color-text-primary)]">{formatRelativeTime(doc.modified_time)}</span>
                    {doc.last_modifying_user && (
                      <span className="text-[10px] opacity-70 truncate max-w-[120px]" title={`By ${doc.last_modifying_user}`}>
                        by {doc.last_modifying_user.split('@')[0]}
                      </span>
                    )}
                  </div>
                </td>

                {/* Quick Actions */}
                <td className="py-[var(--space-2)] px-[var(--space-4)] text-right whitespace-nowrap relative">
                  <div className="inline-flex items-center gap-1">
                    {doc.view_url && (
                      <a
                        href={doc.view_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] rounded hover:bg-[var(--color-bg-surface-elevated)]"
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
                          onClick={() => setOpenExportMenuId(openExportMenuId === doc.id ? null : doc.id)}
                          className="p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] rounded hover:bg-[var(--color-bg-surface-elevated)]"
                          title="Export Document"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                          </svg>
                        </button>

                        {openExportMenuId === doc.id && (
                          <div className="absolute right-0 mt-1 w-32 bg-[var(--color-bg-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] shadow-lg z-20 py-1 text-left">
                            {Object.entries(doc.export_links).map(([fmt, link]) => (
                              <a
                                key={fmt}
                                href={link}
                                download
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={() => setOpenExportMenuId(null)}
                                className="block px-3 py-1 text-xs text-[var(--color-text-primary)] hover:bg-[var(--color-primary)] hover:text-white uppercase font-medium"
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
  );
}
