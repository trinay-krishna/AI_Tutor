import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router";
import { api } from "../api.js";
import MessageBubble from "../components/MessageBubble.jsx";

function starterPrompts(techName) {
  return [
    `How do I get started with ${techName}?`,
    `What is ${techName} used for?`,
    `Create me a 4-week study plan to learn ${techName} from beginner to advanced.`,
  ];
}

export default function Chat() {
  const { slug } = useParams();
  const [tech, setTech] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api.get("/technologies").then((list) => {
      if (cancelled) return;
      setTech(list.find((t) => t.slug === slug) || null);
    });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  useEffect(() => {
    if (!tech) return undefined;
    let cancelled = false;
    api.get(`/conversations?technology_id=${tech.id}`).then((list) => {
      if (cancelled) return;
      setConversations(list);
      if (list.length > 0) setActiveId(list[0].id);
    });
    return () => {
      cancelled = true;
    };
  }, [tech]);

  useEffect(() => {
    let cancelled = false;
    const fetchMessages = activeId ? api.get(`/conversations/${activeId}`) : Promise.resolve({ messages: [] });
    fetchMessages.then((c) => {
      if (!cancelled) setMessages(c.messages);
    });
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleNewChat() {
    const conv = await api.post("/conversations", { technology_id: tech.id });
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
    setMessages([]);
  }

  async function sendContent(content) {
    if (!content.trim() || sending) return;
    setError(null);
    let conversationId = activeId;
    if (!conversationId) {
      const conv = await api.post("/conversations", { technology_id: tech.id });
      setConversations((prev) => [conv, ...prev]);
      conversationId = conv.id;
      setActiveId(conversationId);
    }

    setSending(true);
    setInput("");
    try {
      const result = await api.post(`/conversations/${conversationId}/messages`, { content });
      setMessages((prev) => [...prev, result.user_message, result.assistant_message]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    sendContent(input);
  }

  if (!tech) return <div className="page">Loading…</div>;

  return (
    <div className="page">
      <h1>{tech.name} Tutor</h1>
      {tech.ready_resource_count === 0 && (
        <p className="badge badge-warning">
          No resources onboarded yet for {tech.name} -- answers will use general knowledge only.
        </p>
      )}

      <div className="chat-layout">
        <div className="chat-sidebar">
          <button className="btn btn-primary" style={{ width: "100%", marginBottom: 12 }} onClick={handleNewChat}>
            New chat
          </button>
          {conversations.map((c) => (
            <a
              key={c.id}
              className={`chat-sidebar-item ${c.id === activeId ? "active" : ""}`}
              onClick={() => setActiveId(c.id)}
            >
              {c.title || "New conversation"}
            </a>
          ))}
        </div>

        <div className="chat-main">
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="chat-starters">
                {starterPrompts(tech.name).map((p) => (
                  <button key={p} className="chat-starter" onClick={() => sendContent(p)}>
                    {p}
                  </button>
                ))}
              </div>
            )}
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {sending && (
              <MessageBubble message={{ role: "assistant", content: "Thinking…" }} pending />
            )}
            <div ref={messagesEndRef} />
          </div>

          {error && <p className="form-error">{error}</p>}

          <form className="chat-input-row" onSubmit={handleSubmit}>
            <textarea
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendContent(input);
                }
              }}
              placeholder={`Ask about ${tech.name}...`}
            />
            <button type="submit" className="btn btn-primary" disabled={sending}>
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
