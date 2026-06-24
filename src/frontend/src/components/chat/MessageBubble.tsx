import { useState } from "react";
import { ThumbsUp, ThumbsDown, Bot } from "lucide-react";
import ReactMarkdown from "react-markdown";
import clsx from "clsx";
import type { Message } from "@/types/chat";
import { formatRelativeTime, formatConfidence } from "@/utils/helpers";
import Badge from "@/components/common/Badge";
import SourcesList from "./SourcesList";

interface MessageBubbleProps {
  message: Message;
  onFeedback?: (messageId: string, wasHelpful: boolean) => void;
}

export default function MessageBubble({ message, onFeedback }: MessageBubbleProps) {
  const [feedbackGiven, setFeedbackGiven] = useState<boolean | null>(null);
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

  function handleFeedback(wasHelpful: boolean) {
    if (feedbackGiven !== null) return;
    setFeedbackGiven(wasHelpful);
    onFeedback?.(message.id, wasHelpful);
  }

  return (
    <div
      className={clsx(
        "flex gap-3 max-w-[85%]",
        isUser ? "ml-auto flex-row-reverse" : "mr-auto",
      )}
    >
      {isAssistant && (
        <div className="flex items-start pt-1">
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 shrink-0">
            <Bot size={16} className="text-slate-600" />
          </div>
        </div>
      )}

      <div className="min-w-0 space-y-1">
        {isAssistant && message.agent_name && (
          <p className="text-xs text-gray-500 font-medium px-1">
            {message.agent_name}
          </p>
        )}

        <div
          className={clsx(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-blue-600 text-white rounded-br-md"
              : "bg-gray-100 text-gray-900 rounded-bl-md",
          )}
        >
          {isAssistant ? (
            <div className="prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-code:text-sm prose-pre:bg-gray-800 prose-pre:text-gray-100">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
        </div>

        {isAssistant && message.confidence !== undefined && (
          <div className="px-1">
            <Badge
              variant={
                message.confidence >= 0.8
                  ? "success"
                  : message.confidence >= 0.5
                    ? "warning"
                    : "danger"
              }
            >
              Confidence: {formatConfidence(message.confidence)}
            </Badge>
          </div>
        )}

        {isAssistant && message.rag_context?.sources && message.rag_context.sources.length > 0 && (
          <SourcesList sources={message.rag_context.sources} />
        )}

        <div
          className={clsx(
            "flex items-center gap-2 px-1",
            isUser ? "justify-end" : "justify-start",
          )}
        >
          <span className="text-xs text-gray-400">
            {formatRelativeTime(message.created_at)}
          </span>

          {isAssistant && (
            <div className="flex items-center gap-1 ml-1">
              <button
                type="button"
                onClick={() => handleFeedback(true)}
                disabled={feedbackGiven !== null}
                className={clsx(
                  "p-1 rounded transition-colors",
                  feedbackGiven === true
                    ? "text-green-600"
                    : "text-gray-300 hover:text-gray-500 disabled:opacity-50",
                )}
                aria-label="Helpful"
              >
                <ThumbsUp size={12} />
              </button>
              <button
                type="button"
                onClick={() => handleFeedback(false)}
                disabled={feedbackGiven !== null}
                className={clsx(
                  "p-1 rounded transition-colors",
                  feedbackGiven === false
                    ? "text-red-600"
                    : "text-gray-300 hover:text-gray-500 disabled:opacity-50",
                )}
                aria-label="Not helpful"
              >
                <ThumbsDown size={12} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
