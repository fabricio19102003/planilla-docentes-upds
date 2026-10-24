import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { MessagesSquare } from 'lucide-react'

import { useChatConversations } from '@/api/hooks/useChat'
import { ChatConversationList } from '@/components/chat/ChatConversationList'
import { NewChatDialog } from '@/components/chat/NewChatDialog'
import { ChatThreadPanel } from '@/components/chat/ChatThreadPanel'
import { cn } from '@/lib/utils'

function useDebouncedValue(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

export function AdminChatPage() {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [newChatOpen, setNewChatOpen] = useState(false)
  const debouncedSearch = useDebouncedValue(search, 300)
  const { data: conversations, isLoading, error } = useChatConversations(debouncedSearch)

  const requested = Number(params.get('c'))
  const selectedId = Number.isInteger(requested) && requested > 0 ? requested : null

  const select = (id: number) => setParams({ c: String(id) })
  const back = () => setParams({})

  return (
    <div className="flex h-[calc(100dvh-6rem)] min-h-[26rem] overflow-hidden rounded-2xl border bg-card shadow-xs sm:h-[calc(100dvh-7rem)] md:h-[calc(100dvh-8rem)]">
      <ChatConversationList
        className={cn('w-full border-e md:w-80 md:shrink-0', selectedId ? 'hidden md:flex' : 'flex')}
        conversations={conversations}
        isLoading={isLoading}
        error={error}
        search={search}
        onSearchChange={setSearch}
        selectedId={selectedId}
        onSelect={select}
        onNewMessage={() => setNewChatOpen(true)}
      />
      <div className={cn('min-w-0 flex-1 flex-col', selectedId ? 'flex' : 'hidden md:flex')}>
        {selectedId ? (
          <ChatThreadPanel
            key={selectedId}
            target={{ side: 'admin', conversationId: selectedId }}
            title="Conversación"
            emptyDescription="Esta conversación todavía no tiene mensajes."
            onBack={back}
          />
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center text-muted-foreground">
            <MessagesSquare className="size-10" aria-hidden="true" />
            <p className="text-sm">Selecciona una conversación para leerla y responder.</p>
          </div>
        )}
      </div>
      <NewChatDialog open={newChatOpen} onOpenChange={setNewChatOpen} onStarted={select} />
    </div>
  )
}
