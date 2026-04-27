const SPECIES_EMOJI = { dog: '🐶', cat: '🐱', other: '🐾' };

export default function PetManager({ pets, addPet, ownerSaved }) {
  const handleAdd = (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const name = fd.get('name').trim();
    if (!name) return;
    if (pets.some(p => p.name.toLowerCase() === name.toLowerCase())) {
      alert(`'${name}' is already registered.`);
      return;
    }
    addPet({
      name,
      species:   fd.get('species'),
      age_years: parseFloat(fd.get('age_years')) || 0,
    });
    e.target.reset();
  };

  return (
    <div className="card">
      <h2>🐾 Pets</h2>

      {!ownerSaved && (
        <div className="alert alert-info">Save your owner profile above before adding pets.</div>
      )}

      <form onSubmit={handleAdd}>
        <div className="form-row">
          <div className="form-group">
            <label>Pet name</label>
            <input name="name" placeholder="Mochi" disabled={!ownerSaved} />
          </div>
          <div className="form-group">
            <label>Species</label>
            <select name="species" disabled={!ownerSaved}>
              <option value="dog">Dog</option>
              <option value="cat">Cat</option>
            </select>
          </div>
          <div className="form-group">
            <label>Age (years)</label>
            <input name="age_years" type="number" min="0" max="30" step="0.5"
                   defaultValue="1" disabled={!ownerSaved} />
          </div>
        </div>
        <button className="btn btn-primary" type="submit" disabled={!ownerSaved}>
          ➕ Add Pet
        </button>
      </form>

      {pets.length > 0 && (
        <>
          <p className="section-title">Registered pets</p>
          <ul className="pet-list">
            {pets.map(p => (
              <li key={p.id} className="pet-item">
                <span className="pet-avatar">{SPECIES_EMOJI[p.species] ?? '🐾'}</span>
                <div className="pet-info">
                  <div className="pet-name">{p.name}</div>
                  <div className="pet-meta">
                    {p.species} · {p.age_years}y · {p.tasks.filter(t => !t.completed).length} pending task(s)
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {pets.length === 0 && ownerSaved && (
        <div className="empty">No pets yet — add one above.</div>
      )}
    </div>
  );
}
