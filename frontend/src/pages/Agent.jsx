import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { Icon, RichText, Spinner } from '../components/ui.jsx';

const SUGGESTIONS = [
  'Am I a good fit for this job?',
  'Which skills am I missing, and how much do they matter?',
  'Rewrite my strongest resume line for this job.',
  'Give me interview questions to practise.',
];

function Steps({ steps }) {
  if (!steps.length) return null;
  return (
    <ol className="steps" aria-label="What the agent did">
      {steps.map((s) => (
        <li key={s.id} className={s.status === 'done' ? 'is-done' : 'is-now'}>
          <span className="steps__mark" aria-hidden="true">
            {s.status === 'done' ? <Icon name="check" size={12} /> : <span className="spinner__dot" />}
          </span>
          <span>
            {s.label}
            {s.args?.query ? <span className="muted"> for “{s.args.query}”</span> : null}
            {s.summary ? <span className="muted">. {s.summary}</span> : null}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Sources({ items, active }) {
  if (!items?.length) return null;
  return (
    <div className="sources">
      {items.map((s) => (
        <details key={s.label} open={active === s.label} className={`source-item source-item--${s.label[0]}`}>
          <summary>
            <span className={`cite cite--${s.label[0]}`}>{s.label}</span>
            {s.kind === 'job' ? 'Job ad' : 'Your resume'}
          </summary>
          <p>{s.text}</p>
        </details>
      ))}
    </div>
  );
}

export default function Agent() {
  const [params] = useSearchParams();
  const [resumes, setResumes] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [resumeId, setResumeId] = useState(Number(params.get('resume')) || '');
  const [jobId, setJobId] = useState(Number(params.get('job')) || '');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(null);
  const endRef = useRef(null);

  useEffect(() => {
    api.documents('resume').then((d) => {
      setResumes(d);
      if (!resumeId && d[0]) setResumeId(d[0].id);
    });
    api.documents('job').then((d) => {
      setJobs(d);
      if (!jobId && d[0]) setJobId(d[0].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  const update = (fn) =>
    setMessages((prev) => {
      const copy = [...prev];
      copy[copy.length - 1] = fn(copy[copy.length - 1]);
      return copy;
    });

  async function send(text) {
    const message = text.trim();
    if (!message || busy || !resumeId || !jobId) return;
    const history = messages.map((m) => ({ role: m.role, content: m.text || '' })).filter((m) => m.content);
    setMessages((m) => [...m, { role: 'user', text: message }, { role: 'assistant', steps: [], text: '' }]);
    setInput('');
    setBusy(true);
    try {
      await api.askAgent({ resumeId, jobId, message, history }, (ev) => {
        if (ev.type === 'step')
          update((m) => {
            const others = m.steps.filter((s) => s.id !== ev.id);
            return { ...m, steps: [...others, ev].sort((x, y) => x.id - y.id) };
          });
        else if (ev.type === 'sources') update((m) => ({ ...m, sources: ev.items }));
        else if (ev.type === 'answer') update((m) => ({ ...m, text: ev.text }));
        else if (ev.type === 'error') update((m) => ({ ...m, error: ev.message }));
      });
    } catch (e) {
      update((m) => ({ ...m, error: e.message }));
    } finally {
      setBusy(false);
    }
  }

  const ready = resumeId && jobId;

  return (
    <section className="agent">
      <header className="page-head">
        <div>
          <h1 className="h1">Ask the agent</h1>
          <p className="muted">It searches both documents, compares them and shows its sources.</p>
        </div>
        <div className="pickers">
          <label className="field field--inline">
            <span className="field__label">Resume</span>
            <select value={resumeId} onChange={(e) => { setResumeId(Number(e.target.value)); setMessages([]); }}>
              {resumes.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
          </label>
          <label className="field field--inline">
            <span className="field__label">Job</span>
            <select value={jobId} onChange={(e) => { setJobId(Number(e.target.value)); setMessages([]); }}>
              {jobs.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
          </label>
        </div>
      </header>

      <div className="chat">
        {!ready && <p className="muted">Add a resume and a job ad in the Library first.</p>}
        {ready && !messages.length && (
          <div className="starter">
            <p className="starter__lead">Try one of these, or ask your own question.</p>
            <div className="chips">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="chip" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="msg msg--user"><p>{m.text}</p></div>
          ) : (
            <div key={i} className="msg msg--agent">
              <Steps steps={m.steps} />
              {m.error && <p className="error">{m.error}</p>}
              {m.text ? (
                <>
                  <RichText text={m.text} onCite={setActive} />
                  <Sources items={m.sources} active={active} />
                </>
              ) : (
                !m.error && <Spinner label={m.steps.length ? 'Working' : 'Thinking'} />
              )}
            </div>
          )
        )}
        <div ref={endRef} />
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <label htmlFor="ask" className="sr-only">Your question</label>
        <input id="ask" value={input} onChange={(e) => setInput(e.target.value)} disabled={!ready}
          placeholder="Ask about this job, your gaps or your resume" autoComplete="off" />
        <button type="submit" className="btn btn--primary" disabled={busy || !input.trim() || !ready}>
          <Icon name="send" size={16} />
          Ask
        </button>
      </form>
    </section>
  );
}
