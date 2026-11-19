// Small wrapper around the JobFit API. In dev Vite proxies /api to :8000; in Docker nginx does.

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, options);
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return body;
}

const json = (method, data) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
});

export const api = {
  health: () => request('/health'),

  documents: (kind) => request(`/documents${kind ? `?kind=${kind}` : ''}`),
  document: (id) => request(`/documents/${id}`),
  deleteDocument: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
  addDocument: ({ kind, title, text, file }) => {
    const form = new FormData();
    form.append('kind', kind);
    if (title) form.append('title', title);
    if (file) form.append('file', file);
    else form.append('text', text || '');
    return request('/documents', { method: 'POST', body: form });
  },
  loadSamples: () => request('/samples', { method: 'POST' }),

  analyses: () => request('/analyses'),
  analysis: (id) => request(`/analyses/${id}`),
  deleteAnalysis: (id) => request(`/analyses/${id}`, { method: 'DELETE' }),
  analyze: (resumeId, jobId) => request('/analyses', json('POST', { resume_id: resumeId, job_id: jobId })),

  // Streams agent events (Server-Sent Events over a POST) and calls onEvent for each one.
  async askAgent({ resumeId, jobId, message, history }, onEvent, signal) {
    const res = await fetch('/api/agent/chat', {
      ...json('POST', { resume_id: resumeId, job_id: jobId, message, history }),
      signal,
    });
    if (!res.ok || !res.body) throw new Error(`Agent request failed (${res.status})`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)));
      }
    }
  },
};

export function timeAgo(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}
