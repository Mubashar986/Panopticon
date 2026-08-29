import { useState, useRef } from 'react';
interface Props { onUpload: (file: File) => void; }

export function CredentialUploader({ onUpload }: Props) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File) => {
    if (!file.name.endsWith('.json')) {
      setError('Invalid file type. Please upload a .json file.');
      return;
    }
    setError(null);
    onUpload(file);
  };

  return (
    <div className="mt-[var(--space-4)]">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); }}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center p-[var(--space-6)] border-2 border-dashed rounded-[var(--radius-lg)] cursor-pointer transition-all
          ${dragging ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/5' : 'border-[var(--color-border)] hover:border-[var(--color-text-secondary)] bg-[var(--color-bg-surface-elevated)]'}`}
      >
        <svg className="w-8 h-8 text-[var(--color-text-secondary)] mb-[var(--space-2)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
        <p className="text-sm text-[var(--color-text-primary)] font-medium">Drop credentials.json or service_account.json</p>
        <p className="text-xs text-[var(--color-text-secondary)] mt-[var(--space-1)]">or click to browse</p>
        <input ref={inputRef} type="file" accept=".json" className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
      </div>
      {error && <p className="mt-[var(--space-2)] text-xs text-[var(--color-error)]">{error}</p>}
    </div>
  );
}
