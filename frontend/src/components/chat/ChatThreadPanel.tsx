import { useEffect, useState, useSyncExternalStore } from 'react'
import { ArrowLeft, MessageSquareText, TriangleAlert } from 'lucide-react'

import { useChatThread, useMarkChatRead, useSendChatMessage } from '@/api/hooks/useChat'
import type { ChatTarget } from '@/api/hooks/useChat'
import type { ChatSenderRole } from '@/api/types'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { ChatAttachments } from './ChatAttachments'
import { ChatComposer } from './ChatComposer'
import { ChatConversation } from './chat-conversation'
import { ChatDatePill } from './chat-date-pill'
import { ChatMessage } from './chat-message'
import { ChatMessageText } from './chat-message-text'
import { ChatEmptyState, ChatLoadingState } from './chat-states'
import { ChatUnreadDivider } from './chat-unread-divider'
import { useChatScroll } from './hooks/use-chat-scroll'
import { apiErrorMessage, buildThreadItems, conversationTitle, formatMessageTime, groupByDay, initialsOf, unreadDividerMessageId } from '@/lib/chat'

function subscribeToVisibility(onChange: () => void) {
  document.addEventListener('visibilitychange', onChange)
  return () => document.removeEventListener('visibilitychange', onChange)
}

function usePageVisible(): boolean {
  return useSyncExternalStore(
    subscribeToVisibility,
    () => document.visibilityState === 'visible',
    () => true,
  )
}

export interface ChatThreadPanelProps {
  target: ChatTarget
  title: string
  subtitle?: string
  emptyDescription: string
  onBack?: () => void
}

/** One open conversation: header, message log, composer. Mount it with a `key` per conversation. */
export function ChatThreadPanel({ target, title, subtitle, emptyDescription, onBack }: ChatThreadPanelProps) {
  const viewer: ChatSenderRole = target.side
  const thread = useChatThread(target)
  const send = useSendChatMessage(target)
  const markRead = useMarkChatRead(target)
  const visible = usePageVisible()

  const data = thread.data
  const messages = data?.messages
  const unread = data?.conversation.unread_count ?? 0

  // The divider is placed once, when the conversation opens, so it stays put after marking as read.
  const [dividerId, setDividerId] = useState<number | null | undefined>(undefined)
  if (data && dividerId === undefined) {
    setDividerId(unreadDividerMessageId(data.messages, viewer, data.conversation.unread_count))
  }

  const markReadMutate = markRead.mutate
  useEffect(() => {
    if (unread > 0 && visible) markReadMutate()
  }, [unread, visible, markReadMutate])

  // Admins get the real teacher name from the thread, even when the list is filtered by a search.
  const heading = target.side === 'admin' && data ? conversationTitle(data.conversation) : title
  const headingSubtitle = target.side === 'admin' && data ? `CI ${data.conversation.teacher_ci}` : subtitle

  const items = messages ? buildThreadItems(messages, viewer, dividerId ?? null) : []
  const lastId = messages && messages.length > 0 ? messages[messages.length - 1].id : 0
  const scroll = useChatScroll({ itemCount: items.length, layoutKey: lastId })

  return (
    <section aria-label={`Conversación con ${heading}`} className="flex min-h-0 min-w-0 flex-1 flex-col">
      <header className="flex shrink-0 items-center gap-3 border-b px-3 py-2.5 sm:px-4">
        {onBack && (
          <Button type="button" variant="ghost" size="icon" className="md:hidden" aria-label="Volver a conversaciones" onClick={onBack}>
            <ArrowLeft />
          </Button>
        )}
        <Avatar className="size-9">
          <AvatarFallback className="bg-primary text-xs text-primary-foreground">{initialsOf(heading)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold">{heading}</h3>
          {headingSubtitle && <p className="truncate text-xs text-muted-foreground">{headingSubtitle}</p>}
        </div>
      </header>

      {thread.isError && !data ? (
        <div role="alert" className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
          <TriangleAlert className="size-8 text-destructive-foreground" aria-hidden="true" />
          <p className="max-w-sm text-sm">{apiErrorMessage(thread.error, 'No se pudo cargar la conversación.')}</p>
          <Button type="button" variant="outline" size="sm" onClick={() => void thread.refetch()}>
            Reintentar
          </Button>
        </div>
      ) : (
        <ChatConversation
          scroll={scroll}
          label="Mensajes de la conversación"
          jumpLabel="Ir al último mensaje"
          live="polite"
          contentClassName="flex flex-col gap-1.5"
        >
          {!data ? (
            <ChatLoadingState label="Cargando mensajes" />
          ) : data.messages.length === 0 ? (
            <ChatEmptyState
              icon={<MessageSquareText />}
              title="Aún no hay mensajes"
              description={emptyDescription}
            />
          ) : (
            groupByDay(items).map((day) => (
              // One section per day keeps each sticky date pill inside its own day.
              <div key={day.key} className="flex flex-col gap-1.5">
                <ChatDatePill>{day.label}</ChatDatePill>
                {day.items.map((item) => {
                  if (item.kind === 'unread') return <ChatUnreadDivider key={item.key}>Mensajes nuevos</ChatUnreadDivider>
                  const { message, side, grouped } = item
                  const author = message.sender_name ?? (message.sender_role === 'admin' ? 'Administración' : heading)
                  return (
                    <ChatMessage
                      key={item.key}
                      side={side}
                      grouped={grouped}
                      author={author}
                      avatar={
                        <Avatar className="size-7">
                          <AvatarFallback className="text-[10px]">{initialsOf(author)}</AvatarFallback>
                        </Avatar>
                      }
                      footer={
                        <time dateTime={message.created_at}>
                          {viewer === 'admin' && side === 'outgoing' && message.sender_name
                            ? `${message.sender_name} · ${formatMessageTime(message.created_at)}`
                            : formatMessageTime(message.created_at)}
                        </time>
                      }
                    >
                      <>
                        {message.body && <ChatMessageText text={message.body} />}
                        <ChatAttachments attachments={message.attachments} />
                      </>
                    </ChatMessage>
                  )
                })}
              </div>
            ))
          )}
        </ChatConversation>
      )}

      <ChatComposer onSend={(payload) => send.mutateAsync(payload)} />
    </section>
  )
}
