import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, timeAgo } from '../api.js';
import { FitBar, Icon, ScoreMark, Spinner } from '../components/ui.jsx';

export default function Dashboard() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.analyses().then(setItems).catch((e) => setError(e.message));
  }, []);

  async function trySample() {
    setBusy(true);
    setError('');
    try {
      const [resume, job] = await api.loadSamples();
      const a = await api.analyze(resume.id, job.id);
      navigate(`/report/${a.id}`);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!items) return <Spinner label="Loading your applications" />;

  if (!items.length) {
    return (
      <section className="welcome">
        <h1 className="display">
          Will your resume get you
          <br />
          the interview?
        </h1>
        <p className="lede">
          Add your resume and a job ad. JobFit reads both, shows which requirements you meet with the exact
          line from your resume as proof, and tells you how to close the gaps.
        </p>
        <div className="row">
          <Link to="/new" className="btn btn--primary">
            Check a job
          </Link>
          <button type="button" className="btn" onClick={trySample} disabled={busy}>
            {busy ? <Spinner label="Analysing the sample" /> : 'Try it with a sample resume'}
          </button>
        </div>
        <ol className="how">
          <li>
            <strong>Reads the job ad</strong> and lists what the employer asks for.
          </li>
          <li>
            <strong>Finds proof in your resume</strong> for each requirement, and quotes it.
          </li>
          <li>
            <strong>Coaches you</strong> with sharper resume lines and likely interview questions.
          </li>
        </ol>
      </section>
    );
  }

  const avg = Math.round(items.reduce((s, a) => s + a.score, 0) / items.length);
  return (
    <section>
      <header className="page-head">
        <div>
          <h1 className="h1">Applications</h1>
          <p className="muted">
            {items.length} {items.length === 1 ? 'job' : 'jobs'} checked, average fit {avg}%.
          </p>
        </div>
        <Link to="/new" className="btn btn--primary">
          <Icon name="plus" size={16} />
          Check a job
        </Link>
      </header>

      <ul className="apps">
        {items.map((a) => (
          <li key={a.id}>
            <Link to={`/report/${a.id}`} className="app">
              <ScoreMark score={a.score} size="sm" />
              <span className="app__main">
                <span className="app__title">{a.job_title || 'Untitled job'}</span>
                <span className="muted small">{a.company || 'Company not listed'}</span>
              </span>
              <span className="app__fit">
                <FitBar counts={a.counts} />
                <span className="small muted">
                  {a.counts.matched || 0} matched, {a.counts.missing || 0} missing
                </span>
              </span>
              <span className="small muted app__time">{timeAgo(a.created_at)}</span>
              <Icon name="chevron" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
