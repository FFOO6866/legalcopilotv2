import { useState } from "react";
import { Plus, Search, MessageSquare } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useAuthStore } from "@/stores/authStore";
import * as chatService from "@/services/chat.service";
import type { Conversation } from "@/types/chat";
import { formatRelativeTime } from "@/utils/helpers";
import Badge from "@/components/common/Badge";
import Button from "@/components/common/Button";
import Input from "@/components/common/Input";
import Loading from "@/components/common/Loading";
import EmptyState from "@/components/common/EmptyState";
import ChatArea from "./ChatArea";

const typeBadgeVariant: Record<string, "info" | "success" | "warning" | "neutral"> = {
  legal_research: "info",
  document_drafting: "success",
  case_analysis: "warning",
  general: "neutral",
};

export default function ChatView() {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSidebar, setShowSidebar] = useState(true);

  const {
    data: conversations,
    isPending,
    error,
  } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => chatService.listConversations(user?.firm_id ?? ""),
    enabled: !!user,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      chatService.createConversation(
        user?.firm_id ?? "",
        user?.id ?? "",
        undefined,
        "general",
      ),
    onSuccess: (newConversation) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setActiveConversationId(newConversation.id);
    },
  });

  const filteredConversations = conversations?.filter((conv) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      (conv.title?.toLowerCase().includes(query)) ??
      conv.conversation_type.toLowerCase().includes(query)
    );
  });

  function handleNewConversation() {
    createMutation.mutate();
  }

  return (
    <div className="flex h-[calc(100dvh-theme(spacing.16)-theme(spacing.12))] -mx-4 -my-6 sm:-mx-6 lg:-mx-8">
      {/* Conversation list sidebar */}
      <div
        className={clsx(
          "flex flex-col border-r border-gray-200 bg-white",
          showSidebar ? "w-80 shrink-0" : "hidden",
          "max-lg:absolute max-lg:inset-y-0 max-lg:left-0 max-lg:z-20 max-lg:w-80",
        )}
      >
        <div className="p-4 border-b border-gray-100 space-y-3">
          <Button
            variant="primary"
            size="md"
            className="w-full"
            onClick={handleNewConversation}
            isLoading={createMutation.isPending}
          >
            <Plus size={16} />
            New Conversation
          </Button>
          <Input
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            icon={Search}
          />
        </div>

        <div className="flex-1 overflow-y-auto">
          {isPending && <Loading size="sm" text="Loading..." />}

          {error && (
            <p className="p-4 text-sm text-red-600">
              Failed to load conversations.
            </p>
          )}

          {filteredConversations && filteredConversations.length === 0 && (
            <div className="p-4 text-center">
              <p className="text-sm text-gray-500">
                {searchQuery ? "No matching conversations" : "No conversations yet"}
              </p>
            </div>
          )}

          {filteredConversations?.map((conv) => (
            <button
              key={conv.id}
              type="button"
              onClick={() => {
                setActiveConversationId(conv.id);
                setShowSidebar(false);
              }}
              className={clsx(
                "w-full text-left px-4 py-3 border-b border-gray-50 transition-colors",
                activeConversationId === conv.id
                  ? "bg-blue-50 border-l-2 border-l-blue-600"
                  : "hover:bg-gray-50",
              )}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {conv.title ?? "Untitled Conversation"}
                </p>
                <span className="text-xs text-gray-400 shrink-0">
                  {formatRelativeTime(conv.updated_at)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={typeBadgeVariant[conv.conversation_type] ?? "neutral"}>
                  {conv.conversation_type.replace(/_/g, " ")}
                </Badge>
                {conv.status !== "active" && (
                  <Badge variant="neutral">{conv.status}</Badge>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0 bg-white">
        {!showSidebar && (
          <button
            type="button"
            onClick={() => setShowSidebar(true)}
            className="lg:hidden flex items-center gap-2 px-4 py-2 text-sm text-gray-600 border-b border-gray-100 hover:bg-gray-50"
          >
            <MessageSquare size={14} />
            Show conversations
          </button>
        )}

        {activeConversationId ? (
          <ChatArea conversationId={activeConversationId} />
        ) : (
          <EmptyState
            icon={MessageSquare}
            title="Select a conversation"
            description="Choose an existing conversation from the list, or start a new one to begin your legal research."
            actionLabel="New Conversation"
            onAction={handleNewConversation}
          />
        )}
      </div>
    </div>
  );
}
