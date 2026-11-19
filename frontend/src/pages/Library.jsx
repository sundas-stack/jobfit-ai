import { useEffect, useState } from 'react';
import { api, timeAgo } from '../api.js';
import DocSource from '../components/DocSource.jsx';
import { Icon, Spinner } from '../components/ui.jsx';

function Column({ kind, title }) {
  const [docs, setDocs] = useState(null);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState(null);
  const [name, setName] = useState('');
  const [viewing, setViewing] = useState(null);
  const [error, setError] = useState('');
  const load = () => api.documents(kind).then(setDocs);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function save() {
    if (!draft || draft.mode === 'saved') return setError('Upload a file or paste some text.');
    setError('');
    try {
      await api.addDocument({ kind, title: name, file: draft.file, text: draft.text });
      setAdding(false);
      setDraft(null);
      setName('');
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function view(id) {
    setViewing(viewing?.id === id ? null : await api.document(id));
  }

  return (
    <section className="sheet">
      <div className="sheet__bar sheet__bar--plain">
        <h2 className="h2">{title}</h2>
        <button type="button" className="btn btn--sm" onClick={() => setAdding(!adding)}>
          <Icon name={adding ? 'x' : 'plus'} size={15} />
          {adding ? 'Cancel' : 'Add'}
        </button>
      </div>

      {adding && (
        <div className="adder">
          <label className="field">
            <span className="field__label">Name (optional)</span>
            <input value={name} onChange={(e) => setName(e.target.value)}
              placeholder={kind === 'resume' ? 'e.g. Resume, AI roles' : 'e.g. Frontend Engineer at Acme'} />
          </label>
          <DocSource kind={kind} allowSaved={false} value={draft} onChange={setDraft} />
          {error && <p className="error">{error}</p>}
          <button type="button" className="btn btn--primary" onClick={save}>Save {kind === 'resume' ? 'resume' : 'job ad'}</button>
        </div>
      )}

      {!docs ? (
        <Spinner />
      ) : !docs.length ? (
        <p className="muted">Nothing here yet.</p>
      ) : (
        <ul className="docs">
          {docs.map((d) => (
            <li key={d.id} className="doc">
              <div className="doc__row">
                <Icon name="doc" />
                <button type="button" className="doc__title" onClick={() => view(d.id)} aria-expanded={viewing?.id === d.id}>
                  {d.title}
                </button>
                <span className="small muted">{d.chunks} parts, {timeAgo(d.created_at)}</span>
                <button type="button" className="icon-btn" aria-label={`Delete ${d.title}`}
                  onClick={async () => { await api.deleteDocument(d.id); load(); }}>
                  <Icon name="trash" size={16} />
                </button>
              </div>
              {viewing?.id === d.id && (
                <ol className="chunks">
                  {viewing.chunk_list.map((c) => (
                    <li key={c.label}>
                      <span className={`cite cite--${c.label[0]}`}>{c.label}</span>
                      <p>{c.text}</p>
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function Library() {
  return (
    <section>
      <header className="page-head">
        <div>
          <h1 className="h1">Library</h1>
          <p className="muted">Everything you have added. Each document is split into small parts so the AI can quote them.</p>
        </div>
      </header>
      <div className="pair">
        <Column kind="resume" title="Resumes" />
        <Column kind="job" title="Job ads" />
      </div>
    </section>
  );
}
