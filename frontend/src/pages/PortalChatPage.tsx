import { ChatThreadPanel } from '@/components/chat/ChatThreadPanel'

export function PortalChatPage() {
  return (
    <div className="flex h-[calc(100dvh-6rem)] min-h-[26rem] max-w-3xl flex-col overflow-hidden rounded-2xl border bg-card shadow-xs sm:h-[calc(100dvh-7rem)] md:h-[calc(100dvh-8rem)]">
      <ChatThreadPanel
        target={{ side: 'docente' }}
        title="Administración"
        subtitle="Cualquier persona de administración puede responderte"
        emptyDescription="Escribe tu consulta a Administración. Puedes adjuntar PDF o imágenes."
      />
    </div>
  )
}
