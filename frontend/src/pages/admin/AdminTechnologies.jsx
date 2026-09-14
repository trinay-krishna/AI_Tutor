import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api.js";

export default function AdminTechnologies() {
  const [techs, setTechs] = useState(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function load() {
    api.get("/technologies").then(setTechs);
  }

  useEffect(load, []);

  async function handleCreate(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/technologies", { name, description: description || null });
      setName("");
      setDescription("");
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this technology and all its resources?")) return;
    await api.delete(`/technologies/${id}`);
    load();
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Admin: Technologies</h1>
      </div>

      <form onSubmit={handleCreate} className="auth-form" style={{ maxWidth: 480, marginBottom: 32 }}>
        <h2>Add a technology</h2>
        {error && <p className="form-error">{error}</p>}
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Description
          <input value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? "Adding…" : "Add technology"}
        </button>
      </form>

      {techs === null ? (
        <p>Loading…</p>
      ) : (
        <table className="resource-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Ready resources</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {techs.map((t) => (
              <tr key={t.id}>
                <td>
                  <Link to={`/admin/${t.slug}`}>{t.name}</Link>
                </td>
                <td>{t.ready_resource_count}</td>
                <td>
                  <button className="btn btn-danger" onClick={() => handleDelete(t.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
