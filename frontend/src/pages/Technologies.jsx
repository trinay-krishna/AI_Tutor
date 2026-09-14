import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../api.js";

export default function Technologies() {
  const [techs, setTechs] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/technologies")
      .then(setTechs)
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <div className="page">{error}</div>;
  if (techs === null) return <div className="page">Loading…</div>;

  return (
    <div className="page">
      <h1>Pick a technology</h1>
      {techs.length === 0 && <p>No technologies have been onboarded yet. Ask an admin to add one.</p>}
      <div className="tech-grid">
        {techs.map((t) => (
          <Link key={t.id} to={`/learn/${t.slug}`} className="tech-card">
            <h3>{t.name}</h3>
            <p>{t.description || "No description yet."}</p>
            {t.ready_resource_count === 0 ? (
              <span className="badge badge-warning">No resources onboarded yet</span>
            ) : (
              <span className="badge badge-grounded">{t.ready_resource_count} resources</span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
