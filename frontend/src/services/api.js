const BASE = '/api';

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

export const buildSchedule   = (owner, pets) => post('/schedule',    { owner, pets });
export const buildAISchedule = (owner, pets) => post('/ai-schedule', { owner, pets });
