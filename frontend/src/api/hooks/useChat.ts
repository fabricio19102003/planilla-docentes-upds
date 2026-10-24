import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient, QueryKey } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { ChatConversationSummary, ChatMessage, ChatThread, ChatUnreadCount } from '@/api/types'
import { CHAT_INBOX_POLL_MS, CHAT_THREAD_POLL_MS, lastMessageId, mergeMessages } from '@/lib/chat'

export type ChatSide = 'docente' | 'admin'

/** The open conversation: the docente's own one, or an admin-selected conversation id. */
export type ChatTarget = { side: 'docente' } | { side: 'admin'; conversationId: number }

export const chatKeys = {
  all: ['chat'] as const,
  thread: (target: ChatTarget): QueryKey =>
    target.side === 'docente' ? ['chat', 'thread', 'me'] : ['chat', 'thread', target.conversationId],
  conversations: (q: string): QueryKey => ['chat', 'conversations', q],
  unread: (side: ChatSide): QueryKey => ['chat', 'unread', side],
}

function threadPath(target: ChatTarget): string {
  return target.side === 'docente' ? '/chat/me' : `/chat/conversations/${target.conversationId}/messages`
}

function messagesPath(target: ChatTarget): string {
  return target.side === 'docente' ? '/chat/me/messages' : `/chat/conversations/${target.conversationId}/messages`
}

function readPath(target: ChatTarget): string {
  return target.side === 'docente' ? '/chat/me/read' : `/chat/conversations/${target.conversationId}/read`
}

/**
 * Polls every 5 s while the tab is visible. The first load takes the latest page; every later poll
 * asks only for messages after the cached cursor and appends them, so nothing is refetched in full.
 */
export function useChatThread(target: ChatTarget | null) {
  const key = target ? chatKeys.thread(target) : chatKeys.all
  return useQuery({
    queryKey: key,
    enabled: target !== null,
    retry: false,
    staleTime: 0,
    refetchInterval: CHAT_THREAD_POLL_MS,
    refetchIntervalInBackground: false,
    queryFn: async ({ client }): Promise<ChatThread> => {
      if (!target) throw new Error('No conversation selected')
      const previous = client.getQueryData<ChatThread>(key)
      const after = previous ? lastMessageId(previous.messages) : 0
      const { data } = await api.get<ChatThread>(threadPath(target), { params: after > 0 ? { after } : undefined })
      if (!previous) return data
      return { conversation: data.conversation, messages: mergeMessages(previous.messages, data.messages) }
    },
  })
}

/** Admin inbox list; `q` searches by teacher name or CI. */
export function useChatConversations(q: string) {
  return useQuery({
    queryKey: chatKeys.conversations(q),
    retry: false,
    placeholderData: keepPreviousData,
    refetchInterval: CHAT_INBOX_POLL_MS,
    refetchIntervalInBackground: false,
    queryFn: async () => {
      const { data } = await api.get<ChatConversationSummary[]>('/chat/conversations', {
        params: q.trim() ? { q: q.trim() } : undefined,
      })
      return data
    },
  })
}

export function useChatUnreadCount(side: ChatSide, enabled = true) {
  return useQuery({
    queryKey: chatKeys.unread(side),
    enabled,
    retry: false,
    refetchInterval: CHAT_INBOX_POLL_MS,
    refetchIntervalInBackground: false,
    queryFn: async () => {
      const { data } = await api.get<ChatUnreadCount>(side === 'docente' ? '/chat/me/unread-count' : '/chat/unread-count')
      return data.unread_count
    },
  })
}

export interface SendChatMessagePayload {
  body: string
  files: File[]
}

export function useSendChatMessage(target: ChatTarget) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ body, files }: SendChatMessagePayload) => {
      const formData = new FormData()
      formData.append('body', body)
      for (const file of files) formData.append('files', file)
      const { data } = await api.post<ChatMessage>(messagesPath(target), formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return data
    },
    onSuccess: (message) => {
      queryClient.setQueryData<ChatThread>(chatKeys.thread(target), (thread) =>
        thread ? { ...thread, messages: mergeMessages(thread.messages, [message]) } : thread,
      )
      if (target.side === 'admin') void queryClient.invalidateQueries({ queryKey: ['chat', 'conversations'] })
    },
  })
}

function applyReadResult(queryClient: QueryClient, target: ChatTarget, unread: number) {
  queryClient.setQueryData<ChatThread>(chatKeys.thread(target), (thread) =>
    thread ? { ...thread, conversation: { ...thread.conversation, unread_count: unread } } : thread,
  )
  void queryClient.invalidateQueries({ queryKey: chatKeys.unread(target.side) })
  if (target.side === 'admin') void queryClient.invalidateQueries({ queryKey: ['chat', 'conversations'] })
}

export function useMarkChatRead(target: ChatTarget) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<ChatUnreadCount>(readPath(target))
      return data.unread_count
    },
    onSuccess: (unread) => applyReadResult(queryClient, target, unread),
  })
}

/** Private attachment: authenticated GET as a Blob (never a plain link to the API). */
export async function fetchChatAttachment(attachmentId: number): Promise<Blob> {
  const { data } = await api.get<Blob>(`/chat/attachments/${attachmentId}`, { responseType: 'blob' })
  return data
}
