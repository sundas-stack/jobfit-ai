import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, timeAgo } from '../api.js';
import { CopyButton, Highlight, Icon, ScoreMark, Spinner, StatusPill } from '../components/ui.jsx';

const FILTERS = [
  ['all', 'All'],
  ['matched', 'Matched'],
  ['partial', 'Partly'],
  ['missing', 'Missing'],
];
const IMPORTANCE = { must: 'Required', should: 'Expected', nice: 'Bonus' };

function verdict(score) {
  if (score >= 75) return 'Strong fit. Apply, and lead with your matching experience.';
  if (score >= 50) return 'Good base. Close one or two gaps before you apply.';
  return 'Stretch role. Worth it only if you can show the missing skills another way.';
}

export default function Report() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [a, setA] = useState(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const [open, setOpen] = useState(0);

  useEffect(() => {
    api.analysis(id).then(setA).catch((e) => setError(e.message));
  }, [id]);

  const reqs = useMemo(
    () => (a ? a.report.requirements.filter((r) => filter === 'all' || r.status === filter) : []),
    [a, filter]
  );

  if (error) return <p className="error">{error}</p>;
  if (!a) return <Spinner label="Loading the report" />;
  const r = a.report;

  async function remove() {
    await api.deleteAnalysis(a.id);
    navigate('/');
  }

  return (
    <article className="report">
      <Link to="/" className="back">
        <Icon name="back" size={16} />
        Applications
      </Link>

      <header className="report__head">
        <h1 className="display display--md">{a.job_title || 'Job'}</h1>
        <p className="muted">
          {a.company ? `${a.company}. ` : ''}Compared with “{r.resume_title}”, {timeAgo(a.created_at)}.
        </p>
      </header>

      <div className="report__grid">
      <div className="report__main">
      <section className="sheet sheet--flush">
        <div className="sheet__bar">
          <h2 className="h2">What the job asks for</h2>
          <div className="segmented segmented--sm" role="group" aria-label="Filter requirements">
            {FILTERS.map(([k, label]) => (
              <button key={k} type="button" aria-pressed={filter === k} className={filter === k ? 'is-on' : ''}
                onClick={() => setFilter(k)}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <ul className="reqs">
          {reqs.map((q) => (
            <li key={q.skill} className={`req req--${q.status}`}>
              <div className="req__head">
                <StatusPill status={q.status} />
                <span className="req__skill">{q.skill}</span>
                <span className={`imp imp--${q.importance}`}>{IMPORTANCE[q.importance]}</span>
              </div>
              {q.detail && <p className="req__detail">The ad says: {q.detail}</p>}
              {q.quote ? (
                <blockquote className="proof">
                  <Highlight tone={q.status}>{q.quote}</Highlight>
                  <cite title={q.evidence_text}>Your resume, part {q.evidence_label}</cite>
                </blockquote>
              ) : (
                <p className="req__note">{q.note}</p>
              )}
            </li>
          ))}
          {!reqs.length && <li className="req req--empty muted">Nothing in this group.</li>}
        </ul>
      </section>

      {r.ats && (
        <section className="block">
          <h2 className="h2">How an ATS will read your resume</h2>
          <p className="muted">
            Applicant tracking systems filter by exact words and clear structure before a person reads anything.
          </p>
          <ul className="ats">
            {r.ats.checks.map((c) => (
              <li key={c.id} className={`ats__item ats__item--${c.status}`}>
                <div className="ats__head">
                  <span className="ats__name">{c.name}</span>
                  <span className="ats__score">{c.score}%</span>
                </div>
                <div className="meter" aria-hidden="true"><span style={{ width: `${c.score}%` }} /></div>
                <p className="small muted">{c.detail}</p>
                <p className="ats__tip">{c.tip}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {r.bullet_rewrites?.length > 0 && (
        <section className="block">
          <h2 className="h2">Sharper resume lines</h2>
          <p className="muted">Same facts, rewritten for this job. Nothing invented.</p>
          <div className="rewrites">
            {r.bullet_rewrites.map((b) => (
              <div key={b.before} className="rewrite">
                <p className="rewrite__before"><del>{b.before}</del></p>
                <p className="rewrite__after">{b.after}</p>
                <div className="rewrite__foot">
                  <span className="small muted">{b.why}</span>
                  <CopyButton text={b.after} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {r.interview_questions?.length > 0 && (
        <section className="block">
          <h2 className="h2">Questions they will probably ask</h2>
          <div className="qa">
            {r.interview_questions.map((q, i) => (
              <div key={q.question} className={`qa__item ${open === i ? 'is-open' : ''}`}>
                <button type="button" className="qa__q" aria-expanded={open === i}
                  onClick={() => setOpen(open === i ? -1 : i)}>
                  <span>{q.question}</span>
                  <Icon name="chevron" size={16} />
                </button>
                {open === i && (
                  <div className="qa__a">
                    <p><strong>Why they ask:</strong> {q.why}</p>
                    <p><strong>How to answer:</strong> {q.tip}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      </div>

      <aside className="report__aside">
        <div className="sheet score-card">
          <ScoreMark score={a.score} />
          {r.ats && (
            <dl className="subscores">
              <div>
                <dt>Requirement match</dt>
                <dd>{r.match_score}%</dd>
                <div className="meter" aria-hidden="true"><span style={{ width: `${r.match_score}%` }} /></div>
              </div>
              <div>
                <dt>ATS readiness</dt>
                <dd>{r.ats.score}%</dd>
                <div className="meter" aria-hidden="true"><span style={{ width: `${r.ats.score}%` }} /></div>
              </div>
            </dl>
          )}
          <dl className="tally">
            <div><dt>Matched</dt><dd className="t-matched">{r.counts.matched}</dd></div>
            <div><dt>Partly</dt><dd className="t-partial">{r.counts.partial}</dd></div>
            <div><dt>Missing</dt><dd className="t-missing">{r.counts.missing}</dd></div>
          </dl>
          <p className="verdict">{verdict(a.score)}</p>
          {r.summary && <p className="summary">{r.summary}</p>}
          <Link to={`/ask?resume=${a.resume_id}&job=${a.job_id}`} className="btn btn--primary btn--block">
            <Icon name="chat" size={16} />
            Ask the agent about this job
          </Link>
        </div>
        {r.strengths?.length > 0 && (
          <section className="sheet">
            <h2 className="h3">Your strongest points</h2>
            <ul className="ticks">{r.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
          </section>
        )}
        {r.next_steps?.length > 0 && (
          <section className="sheet">
            <h2 className="h3">Before you apply</h2>
            <ul className="todo">{r.next_steps.map((s) => <li key={s}>{s}</li>)}</ul>
          </section>
        )}
        <button type="button" className="btn btn--quiet btn--sm" onClick={remove}>
          <Icon name="trash" size={15} />
          Delete this report
        </button>
      </aside>
      </div>

      <p className="small muted model-note">Analysed with {r.model}.</p>
    </article>
  );
}
