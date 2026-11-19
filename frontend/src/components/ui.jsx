import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const PATHS = {
  list: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
  plus: 'M12 5v14M5 12h14',
  chat: 'M4 5h16v11H9l-5 4z',
  folder: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M6 6l12 12M18 6L6 18',
  tilde: 'M5 13c2-3 4-3 7 0s5 3 7 0',
  upload: 'M12 16V4M7 9l5-5 5 5M5 20h14',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
  copy: 'M9 9h10v11H9zM5 15V4h10',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4',
  send: 'M5 12h13M13 6l6 6-6 6',
  doc: 'M7 3h7l5 5v13H7zM14 3v5h5',
  spark: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6',
  back: 'M19 12H6M11 6l-6 6 6 6',
  chevron: 'M9 6l6 6-6 6',
};

export function Icon({ name, size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="icon">
      <path d={PATHS[name]} />
    </svg>
  );
}

export function Spinner({ label }) {
  return (
    <span className="spinner" role="status">
      <span className="spinner__dot" aria-hidden="true" />
      {label && <span>{label}</span>}
    </span>
  );
}

const STATUS = {
  matched: { label: 'Matched', icon: 'check' },
  partial: { label: 'Partly', icon: 'tilde' },
  missing: { label: 'Missing', icon: 'x' },
};

export function StatusPill({ status }) {
  const s = STATUS[status];
  return (
    <span className={`pill pill--${status}`}>
      <Icon name={s.icon} size={14} />
      {s.label}
    </span>
  );
}

// The memorable bit: the score, circled in blue pen like a teacher's grade.
export function ScoreMark({ score, size = 'lg' }) {
  const tone = score >= 75 ? 'strong' : score >= 50 ? 'fair' : 'weak';
  return (
    <div className={`score score--${size} score--${tone}`}>
      <svg viewBox="0 0 120 100" aria-hidden="true" className="score__ring">
        <path
          pathLength="1"
          d="M64 10c-30-2-54 14-54 40 0 25 22 42 50 41 29-1 52-17 51-43C110 24 88 10 58 13c-9 1-17 4-23 8"
        />
      </svg>
      <span className="score__num">
        {score}
        <small>%</small>
      </span>
      <span className="sr-only">Fit score {score} percent</span>
    </div>
  );
}

// A thin stacked bar: green matched, yellow partial, red missing.
export function FitBar({ counts }) {
  const total = (counts.matched || 0) + (counts.partial || 0) + (counts.missing || 0) || 1;
  return (
    <div className="fitbar" aria-label={`${counts.matched || 0} matched, ${counts.partial || 0} partly, ${counts.missing || 0} missing`}>
      {['matched', 'partial', 'missing'].map((k) =>
        counts[k] ? <span key={k} className={`fitbar__seg fitbar__seg--${k}`} style={{ flexGrow: counts[k] / total }} /> : null
      )}
    </div>
  );
}

export function Highlight({ children, tone = 'matched' }) {
  return <mark className={`hl hl--${tone}`}>{children}</mark>;
}

export function CopyButton({ text }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="btn btn--quiet btn--sm"
      onClick={() => {
        navigator.clipboard?.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
    >
      <Icon name={done ? 'check' : 'copy'} size={15} />
      {done ? 'Copied' : 'Copy'}
    </button>
  );
}

// Renders the agent's Markdown answer. [R3] / [J2] citations become clickable chips.
export function RichText({ text, onCite }) {
  const prepared = text
    .replace(/【\s*([RJ]\d+)[^】]*】/g, '[$1]')
    .replace(/【[^】]*】/g, '')
    .split('\n')
    .map((ln) => ln.replace(/<br\s*\/?>/gi, ln.trimStart().startsWith('|') ? '; ' : '\n'))
    .join('\n')
    .replace(/\[([RJ]\d+)\](?!\()/g, '[$1](#cite-$1)');
  return (
    <div className="rich">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const m = href?.match(/^#cite-([RJ]\d+)$/);
            if (m)
              return (
                <button type="button" className={`cite cite--${m[1][0]}`} onClick={() => onCite?.(m[1])}>
                  {m[1]}
                </button>
              );
            return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
          },
          table: ({ children }) => (
            <div className="table-wrap">
              <table>{children}</table>
            </div>
          ),
          h1: ({ children }) => <h3>{children}</h3>,
          h2: ({ children }) => <h3>{children}</h3>,
        }}
      >
        {prepared}
      </ReactMarkdown>
    </div>
  );
}
