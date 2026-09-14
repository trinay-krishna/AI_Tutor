export default function SourceList({ sources }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="chat-sources">
      <strong>Sources</strong>
      <ol>
        {sources.map((s) => (
          <li key={s.n} style={{ opacity: s.cited ? 1 : 0.6 }}>
            <a href={s.url} target="_blank" rel="noreferrer">
              {s.title || s.url}
            </a>
            {s.heading_path && <span> — {s.heading_path}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}
