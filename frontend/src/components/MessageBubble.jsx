import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SourceList from "./SourceList.jsx";

function modeBadge(mode) {
  if (mode === "grounded") return <span className="badge badge-grounded">From the docs</span>;
  if (mode === "general") return <span className="badge badge-general">General knowledge</span>;
  if (mode === "refusal") return <span className="badge badge-refusal">Out of scope</span>;
  return null;
}

export default function MessageBubble({ message, pending }) {
  const isUser = message.role === "user";

  return (
    <div className={`chat-message ${isUser ? "user" : "assistant"} ${pending ? "pending" : ""}`}>
      {!isUser && modeBadge(message.mode)}
      <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
      {!isUser && <SourceList sources={message.sources} />}
    </div>
  );
}
