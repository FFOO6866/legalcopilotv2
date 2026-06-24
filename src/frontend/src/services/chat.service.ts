import { nexusCall } from "./api";
import type { Conversation, Message, RAGFeedback } from "@/types/chat";
import type { PaginatedResponse } from "@/types/common";

export async function createConversation(
  firm_id: string,
  user_id: string,
  case_id?: string,
  conversation_type?: string,
  title?: string,
): Promise<Conversation> {
  return nexusCall<Conversation>("chat.create_conversation", {
    firm_id,
    user_id,
    case_id,
    conversation_type,
    title,
  });
}

export async function sendMessage(
  conversation_id: string,
  content: string,
  firm_id: string,
  user_id?: string,
  case_context?: Record<string, unknown>,
): Promise<Message> {
  return nexusCall<Message>("chat.send_message", {
    conversation_id,
    content,
    firm_id,
    user_id,
    case_context,
  });
}

export async function getConversationHistory(
  conversation_id: string,
  firm_id: string,
  limit?: number,
  offset?: number,
): Promise<PaginatedResponse<Message>> {
  return nexusCall<PaginatedResponse<Message>>("chat.get_conversation_history", {
    conversation_id,
    firm_id,
    limit,
    offset,
  });
}

export async function listConversations(
  firm_id: string,
): Promise<Conversation[]> {
  return nexusCall<Conversation[]>("chat.list_conversations", {
    firm_id,
  });
}

export async function searchConversations(
  firm_id: string,
  query?: string,
  status?: string,
  limit?: number,
  offset?: number,
): Promise<PaginatedResponse<Conversation>> {
  return nexusCall<PaginatedResponse<Conversation>>("chat.search_conversations", {
    firm_id,
    query,
    status,
    limit,
    offset,
  });
}

export async function submitFeedback(
  message_id: string,
  firm_id: string,
  was_helpful: boolean,
  feedback_text?: string,
): Promise<RAGFeedback> {
  return nexusCall<RAGFeedback>("chat.submit_feedback", {
    message_id,
    firm_id,
    was_helpful,
    feedback_text,
  });
}

export async function closeConversation(
  conversation_id: string,
  firm_id: string,
  resolved?: boolean,
): Promise<Conversation> {
  return nexusCall<Conversation>("chat.close_conversation", {
    conversation_id,
    firm_id,
    resolved,
  });
}

export async function draftDocument(
  document_type: string,
  instructions: string,
  firm_id: string,
  user_id?: string,
  case_id?: string,
  case_type?: string,
  facts?: string,
  tone?: string,
): Promise<{ content: string; metadata: Record<string, unknown> }> {
  return nexusCall<{ content: string; metadata: Record<string, unknown> }>(
    "chat.draft_document",
    {
      document_type,
      instructions,
      firm_id,
      user_id,
      case_id,
      case_type,
      facts,
      tone,
    },
  );
}
