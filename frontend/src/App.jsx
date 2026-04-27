import { useState } from 'react';
import OwnerSetup   from './components/OwnerSetup';
import PetManager   from './components/PetManager';
import TaskManager  from './components/TaskManager';
import ScheduleView from './components/ScheduleView';
import './App.css';

const TABS = [
  { id: 'setup',    label: '👤 Setup'    },
  { id: 'tasks',    label: '📋 Tasks'    },
  { id: 'schedule', label: '🗓️ Schedule' },
];

export default function App() {
  const [tab, setTab] = useState('setup');

  const [owner, setOwner] = useState({
    name: '', available_start: '08:00', available_end: '20:00', saved: false,
  });

  const [pets, setPets] = useState([]);
  const [scheduleResult, setScheduleResult] = useState(null);

  const addPet = (petData) =>
    setPets(prev => [...prev, { ...petData, tasks: [], id: crypto.randomUUID() }]);

  const addTask = (petId, taskData) =>
    setPets(prev =>
      prev.map(p =>
        p.id === petId
          ? {
              ...p,
              tasks: [
                ...p.tasks,
                { ...taskData, task_id: crypto.randomUUID().slice(0, 8), completed: false },
              ],
            }
          : p
      )
    );

  const markTaskDone = (petId, taskId) =>
    setPets(prev =>
      prev.map(p =>
        p.id === petId
          ? { ...p, tasks: p.tasks.map(t => t.task_id === taskId ? { ...t, completed: true } : t) }
          : p
      )
    );

  return (
    <div className="app">
      <header className="app-header">
        <h1>🐾 PawPal+ AI</h1>
        <p>Smart, AI-powered pet care scheduling</p>
      </header>

      <nav className="tab-nav">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`tab-btn ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main>
        {tab === 'setup' && (
          <>
            <OwnerSetup owner={owner} setOwner={setOwner} />
            <PetManager pets={pets} addPet={addPet} ownerSaved={owner.saved} />
          </>
        )}

        {tab === 'tasks' && (
          <TaskManager pets={pets} addTask={addTask} />
        )}

        {tab === 'schedule' && (
          <ScheduleView
            owner={owner}
            pets={pets}
            scheduleResult={scheduleResult}
            setScheduleResult={setScheduleResult}
            markTaskDone={markTaskDone}
          />
        )}
      </main>
    </div>
  );
}
