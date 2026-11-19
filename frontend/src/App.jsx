import { useEffect, useState } from 'react';
import { Link, NavLink, Route, Routes, Navigate, useLocation } from 'react-router-dom';
import { api } from './api.js';
import Dashboard from './pages/Dashboard.jsx';
import NewAnalysis from './pages/NewAnalysis.jsx';
import Report from './pages/Report.jsx';
import Agent from './pages/Agent.jsx';
import Library from './pages/Library.jsx';
import { Icon, ScoreMark } from './components/ui.jsx';

const NAV = [
  ['/', 'Applications', 'list'],
  ['/new', 'Check a job', 'plus'],
  ['/ask', 'Ask the agent', 'chat'],
  ['/library', 'Library', 'folder'],
];

export default function App() {
  const [health, setHealth] = useState(null);
  const [recent, setRecent] = useState([]);
  const location = useLocation();
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: 'down' }));
  }, []);
  useEffect(() => {
    api.analyses().then((a) => setRecent(a.slice(0, 5))).catch(() => setRecent([]));
  }, [location.pathname]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="brand__mark" aria-hidden="true">
            <Icon name="check" />
          </span>
          JobFit
        </NavLink>
        <nav className="sidebar__nav" aria-label="Main">
          {NAV.map(([to, label, icon]) => (
            <NavLink key={to} to={to} end={to === '/'} className="navlink">
              <Icon name={icon} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        {recent.length > 0 && (
          <div className="recent">
            <h2 className="recent__title">Recent checks</h2>
            <ul>
              {recent.map((a) => (
                <li key={a.id}>
                  <Link to={`/report/${a.id}`} className={`recent__item ${location.pathname === `/report/${a.id}` ? 'is-on' : ''}`}>
                    <ScoreMark score={a.score} size="xs" />
                    <span className="recent__text">
                      <span className="recent__job">{a.job_title || 'Untitled job'}</span>
                      {a.company && <span className="recent__co">{a.company}</span>}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="sidebar__foot">
          {health?.status === 'down' ? (
            <span className="engine engine--down">API not reachable</span>
          ) : health ? (
            <span className={`engine ${health.demo_mode ? 'engine--demo' : ''}`}>
              {health.demo_mode ? 'Demo mode, no AI key' : `AI: ${health.model}`}
            </span>
          ) : null}
        </div>
      </aside>

      <main className="main">
        {health?.demo_mode && (
          <p className="demo-note">
            You are in demo mode: matching uses simple keyword rules. Add <code>LLM_API_KEY</code> to the{' '}
            <code>.env</code> file for real AI analysis.
          </p>
        )}
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewAnalysis />} />
          <Route path="/report/:id" element={<Report />} />
          <Route path="/ask" element={<Agent />} />
          <Route path="/library" element={<Library />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
