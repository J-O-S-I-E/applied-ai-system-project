export default function OwnerSetup({ owner, setOwner }) {
  const handleSave = (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    setOwner({
      name:            fd.get('name').trim(),
      available_start: fd.get('available_start'),
      available_end:   fd.get('available_end'),
      saved: true,
    });
  };

  return (
    <div className="card">
      <h2>👤 Owner Setup</h2>
      <form onSubmit={handleSave}>
        <div className="form-row">
          <div className="form-group">
            <label>Your name</label>
            <input name="name" defaultValue={owner.name} placeholder="Jordan" required />
          </div>
          <div className="form-group">
            <label>Available from</label>
            <input name="available_start" type="time" defaultValue={owner.available_start} required />
          </div>
          <div className="form-group">
            <label>Available until</label>
            <input name="available_end" type="time" defaultValue={owner.available_end} required />
          </div>
        </div>
        <button className="btn btn-primary" type="submit">💾 Save Owner</button>
      </form>
      {owner.saved && (
        <div className="alert alert-success" style={{ marginTop: '0.75rem' }}>
          Saved! Hello, {owner.name} 👋 — window {owner.available_start}–{owner.available_end}
        </div>
      )}
    </div>
  );
}
