import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import DocSource from '../components/DocSource.jsx';
import { Icon } from '../components/ui.jsx';

const STAGES = [
  'Reading your files (scans and photos are read with OCR)',
  'Finding the requirements in the job ad',
  'Searching your resume for proof',
  'Scoring your fit',
  'Writing your coaching notes',
];

class SideError extends Error {
  constructor(side, message) {
    super(message);
    this.side = side;
  }
}

async function toId(kind, value) {
  if (value.mode === 'saved') return value.id;
  try {
    const doc = await api.addDocument({ kind, file: value.file, text: value.text });
    return doc.id;
  } catch (e) {
    throw new SideError(kind, e.message);
  }
}

function Progress({ resume, job, running }) {
  const steps = [
    ['Your resume', !!resume],
    ['The job ad', !!job],
    ['Your report', false],
  ];
  const current = !resume ? 0 : !job ? 1 : 2;
  return (
    <ol className="progress" aria-label="Progress">
      {steps.map(([name, done], i) => (
        <li key={name} className={done ? 'is-done' : i === current ? (running ? 'is-now is-busy' : 'is-now') : ''}>
          <span className="progress__num" aria-hidden="true">{done ? <Icon name="check" size={14} /> : i + 1}</span>
          <span className="progress__name">{name}</span>
        </li>
      ))}
    </ol>
  );
}

export default function NewAnalysis() {
  const [resume, setResume] = useState(null);
  const [job, setJob] = useState(null);
  const [stage, setStage] = useState(-1);
  const [errors, setErrors] = useState({});
  const navigate = useNavigate();
  const running = stage >= 0;

  // The analysis is one request; the stage list advances on a timer so people see what is happening.
  useEffect(() => {
    if (stage < 1 || stage >= STAGES.length - 1) return undefined;
    const t = setTimeout(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 1600);
    return () => clearTimeout(t);
  }, [stage]);

  async function submit(e) {
    e.preventDefault();
    const missing = {};
    if (!resume) missing.resume = 'Add your resume first.';
    if (!job) missing.job = 'Add the job ad first.';
    setErrors(missing);
    if (Object.keys(missing).length) return;

    setStage(0);
    try {
      const rid = await toId('resume', resume);
      const jid = await toId('job', job);
      setStage(1);
      const a = await api.analyze(rid, jid);
      navigate(`/report/${a.id}`);
    } catch (err) {
      setErrors(err instanceof SideError ? { [err.side]: err.message } : { form: err.message });
      setStage(-1);
    }
  }

  return (
    <section>
      <header className="page-head page-head--stack">
        <div>
          <h1 className="h1">Check a job</h1>
          <p className="muted">Add your resume and the job you want. You will get a report in a few seconds.</p>
        </div>
        <Progress resume={resume} job={job} running={running} />
      </header>

      <form onSubmit={submit}>
        <div className="pair">
          <div className="sheet">
            <h2 className="h2">Your resume</h2>
            <DocSource kind="resume" value={resume} error={errors.resume}
              onChange={(v) => { setResume(v); setErrors((x) => ({ ...x, resume: '' })); }} />
          </div>
          <div className="sheet">
            <h2 className="h2">The job ad</h2>
            <DocSource kind="job" value={job} error={errors.job}
              onChange={(v) => { setJob(v); setErrors((x) => ({ ...x, job: '' })); }} />
          </div>
        </div>

        {errors.form && <p className="error">{errors.form}</p>}

        {running ? (
          <ol className="stages" aria-live="polite">
            {STAGES.map((s, i) => (
              <li key={s} className={i < stage ? 'is-done' : i === stage ? 'is-now' : ''}>
                <span className="stages__mark" aria-hidden="true">{i < stage ? <Icon name="check" size={14} /> : null}</span>
                {s}
              </li>
            ))}
          </ol>
        ) : (
          <div className="submit-bar">
            <p className="small muted">Your files stay on this computer, in your own database.</p>
            <button type="submit" className="btn btn--primary btn--lg">Check my fit</button>
          </div>
        )}
      </form>
    </section>
  );
}
