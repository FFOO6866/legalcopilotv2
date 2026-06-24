import { create } from "zustand";
import type { Conversation, Message } from "@/types/chat";

interface ChatStore {
  conversations: Map<string, Conversation>;
  activeConversationId: string | null;
  messages: Map<string, Message[]>;
  isProcessing: boolean;
  setActiveConversation: (id: string | null) => void;
  addConversation: (conversation: Conversation) => void;
  addMessage: (conversationId: string, message: Message) => void;
  setProcessing: (processing: boolean) => void;
  clearMessages: (conversationId: string) => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  conversations: new Map<string, Conversation>(),
  activeConversationId: null,
  messages: new Map<string, Message[]>(),
  isProcessing: false,

  setActiveConversation: (id: string | null) => {
    set({ activeConversationId: id });
  },

  addConversation: (conversation: Conversation) => {
    set((state) => {
      const updated = new Map(state.conversations);
      updated.set(conversation.id, conversation);
      return { conversations: updated };
    });
  },

  addMessage: (conversationId: string, message: Message) => {
    set((state) => {
      const updated = new Map(state.messages);
      const existing = updated.get(conversationId) ?? [];
      updated.set(conversationId, [...existing, message]);
      return { messages: updated };
    });
  },

  setProcessing: (processing: boolean) => {
    set({ isProcessing: processing });
  },

  clearMessages: (conversationId: string) => {
    set((state) => {
      const updated = new Map(state.messages);
      updated.set(conversationId, []);
      return { messages: updated };
    });
  },
}));
