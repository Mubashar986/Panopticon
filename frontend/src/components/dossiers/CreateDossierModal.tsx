import React, { useState } from 'react';
import { DossierCreatePayload, DossierSummary } from '../../types/api';

interface CreateDossierModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (payload: DossierCreatePayload) => Promise<DossierSummary>;
}

const COLOR_PRESETS = [
  { label: 'Emerald', hex: '#10b981' },
  { label: 'Cyan', hex: '#06b6d4' },
  { label: 'Cobalt', hex: '#3b82f6' },
  { label: 'Amber', hex: '#f59e0b' },
  { label: 'Violet', hex: '#8b5cf6' },
  { label: 'Rose', hex: '#f43f5e' },
  { label: 'Graphite', hex: '#64748b' },
];

const ICON_PRESETS = [
  { id: 'folder', symbol: '📁' },
  { id: 'shield', symbol: '🛡️' },
  { id: 'cpu', symbol: '⚡' },
  { id: 'book', symbol: '📖' },
  { id: 'target', symbol: '🎯' },
  { id: 'globe', symbol: '🌐' },
];

export function CreateDossierModal({ isOpen, onClose, onCreate }: CreateDossierModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedColor, setSelectedColor] = useState(COLOR_PRESETS[0].hex);
  const [selectedIcon, setSelectedIcon] = useState(ICON_PRESETS[0].id);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Dossier name is required.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim() || undefined,
        color: selectedColor,
        icon: selectedIcon,
      });
      setName('');
      setDescription('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create dossier');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-dossier-title"
    >
      <div className="double-bezel w-full max-w-lg shadow-2xl">
        <div className="bezel-inner p-6">
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-white/5 mb-5">
            <div className="flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10"
                style={{ backgroundColor: `${selectedColor}22` }}
              >
                <span className="text-base">
                  {ICON_PRESETS.find((i) => i.id === selectedIcon)?.symbol || '📁'}
                </span>
              </div>
              <div>
                <h2 id="create-dossier-title" className="text-base font-semibold text-zinc-100">
                  New Project Dossier
                </h2>
                <p className="text-xs text-zinc-400">
                  Isolate workspace files for scoped search, diffing & AI reasoning
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="w-7 h-7 rounded-md flex items-center justify-center text-zinc-400 hover:text-zinc-100 hover:bg-white/5 transition-colors cursor-pointer"
              aria-label="Close dialog"
            >
              ✕
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="dossier-name" className="block text-xs font-medium text-zinc-300 mb-1.5">
                Project Name <span className="text-emerald-400">*</span>
              </label>
              <input
                id="dossier-name"
                type="text"
                required
                maxLength={120}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Falcon Avionics Spec"
                className="w-full px-3 py-2 rounded-lg bg-zinc-950/80 border border-zinc-700/60 text-zinc-100 placeholder-zinc-500 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all font-sans"
              />
            </div>

            <div>
              <label htmlFor="dossier-desc" className="block text-xs font-medium text-zinc-300 mb-1.5">
                Description & Mission Scope
              </label>
              <textarea
                id="dossier-desc"
                rows={3}
                maxLength={2000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Context and purpose of this dossier..."
                className="w-full px-3 py-2 rounded-lg bg-zinc-950/80 border border-zinc-700/60 text-zinc-100 placeholder-zinc-500 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all resize-none font-sans"
              />
            </div>

            {/* Icon Picker */}
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">Dossier Emblem</label>
              <div className="flex gap-2">
                {ICON_PRESETS.map((icon) => (
                  <button
                    key={icon.id}
                    type="button"
                    onClick={() => setSelectedIcon(icon.id)}
                    className={`w-9 h-9 rounded-lg flex items-center justify-center text-sm border transition-all cursor-pointer ${
                      selectedIcon === icon.id
                        ? 'border-emerald-500/80 bg-emerald-500/15 text-zinc-100 shadow-sm'
                        : 'border-white/5 bg-zinc-900/50 text-zinc-400 hover:border-white/20 hover:text-zinc-200'
                    }`}
                  >
                    {icon.symbol}
                  </button>
                ))}
              </div>
            </div>

            {/* Color Accent Picker */}
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">Accent Tint</label>
              <div className="flex items-center gap-2">
                {COLOR_PRESETS.map((color) => (
                  <button
                    key={color.hex}
                    type="button"
                    onClick={() => setSelectedColor(color.hex)}
                    className={`w-6 h-6 rounded-full border-2 transition-transform cursor-pointer ${
                      selectedColor === color.hex
                        ? 'scale-125 border-white shadow-md'
                        : 'border-transparent hover:scale-110'
                    }`}
                    style={{ backgroundColor: color.hex }}
                    title={color.label}
                    aria-label={`Select ${color.label} color`}
                  />
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/5 mt-6">
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                className="px-4 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-white/5 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold text-xs transition-all active:scale-95 shadow-sm shadow-emerald-500/20 disabled:opacity-50 cursor-pointer"
              >
                {loading ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-zinc-950 border-t-transparent rounded-full animate-spin" />
                    <span>Creating...</span>
                  </>
                ) : (
                  <span>Create Dossier</span>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
