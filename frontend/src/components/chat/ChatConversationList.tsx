import { MessageSquareOff, Plus, Search, TriangleAlert } from 'lucide-react'

import type { ChatConversationSummary } from '@/api/types'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorMessage, conversationTitle, formatListTimestamp, initialsOf } from '@/lib/chat'
import { cn } from '@/lib/utils'

export interface ChatConversationListProps {
  conversations: ChatConversationSummary[] | undefined
  isLoading: boolean
  error: unknown
  search: string
  onSearchChange: (value: string) => void
  selectedId: number | null
  onSelect: (id: number) => void
  /** Shows the "Nuevo mensaje" action (admin inbox). */
  onNewMessage?: () => void
  className?: string
}

function previewOf(conversation: ChatConversationSummary): string {
  const last = conversation.last_message
  if (!last) return 'Sin mensajes'
  return last.sender_role === 'admin' ? `Administración: ${last.preview}` : last.preview
}

export function ChatConversationList({
  conversations,
  isLoading,
  error,
  search,
  onSearchChange,
  selectedId,
  onSelect,
  onNewMessage,
  className,
}: ChatConversationListProps) {
  const searching = search.trim().length > 0

  return (
    <section aria-label="Conversaciones" className={cn('flex min-h-0 min-w-0 flex-col', className)}>
      <div className="shrink-0 space-y-2 border-b p-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Conversaciones</h3>
          {onNewMessage && (
            <Button type="button" size="sm" variant="outline" onClick={onNewMessage}>
              <Plus aria-hidden="true" />
              Nuevo mensaje
            </Button>
          )}
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute start-2.5 top-1/2 z-10 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            type="search"
            aria-label="Buscar conversación"
            placeholder="Buscar por nombre o CI"
            className="[&_input]:ps-8"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          <div role="status" className="space-y-1 p-2">
            <span className="sr-only">Cargando conversaciones</span>
            {[0, 1, 2, 3, 4].map((row) => (
              <div key={row} className="flex items-center gap-3 p-2" aria-hidden="true">
                <Skeleton className="size-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-2/3" />
                  <Skeleton className="h-3 w-full" />
                </div>
              </div>
            ))}
          </div>
        ) : error && !conversations ? (
          <div role="alert" className="flex flex-col items-center gap-2 p-6 text-center text-sm">
            <TriangleAlert className="size-6 text-destructive-foreground" aria-hidden="true" />
            {apiErrorMessage(error, 'No se pudieron cargar las conversaciones.')}
          </div>
        ) : conversations && conversations.length === 0 ? (
          <div role="status" className="flex flex-col items-center gap-2 p-6 text-center text-sm text-muted-foreground">
            <MessageSquareOff className="size-6" aria-hidden="true" />
            {searching ? 'Ninguna conversación coincide con la búsqueda.' : 'Todavía no hay conversaciones. Aparecerán cuando un docente escriba o cuando envíes un mensaje nuevo.'}
          </div>
        ) : (
          <ul className="m-0 list-none p-1">
            {conversations?.map((conversation) => {
              const selected = conversation.id === selectedId
              const title = conversationTitle(conversation)
              const unread = conversation.unread_count
              return (
                <li key={conversation.id}>
                  <button
                    type="button"
                    aria-current={selected ? 'true' : undefined}
                    onClick={() => onSelect(conversation.id)}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-xl p-2 text-start outline-none transition-colors hover:bg-accent/60 focus-visible:ring-2 focus-visible:ring-ring',
                      selected && 'bg-accent',
                    )}
                  >
                    <Avatar className="size-10">
                      <AvatarFallback className="bg-primary/10 text-xs font-medium text-primary">{initialsOf(title)}</AvatarFallback>
                    </Avatar>
                    <span className="grid min-w-0 flex-1 gap-0.5">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className={cn('truncate text-sm', unread > 0 ? 'font-semibold' : 'font-medium')}>{title}</span>
                        <span className="shrink-0 text-[11px] text-muted-foreground">
                          {formatListTimestamp(conversation.last_message?.created_at ?? conversation.last_message_at)}
                        </span>
                      </span>
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate text-xs text-muted-foreground">{previewOf(conversation)}</span>
                        {unread > 0 && (
                          <Badge size="default" className="shrink-0 rounded-full">
                            <span aria-hidden="true">{unread > 99 ? '99+' : unread}</span>
                            <span className="sr-only">{unread === 1 ? '1 mensaje sin leer' : `${unread} mensajes sin leer`}</span>
                          </Badge>
                        )}
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </section>
  )
}
