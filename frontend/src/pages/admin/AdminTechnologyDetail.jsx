import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { api } from "../../api.js";

const ACTIVE_STATUSES = new Set(["pending", "processing"]);

export default function AdminTechnologyDetail() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [tech, setTech] = useState(null);
  const [resources, setResources] = useState(null);
  const [urlsText, setUrlsText] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const pollRef = useRef(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);

  const loadResources = useCallback(async (technologyId) => {
    const list = await api.get(`/technologies/${technologyId}/resources`);
    setResources(list);
    return list;
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.get("/technologies").then(async (list) => {
      if (cancelled) return;
      const found = list.find((t) => t.slug === slug);
      if (!found) {
        navigate("/admin", { replace: true });
        return;
      }
      setTech(found);
      await loadResources(found.id);
    });
    return () => {
      cancelled = true;
    };
  }, [slug, navigate, loadResources]);

  // Poll while anything is still pending/processing.
  useEffect(() => {
    if (!tech) return undefined;
    clearInterval(pollRef.current);
    const hasActive = resources?.some((r) => ACTIVE_STATUSES.has(r.status));
    if (hasActive) {
      pollRef.current = setInterval(() => loadResources(tech.id), 3000);
    }
    return () => clearInterval(pollRef.current);
  }, [tech, resources, loadResources]);

  async function handleAddUrls(e) {
    e.preventDefault();
    setError(null);
    const urls = urlsText
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length === 0) return;
    setSubmitting(true);
    try {
      const result = await api.post(`/technologies/${tech.id}/resources`, { urls });
      setUrlsText("");
      if (result.skipped.length > 0) {
        setError(`Skipped ${result.skipped.length} duplicate URL(s).`);
      }
      await loadResources(tech.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRetry(id) {
    await api.post(`/resources/${id}/reingest`);
    await loadResources(tech.id);
  }

  async function handleDelete(id) {
    if (!confirm("Remove this resource and its indexed content?")) return;
    await api.delete(`/resources/${id}`);
    await loadResources(tech.id);
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const hits = await api.post(`/technologies/${tech.id}/search`, { query: searchQuery, k: 8 });
      setSearchResults(hits);
    } finally {
      setSearching(false);
    }
  }

  if (!tech) return <div className="page">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>{tech.name}</h1>
      </div>

      <form onSubmit={handleAddUrls} style={{ marginBottom: 24 }}>
        <label>
          Add resource URLs (one per line)
          <textarea
            className="url-textarea"
            value={urlsText}
            onChange={(e) => setUrlsText(e.target.value)}
            placeholder={"https://react.dev/learn\nhttps://react.dev/reference/react/useEffect"}
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={submitting} style={{ marginTop: 8 }}>
          {submitting ? "Adding…" : "Add URLs"}
        </button>
      </form>

      {resources === null ? (
        <p>Loading resources…</p>
      ) : resources.length === 0 ? (
        <p>No resources yet.</p>
      ) : (
        <table className="resource-table">
          <thead>
            <tr>
              <th>URL</th>
              <th>Status</th>
              <th>Chunks</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {resources.map((r) => (
              <tr key={r.id}>
                <td>
                  <div>{r.title || r.url}</div>
                  <div style={{ fontSize: 12, opacity: 0.7 }}>{r.url}</div>
                  {r.error && <div className="form-error">{r.error}</div>}
                </td>
                <td>
                  <span className={`status-pill status-${r.status}`}>{r.status}</span>
                </td>
                <td>{r.chunk_count}</td>
                <td style={{ display: "flex", gap: 8 }}>
                  <button className="btn" onClick={() => handleRetry(r.id)}>
                    Retry
                  </button>
                  <button className="btn btn-danger" onClick={() => handleDelete(r.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2 style={{ marginTop: 32 }}>Test retrieval</h2>
      <form onSubmit={handleSearch} style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          style={{ flex: 1, padding: 8, border: "1px solid var(--border)", borderRadius: 6 }}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="e.g. useEffect cleanup"
        />
        <button type="submit" className="btn btn-primary" disabled={searching}>
          {searching ? "Searching…" : "Search"}
        </button>
      </form>
      {searchResults !== null && (
        <div>
          {searchResults.length === 0 ? (
            <p>No chunks found.</p>
          ) : (
            searchResults.map((h) => (
              <div key={h.chunk_id} style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
                <div style={{ fontSize: 12, opacity: 0.7 }}>
                  score {h.score.toFixed(3)} · {h.title} {h.heading_path ? `> ${h.heading_path}` : ""}
                </div>
                <div style={{ fontSize: 13 }}>{h.content.slice(0, 300)}…</div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
