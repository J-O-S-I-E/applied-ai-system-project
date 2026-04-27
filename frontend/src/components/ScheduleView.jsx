import { useState } from 'react';
import { buildSchedule, buildAISchedule } from '../services/api';

const PRIORITY_EMOJI = { HIGH: '🔴', MEDIUM: '🟡', LOW: '🟢' };

function Spinner({ text }) {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      <span>{text}</span>
    </div>
  );
}

function Metrics({ result }) {
  return (
    <div className="metrics-row">
      {[
        { value: result.scheduled.length,          label: 'Scheduled'   },
        { value: result.skipped.length,            label: 'Skipped'     },
        { value: `${result.total_minutes} min`,    label: 'Time used'   },
        { value: `${result.utilization_pct}%`,     label: 'Utilization' },
      ].map(m => (
        <div key={m.label} className="metric-card">
          <div className="value">{m.value}</div>
          <div className="label">{m.label}</div>
        </div>
      ))}
    </div>
  );
}

function ScheduleTable({ tasks, onMarkDone }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Start</th>
            <th>End</th>
            <th>Task</th>
            <th>Priority</th>
            <th>Min</th>
            <th>Notes</th>
            {onMarkDone && <th></th>}
          </tr>
        </thead>
        <tbody>
          {tasks.map(t => (
            <tr key={t.task_id}>
              <td>{PRIORITY_EMOJI[t.priority]}</td>
              <td>{t.scheduled_start}</td>
              <td>{t.scheduled_end}</td>
              <td>{t.title}</td>
              <td><span className={`badge badge-${t.priority}`}>{t.priority}</span></td>
              <td>{t.duration_minutes}</td>
              <td style={{ color: 'var(--muted)' }}>{t.notes || '—'}</td>
              {onMarkDone && (
                <td>
                  <button
                    className="btn btn-success btn-sm"
                    onClick={() => onMarkDone(t.task_id)}
                  >
                    ✓ Done
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ValidationPanel({ validation }) {
  const color = validation.passed ? 'var(--success)' : 'var(--danger)';
  return (
    <div>
      <div className="score-bar-wrap">
        <div
          className="score-bar"
          style={{ width: `${validation.score}%`, background: color }}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: '.5rem' }}>
        <span style={{ fontWeight: 600, color }}>
          {validation.passed ? '✅ Passed' : '❌ Issues found'}
        </span>
        <span style={{ color: 'var(--muted)', fontSize: '.85rem' }}>
          Score: {validation.score}/100
        </span>
      </div>
      {validation.issues.map((issue, i) => (
        <div key={i} className="alert alert-danger">{issue}</div>
      ))}
      {validation.warnings.map((warn, i) => (
        <div key={i} className="alert alert-warning">{warn}</div>
      ))}
    </div>
  );
}

const SPECIES_EMOJI = { dog: '🐕', cat: '🐈' };

function PetRAGSection({ pg }) {
  const [open, setOpen] = useState(false);
  const emoji = SPECIES_EMOJI[pg.species] ?? '🐾';
  return (
    <div className="rag-section">
      <button className="rag-toggle" onClick={() => setOpen(o => !o)}>
        <span>{emoji} {pg.pet_name} — {pg.species.charAt(0).toUpperCase() + pg.species.slice(1)}, {pg.age_years} yrs</span>
        <span className="rag-badge">{pg.passages.length}</span>
        <span className="rag-chevron">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="rag-grid">
          {pg.passages.map((p, i) => (
            <div key={i} className="rag-card">
              <span className="rag-quote-mark">❝</span>
              <div>
                <p className="rag-card-text">{p.text}</p>
                {p.source && (
                  <span className="rag-source-tag">
                    {p.source.replace('.pdf', '').replace('-', ' ')}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RAGPanel({ petGuidelines }) {
  if (!petGuidelines?.length) return null;
  return (
    <div style={{ marginTop: '.75rem' }}>
      <p className="section-title">📖 Pet Care Guide Passages</p>
      {petGuidelines.map((pg) => (
        <PetRAGSection key={pg.pet_name} pg={pg} />
      ))}
    </div>
  );
}

function AIPanel({ ai, petGuidelines }) {
  return (
    <div className="ai-panel">
      <h3>🧠 AI Analysis</h3>

      <RAGPanel petGuidelines={petGuidelines} />

      {ai.error ? (
        <div className="alert alert-warning">
          Gemini unavailable: {ai.error}
        </div>
      ) : (
        <>
          {ai.explanation && (
            <div className="alert alert-info" style={{ marginTop: '.75rem' }}>
              {ai.explanation}
            </div>
          )}

          {ai.reasoning && (
            <>
              <p className="section-title">🤖 Step-by-Step Reasoning</p>
              <div className="reasoning-box">{ai.reasoning}</div>
            </>
          )}

          {ai.recommendations?.length > 0 && (
            <>
              <p className="section-title">💡 Recommendations</p>
              <ul className="rec-list">
                {ai.recommendations.map((r, i) => (
                  <li key={i} className="rec-item">{r}</li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default function ScheduleView({ owner, pets, scheduleResult, setScheduleResult, markTaskDone }) {
  const [loading, setLoading] = useState(false);
  const [aiMode,  setAiMode]  = useState(false);
  const [error,   setError]   = useState(null);

  const allPending = pets.flatMap(p => p.tasks.filter(t => !t.completed));

  const run = async (withAI) => {
    if (!owner.saved) { setError('Save your owner profile first.'); return; }
    if (pets.length === 0) { setError('Add at least one pet first.'); return; }
    if (allPending.length === 0) { setError('Add at least one task first.'); return; }

    setLoading(true);
    setError(null);
    setAiMode(withAI);
    setScheduleResult(null);

    try {
      const fn  = withAI ? buildAISchedule : buildSchedule;
      const res = await fn(
        { name: owner.name, available_start: owner.available_start, available_end: owner.available_end },
        pets.map(p => ({
          name: p.name, species: p.species, age_years: p.age_years, tasks: p.tasks,
        }))
      );
      setScheduleResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkDone = (taskId) => {
    const pet = pets.find(p => p.tasks.some(t => t.task_id === taskId));
    if (pet) markTaskDone(pet.id, taskId);
    setScheduleResult(null);  // force rebuild after marking done
  };

  return (
    <div className="card">
      <h2>🗓️ Generate Schedule</h2>

      {allPending.length === 0 && (
        <div className="alert alert-info">Add tasks in the Tasks tab before generating a schedule.</div>
      )}

      <div className="btn-row">
        <button
          className="btn btn-primary btn-full"
          onClick={() => run(false)}
          disabled={loading || allPending.length === 0}
        >
          ⚡ Build Schedule (Fast)
        </button>
        <button
          className="btn btn-ai btn-full"
          onClick={() => run(true)}
          disabled={loading || allPending.length === 0}
        >
          🧠 Generate AI Schedule
        </button>
      </div>

      {loading && (
        <div style={{ marginTop: '1rem' }}>
          <Spinner text={aiMode ? 'Running AI analysis…' : 'Building schedule…'} />
        </div>
      )}

      {error && <div className="alert alert-danger" style={{ marginTop: '1rem' }}>{error}</div>}

      {scheduleResult && !loading && (
        <div style={{ marginTop: '1.25rem' }}>
          <Metrics result={scheduleResult} />

          {scheduleResult.conflicts.length > 0 ? (
            <div className="alert alert-danger">
              ⚠️ Conflicts: {scheduleResult.conflicts.join(', ')}
            </div>
          ) : (
            <div className="alert alert-success">✅ No conflicts — schedule is clean.</div>
          )}

          {scheduleResult.scheduled.length > 0 && (
            <>
              <p className="section-title">Scheduled tasks</p>
              <ScheduleTable
                tasks={scheduleResult.scheduled}
                onMarkDone={handleMarkDone}
              />
            </>
          )}

          {scheduleResult.skipped.length > 0 && (
            <>
              <p className="section-title">Skipped (didn't fit)</p>
              <ScheduleTable tasks={scheduleResult.skipped} />
            </>
          )}

          {/* AI section — only present when AI schedule was requested */}
          {scheduleResult.validation && (
            <>
              <p className="section-title">🛡️ Guardrail Validation</p>
              <ValidationPanel validation={scheduleResult.validation} />
            </>
          )}

          {(scheduleResult.ai || scheduleResult.pet_guidelines?.length > 0) && (
            <AIPanel ai={scheduleResult.ai} petGuidelines={scheduleResult.pet_guidelines} />
          )}
        </div>
      )}
    </div>
  );
}
