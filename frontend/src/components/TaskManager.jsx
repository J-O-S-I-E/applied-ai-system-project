import { useState } from 'react';

const PRIORITY_EMOJI = { HIGH: '🔴', MEDIUM: '🟡', LOW: '🟢' };

export default function TaskManager({ pets, addTask }) {
  const [selectedPetId, setSelectedPetId] = useState('');

  if (pets.length === 0) {
    return (
      <div className="card">
        <h2>📋 Tasks</h2>
        <div className="alert alert-info">Add at least one pet in the Setup tab first.</div>
      </div>
    );
  }

  const activePetId = selectedPetId || pets[0].id;
  const activePet   = pets.find(p => p.id === activePetId) ?? pets[0];

  const handleAdd = (e) => {
    e.preventDefault();
    const fd   = new FormData(e.target);
    const title = fd.get('title').trim();
    if (!title) return;
    addTask(activePetId, {
      title,
      duration_minutes: parseInt(fd.get('duration'), 10),
      priority:         fd.get('priority'),
      preferred_time:   fd.get('preferred_time') || null,
      recurring:        fd.get('recurring') === 'on',
      notes:            fd.get('notes').trim(),
    });
    e.target.reset();
  };

  return (
    <div>
      {/* Pet selector */}
      <div className="card">
        <h2>📋 Tasks</h2>
        <div className="form-row">
          <div className="form-group">
            <label>Assign to pet</label>
            <select
              value={activePetId}
              onChange={e => setSelectedPetId(e.target.value)}
            >
              {pets.map(p => (
                <option key={p.id} value={p.id}>{p.name} ({p.species})</option>
              ))}
            </select>
          </div>
        </div>

        <form onSubmit={handleAdd}>
          <div className="form-row">
            <div className="form-group" style={{ flex: 2 }}>
              <label>Task title</label>
              <input name="title" placeholder="Morning walk" required />
            </div>
            <div className="form-group">
              <label>Duration (min)</label>
              <input name="duration" type="number" min="1" max="480" defaultValue="30" required />
            </div>
            <div className="form-group">
              <label>Priority</label>
              <select name="priority" defaultValue="MEDIUM">
                <option value="HIGH">🔴 High</option>
                <option value="MEDIUM">🟡 Medium</option>
                <option value="LOW">🟢 Low</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Preferred time</label>
              <select name="preferred_time">
                <option value="">No preference</option>
                <option value="morning">Morning</option>
                <option value="afternoon">Afternoon</option>
                <option value="evening">Evening</option>
              </select>
            </div>
            <div className="form-group" style={{ flex: 2 }}>
              <label>Notes (optional)</label>
              <input name="notes" placeholder="e.g. Give with food" />
            </div>
          </div>
          <div className="checkbox-row">
            <input name="recurring" type="checkbox" id="recurring" />
            <label htmlFor="recurring">Recurring — repeats daily</label>
          </div>
          <button className="btn btn-primary" type="submit" style={{ marginTop: '.5rem' }}>
            ➕ Add Task
          </button>
        </form>
      </div>

      {/* Task list per pet */}
      {pets.map(pet => {
        const pending = pet.tasks.filter(t => !t.completed);
        if (pending.length === 0) return null;
        return (
          <div key={pet.id} className="card">
            <h2>{pet.name} — {pending.length} pending task(s)</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th></th>
                    <th>Task</th>
                    <th>Min</th>
                    <th>Priority</th>
                    <th>Time</th>
                    <th>Recurring</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {pending.map(t => (
                    <tr key={t.task_id}>
                      <td>{PRIORITY_EMOJI[t.priority]}</td>
                      <td>{t.title}</td>
                      <td>{t.duration_minutes}</td>
                      <td><span className={`badge badge-${t.priority}`}>{t.priority}</span></td>
                      <td>{t.preferred_time ?? '—'}</td>
                      <td>{t.recurring ? '🔁' : '—'}</td>
                      <td style={{ color: 'var(--muted)' }}>{t.notes || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
