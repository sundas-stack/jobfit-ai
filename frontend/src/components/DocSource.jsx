import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api.js';
import { Icon } from './ui.jsx';

const ACCEPT = '.pdf,.docx,.png,.jpg,.jpeg,.webp,.txt,.md';
const MAX_MB = 10;

function prettySize(bytes) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function fileKind(name) {
  const ext = name.split('.').pop().toLowerCase();
  if (ext === 'pdf') return 'PDF';
  if (ext === 'docx') return 'Word';
  if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) return 'Image';
  return 'Text';
}

// One side of the "check a job" form: pick a saved document, upload a file, or paste text.
export default function DocSource({ kind, value, onChange, allowSaved = true, error }) {
  const [saved, setSaved] = useState([]);
  const [mode, setMode] = useState('upload');
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState('');
  const fileRef = useRef(null);
  const label = kind === 'resume' ? 'resume' : 'job ad';

  useEffect(() => {
    if (!allowSaved) return;
    api.documents(kind).then((docs) => {
      setSaved(docs);
      if (docs.length) setMode('saved');
    });
  }, [kind, allowSaved]);

  const file = value?.mode === 'upload' ? value.file : null;
  const preview = useMemo(() => (file && file.type.startsWith('image/') ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const modes = [
    ...(saved.length ? [['saved', 'Saved']] : []),
    ['upload', 'Upload file'],
    ['paste', 'Paste text'],
  ];

  function pickFile(f) {
    if (!f) return;
    const ext = `.${f.name.split('.').pop().toLowerCase()}`;
    if (!ACCEPT.split(',').includes(ext)) {
      setLocalError('Use a PDF, Word (DOCX), image (PNG, JPG, WEBP) or TXT file.');
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setLocalError(`This file is ${prettySize(f.size)}. The limit is ${MAX_MB} MB.`);
      return;
    }
    setLocalError('');
    onChange({ mode: 'upload', file: f });
  }

  const shownError = localError || error;

  return (
    <div className="source">
      <div className="segmented" role="tablist" aria-label={`How to add the ${label}`}>
        {modes.map(([m, text]) => (
          <button key={m} type="button" role="tab" aria-selected={mode === m} className={mode === m ? 'is-on' : ''}
            onClick={() => { setMode(m); setLocalError(''); onChange(null); }}>
            {text}
          </button>
        ))}
      </div>

      {mode === 'saved' && (
        <label className="field">
          <span className="field__label">Choose a saved {label}</span>
          <select value={value?.id || ''}
            onChange={(e) => onChange(e.target.value ? { mode: 'saved', id: Number(e.target.value) } : null)}>
            <option value="">Select…</option>
            {saved.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
          </select>
        </label>
      )}

      {mode === 'upload' && (
        <div
          className={`drop ${dragging ? 'is-drag' : ''} ${file ? 'has-file' : ''} ${shownError ? 'has-error' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0]); }}
        >
          {file ? (
            <div className="picked">
              {preview ? (
                <img src={preview} alt="" className="picked__thumb" />
              ) : (
                <span className="picked__icon"><Icon name="doc" size={22} /></span>
              )}
              <span className="picked__info">
                <strong className="picked__name">{file.name}</strong>
                <span className="small muted">
                  {fileKind(file.name)}, {prettySize(file.size)}
                  {fileKind(file.name) === 'Image' ? '. The text will be read from the picture.' : ''}
                </span>
              </span>
              <span className="picked__actions">
                <button type="button" className="btn btn--sm" onClick={() => fileRef.current?.click()}>Change</button>
                <button type="button" className="icon-btn" aria-label="Remove file"
                  onClick={() => { onChange(null); if (fileRef.current) fileRef.current.value = ''; }}>
                  <Icon name="x" size={16} />
                </button>
              </span>
            </div>
          ) : (
            <button type="button" className="drop__pick" onClick={() => fileRef.current?.click()}>
              <span className="drop__icon"><Icon name="upload" size={22} /></span>
              <span className="drop__text">
                <strong>Drop your {label} here, or click to browse</strong>
                <span className="small muted">PDF, Word, photo or TXT, up to {MAX_MB} MB. Scanned files are read automatically.</span>
              </span>
            </button>
          )}
          <input ref={fileRef} type="file" accept={ACCEPT} hidden onChange={(e) => pickFile(e.target.files[0])} />
        </div>
      )}

      {mode === 'paste' && (
        <label className="field">
          <span className="field__label">Paste the {label}</span>
          <textarea rows={11} value={value?.text || ''}
            placeholder={kind === 'resume' ? 'Your name, experience, projects, skills…' : 'Job title, company, responsibilities, requirements…'}
            onChange={(e) => onChange(e.target.value.trim() ? { mode: 'paste', text: e.target.value } : null)} />
        </label>
      )}

      {shownError && <p className="field-error" role="alert">{shownError}</p>}
    </div>
  );
}
