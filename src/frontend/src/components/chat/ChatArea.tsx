import { useEffect, useRef, useState, useCallback } from "react";
import { AlertTriangle, Loader2, MessageSquare } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import * as chatService from "@/services/chat.service";
import type { Message } from "@/types/chat";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import Loading from "@/components/common/Loading";
import EmptyState from "@/components/common/EmptyState";

interface ChatAreaProps {
  conversationId: string;
}

export default function ChatArea({ conversationId }: ChatAreaProps) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const firmId = user?.firm_id ?? "";
  const scrollRef = useRef<HTMLDivElement>(null);
  const [qualityWarning, setQualityWarning] = useState<string | null>(null);

  const {
    data: messages,
    isPending,
    error,
  } = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: async () => {
      const result = await chatService.getConversationHistory(conversationId, firmId);
      return result.items;
    },
    enabled: !!conversationId && !!firmId,
  });

  const sendMutation = useMutation({
    mutationFn: (content: string) =>
      chatService.sendMessage(conversationId, content, firmId, user?.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["case-conversations"] });
    },
  });

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  function handleSend(content: string) {
    sendMutation.mutate(content);
  }

  function handleFeedback(messageId: string, wasHelpful: boolean) {
    chatService.submitFeedback(messageId, firmId, wasHelpful).catch(() => {
      // Fire-and-forget — feedback submission failure is non-blocking
    });
  }

  if (isPending) {
    return <Loading size="md" text="Loading messages..." />;
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <p className="text-sm text-red-600">
          Failed to load messages. Please try again.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {qualityWarning && (
        <div className="flex items-center gap-2 px-4 py-2.5 bg-yellow-50 border-b border-yellow-200 text-sm text-yellow-800">
          <AlertTriangle size={16} className="shrink-0" />
          <p>{qualityWarning}</p>
        </div>
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages && messages.length > 0 ? (
          messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              onFeedback={handleFeedback}
            />
          ))
        ) : (
          <EmptyState
            icon={MessageSquare}
            title="Start a conversation"
            description="Ask a legal question and the AI assistant will research and respond with relevant case law and analysis."
          />
        )}

        {sendMutation.isPending && (
          <div className="flex items-center gap-2 text-sm text-gray-500 ml-11">
            <Loader2 size={14} className="animate-spin" />
            <span>Researching your question...</span>
          </div>
        )}
      </div>

      <ChatInput
        onSend={handleSend}
        isProcessing={sendMutation.isPending}
      />
    </div>
  );
}
